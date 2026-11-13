# Warehouse Ops MCP Toolkit: Implementation Plan

Implements the interface in `spec.md` (committed as `01-spec`). This plan does not
redesign the interface. If implementation exposes a genuine design flaw, `spec.md` is
amended in a **separate, later commit** with the reason recorded; the `01-spec` commit
is never rewritten.

## 1. Objective

Deliver a working MCP server exposing the 10 tools in `spec.md` (4 read-only, 6
state-changing) over the supplied data, registered in Claude Code, with tests and
runtime evidence showing:

- schema-constrained inputs, with closed sets as enums, and actionable errors, including on schema rejection;
- site scoping from trusted server context, with same-site access working and cross-site access refused;
- ambiguous search returning candidates, unambiguous search answering directly;
- two-step confirmation (preview, then token) on all six write tools;
- an agent selecting tools at runtime and asking a clarifying question instead of guessing.

## 2. Technology

Python 3.11, MCP Python SDK, Pydantic v2, pytest, pytest-asyncio, supplied CSV/JSONL as
stub data. Agent host: Claude Code, with a project-scoped `.mcp.json`.

## 3. Repository layout

```text
spec.md  plan.md  tasks.md                  # commits 01, 02, 03 (one file each)
--- everything below arrives in 04-implement or later ---
pyproject.toml
data/stock_snapshot.csv  data/dock_schedule.jsonl
src/warehouse_mcp/
    server.py        # MCP wiring: tool list, schemas, annotations, dispatch, server instructions
    context.py       # SessionContext from env; refuses to start if invalid (spec 5)
    models.py        # Pydantic input models (extra="forbid"), enums, patterns
    errors.py        # error codes, envelope builder, example_call helper (spec 6)
    store.py         # in-memory stock/dock/exception state; no MCP imports
    scope.py         # the single place that filters by site and detects cross-site identifiers
    search.py        # tokeniser and matcher (pure functions)
    confirm.py       # preview + single-use token store (spec 7.1)
    tools/           # stock.py, dock.py, exceptions.py
tests/               # pytest-asyncio suite (section 7)
evidence/            # runtime transcript, pytest output, git log --stat
.mcp.json  .claude/settings.json  CLAUDE.md  AGENT_INSTRUCTIONS.md
REFLECTION.md
```

## 4. Key implementation decisions

| Decision | Approach | Risk it addresses |
| --- | --- | --- |
| **Schema rejection must return our error shape** (spec 6) | Validate inside the toolkit with Pydantic models (`extra="forbid"`), and publish the same JSON Schema as each tool's `inputSchema`, so the agent still sees the enums and patterns. Turn the SDK's own input validation off for tool calls if the installed version allows it (task spike, e.g. the low-level server's `validate_input` option); otherwise catch its failure and re-raise in our shape. Map `ValidationError` to `INVALID_ARGUMENT` with `field`, allowed values and `example_call`. | The SDK's default path can return a generic string, which would fail "actionable errors". Publishing the schema keeps closed sets visible to the model. |
| **Trusted session context** (spec 5) | `KESTREL_CALLER_ID` and `KESTREL_ASSIGNED_SITE` read once at startup; the server exits if either is missing or the site is not one of the three. **No tool has a `site` parameter.** | Site scope cannot be widened by the model. |
| **Scoping in one place** | `scope.py` filters rows by session site and, for a caller-named identifier (SKU, `to_bin`, exception ID), detects that it belongs to another site and builds `SITE_ACCESS_DENIED` with no foreign data. Tools never touch unfiltered rows. | No tool can forget to scope. |
| **Two-step confirmation on all six writes** (spec 7) | Preview call runs full schema and business validation, changes nothing, and returns `CONFIRMATION_REQUIRED` with `proposed_action` and a token. Token from `secrets.token_urlsafe`, single-use, 300 s TTL, bound to (caller, tool, canonical JSON of arguments). Commit re-validates state, because it may have changed since the preview. The clock is injectable so expiry is testable. | A blind one-shot write; confirming something that would fail; token reuse for a different action. |
| **Search** (spec 4.2) | Pure function: site filter first, then every query word must appear in the description (case-insensitive, trailing "s" ignored on words longer than 3 letters). Result is `single` (with quantity) or `multiple` (no quantities or bins). | Ambiguity decided by data, not model judgement. |
| **State** | In-memory copies of the data files, one row per (SKU, bin), reset per test by a fixture. `store.py` has no MCP dependency. A small append-only audit list records executed writes so tests can assert that previews and failures wrote nothing. | Unit-testable state; previews provably side-effect free. |
| **Guidance ships with the server** | Tool descriptions are taken verbatim from spec 4.x, results carry `next_step`, and the MCP server `instructions` field restates the key rules. `AGENT_INSTRUCTIONS.md` is a convenience layer only. | The assessing agent may never see our instructions file. |
| **Read/write distinction in the interface** | `READ-ONLY.` / `CHANGES STATE.` description prefixes plus MCP annotations (`readOnlyHint`, `destructiveHint` on cancel, correct and close). | Model and host can tell reads from writes without reading prose. |
| **Host permissions** | `.claude/settings.json` pre-approves the four read-only tools only; write tools stay on the host's approval prompt. | The server token proves the preview matched the commit; the host prompt is the human gate (spec 7.1). |

## 5. Build order

Build a thin vertical slice first, then widen. Each step lists the spec sections it implements.

1. **Setup:** environment, dependencies, data under `data/`. *(all)*
2. **Errors and envelope:** codes, builder, `example_call` helper. *(spec 6)*
3. **Context and scope:** startup validation, cross-site detection. *(spec 5)*
4. **Models:** Pydantic inputs with enums, patterns and ranges. *(spec 4.x schemas)*
5. **Store:** stock per (SKU, bin), dock slots, exceptions. *(spec 2)*
6. **Search:** tokeniser and matcher. *(spec 4.2)*
7. **Read tools:** `get_stock`, `search_stock`, `list_dock_slots`, `list_exceptions`. *(spec 4.1 to 4.4)*
8. **MCP server skeleton with the four read tools and the validation spike.** Register in Claude Code early and confirm the agent can discover and call them. This is the point to resolve the SDK validation question, before building on it. *(spec 4.0, 6)*
9. **Confirmation:** preview and token store. *(spec 7.1)*
10. **Write tools:** book, cancel, correct, move, raise, close. *(spec 4.5 to 4.10)*
11. **Tests:** written alongside steps 2 to 10, completed here. *(section 7)*
12. **Claude Code integration:** `.mcp.json`, `.claude/settings.json`, `CLAUDE.md`, `AGENT_INSTRUCTIONS.md` updated to the ten tools and nine error codes.
13. **Runtime demonstration:** section 8.
14. **Documentation:** changes-from-request summary (spec 3), `REFLECTION.md`, declared-effort statement.

## 6. Requirement traceability and gates

The supplied data is design evidence, not just test input. The implementation must honour:

- `SKU-8801`/`8802` are two pallet wrap variants at Leeds, so "pallet wrap" is ambiguous.
- `SKU-8803`/`8804` are two strapping-band sizes, so search returns candidates rather than a fuzzy winner.
- `SKU-8809` has quantity `0`, so zero stock is a valid result, never `NOT_FOUND`.
- Each site has both available and booked slots, so booking must check current state and never overwrite.
- Corrections feed the month-end count, so they are confirmed writes, separate from bin moves.

The implementation is complete only when:

1. A real MCP entry point registers all **ten** tools and takes the site only from trusted context; no tool accepts a `site` argument.
2. Schema validation runs before business logic, and every failure, including schema rejection, uses the spec 6 error shape.
3. Changes persist for the life of the server session and are visible to later reads; no tool reports success before applying its change.
4. Tests prove same-site success **and** cross-site refusal, ambiguous and unambiguous lookup, zero stock, preview-then-commit, token misuse, invalid enums, booked slot, insufficient stock and the exception lifecycle.
5. The Claude Code transcript shows discovery, tool selection, a clarification question, the confirmation flow, and correction from an actionable error.
6. Registration config and pytest output are stored under `evidence/`.

## 7. Test strategy (pytest-asyncio)

Tests drive the server **through the MCP protocol** (in-memory client session or stdio
subprocess), not by calling Python functions, because the toolkit will be used by an
agent. State resets per test. Site-dependent tests are parametrised over all three sites.

| Area | What is asserted |
| --- | --- |
| Invocation | Each of the 10 tools succeeds on a valid same-site call; `list_tools` shows the enums, patterns and annotations, and no tool exposes a `site` property. |
| Schema rejection | Bad SKU pattern, `slot: "11:00"` and `"10am"`, bad category, zero or negative quantity, missing field, extra property (including `site`) all give `INVALID_ARGUMENT` with `field`, allowed values and `example_call`. |
| Search oracle | Parametrised cases from the data. Leeds: "pallet wrap" gives 2, "pallet" gives 4, "void fill" gives 1 (8811), "strapping 12" gives 1 (8803). Reading: "tape" gives 2, "edge board" gives 1. Glasgow: "shrink film" gives 2, "600mm shrink film" gives 1 (8809, quantity 0, success), "void fill" gives 1 (8810). Cross-site: "edge board" at Leeds is `NOT_FOUND`. |
| Ambiguity | `multiple` results contain **no quantities or bins**; zero-stock candidates are present; `next_step` is set. |
| Site scoping | Per session site: same-site SKU works; another site's SKU gives `SITE_ACCESS_DENIED` on `get_stock`, `correct_stock`, `move_stock` and `raise_exception`; a `to_bin` from another site's zone is denied; an exception ID from another site is denied; the serialised denial contains no foreign description, quantity, bin or site name. Docks: a Leeds session never sees Reading rows for the same slot time. Startup with a missing or invalid `KESTREL_ASSIGNED_SITE` fails. |
| Confirmation | For each write tool: no token gives `CONFIRMATION_REQUIRED` and state unchanged; correct token executes; the same token reused, an expired token, a token for different arguments, and a token from a different tool all give `CONFIRMATION_INVALID` and change nothing. A call that would fail returns its business error at preview time and issues no token. |
| Business rules | Booking a booked slot gives `SLOT_ALREADY_BOOKED` with alternatives; cancelling an available slot gives `SLOT_NOT_BOOKED`; moving more than held gives `INSUFFICIENT_STOCK` with `available` and `requested`; `from_bin` equal to `to_bin` is `INVALID_ARGUMENT`; a date with no schedule gives `NOT_FOUND` with `scheduled_dates`; a second close gives `ALREADY_CLOSED`. |
| Move and correct | A partial move leaves the remainder and creates the destination row; total is unchanged; `correct_stock` on a bin that does not hold the SKU gives `NOT_FOUND` listing the bins that do. |
| Error shape | Every code in spec 6 returns `code`, `message`, `field`, `details`, `suggested_action`, with `example_call` where one can be built. |
| Audit | Each executed write appends one entry with before and after; previews and failed calls append none. |

Capture the full passing output to `evidence/pytest_output.txt`.

## 8. Runtime demonstration plan (Claude Code)

**Registration.** One server entry in `.mcp.json` with `KESTREL_ASSIGNED_SITE=LEEDS-01`.
Do **not** register one server per site in the same host: the agent could then choose a
site by choosing a server, which defeats the scoping. For Reading and Glasgow cases,
change the env value and restart the host, and record each session separately.

Prompts are phrased the way Ops would phrase them:

| # | Session site | Prompt | Expected behaviour |
| --- | --- | --- | --- |
| 1 | Leeds | "how much void fill have we got" | `search_stock`, single match (8811), answers directly without a question |
| 2 | Leeds | "how many rolls of pallet wrap" | `search_stock`, multiple, **asks clear or black**; no quantity quoted |
| 3 | Leeds | "the black one" | `get_stock` for SKU-8802, answers 180 |
| 4 | Leeds | "what's the stock on SKU-8805" | `SITE_ACCESS_DENIED`; agent says it is not stocked here and quotes nothing |
| 5 | Leeds | "what docks are free on 8 April 2026" | `list_dock_slots`, reports 06:00, 10:00, 14:00, 16:00 |
| 6 | Leeds | "book the 10:00 for Northbound" | preview, user agrees, commit; then "book the 08:00" gives `SLOT_ALREADY_BOOKED` and the agent offers alternatives |
| 7 | Leeds | "book the 11:00" | `INVALID_ARGUMENT`; agent corrects to a valid slot or asks |
| 8 | Leeds | "the black wrap count is actually 175" | `get_stock` for the bin, preview shows 180 to 175, user agrees, commit |
| 9 | Leeds | "that pallet wrap is damaged, raise it" then "close it, we replaced it" | `raise_exception`, `list_exceptions`, `close_exception`; the agent warns that closing is final |
| 10 | Glasgow | "how many 600mm shrink film" | success with quantity 0, reported as zero, not as "not found" |

Save the transcript to `evidence/agent_transcript.md`, the registration to
`evidence/registration/`, and `git log --stat` to `evidence/git_log.txt`.

## 9. Risks

| Risk | Mitigation |
| --- | --- |
| SDK validation replaces our error shape | Spike in build step 8 before anything depends on it; fallback is to catch and re-raise. |
| The agent skips the preview and tries to commit blindly | The server rejects a missing or wrong token; tests cover it. |
| The agent asks needlessly on a single match | `search_stock` returns `single` with the quantity; demo prompt 1 and the search oracle prove it. |
| Per-site servers in one host let the agent pick a site | One registration per session (section 8). |
| Over-scoping: blocking same-site access | Scoping tests are parametrised so every same-site call must succeed alongside every cross-site refusal. |
| Instructions file never reaches the assessing agent | Descriptions, `next_step` and server `instructions` carry the rules (section 4). |

## 10. Process rules

- `02-plan` contains `plan.md` only. `03-tasks` adds `tasks.md` only. No source, config
  or test file appears before `04-implement`.
- After `04-implement`, further commits are fine (evidence, reflection, spec amendments
  with reasons).