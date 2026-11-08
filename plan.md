# Warehouse Ops MCP Toolkit — Implementation Plan

Implements the interface defined in `spec.md` (committed as `01-spec`). This plan does not
redesign the interface; where implementation reveals a genuine design flaw, `spec.md`
is amended in a **separate, later commit** with the reason recorded (the `01-spec` commit
itself is never rewritten).

## 1. Objective

Deliver a working MCP server exposing the 10 tools in `spec.md` (4 read-only, 6
state-changing) over the supplied data, registered in Claude Code, with tests and
runtime evidence that show:

- schema-constrained inputs and actionable errors (including on schema rejection);
- site scoping enforced from trusted session context, with same-site access working;
- ambiguous search returning candidates, unambiguous search answering directly;
- tiered confirmation, with server-issued tokens for irreversible operations;
- an agent selecting tools at runtime and asking a clarifying question instead of guessing.

## 2. Technology

Python 3.11 · MCP Python SDK · Pydantic v2 · pytest · pytest-asyncio · supplied CSV/JSONL as stub data.
Agent host: Claude Code (project-scoped `.mcp.json`).

## 3. Repository layout

```text
spec.md  plan.md  tasks.md                  # commits 01, 02, 03 (one file each)
--- everything below arrives in 04-implement or later ---
pyproject.toml
data/stock_snapshot.csv  data/dock_schedule.jsonl
src/warehouse_mcp/
    server.py        # MCP wiring: tool list, schemas, annotations, dispatch, server instructions
    context.py       # SessionContext from env; startup validation
    models.py        # Pydantic input models (extra="forbid") + shared enums/patterns
    errors.py        # ToolError, error codes, envelope builders
    store.py         # in-memory stock/dock/exception state + audit ledger (no MCP imports)
    search.py        # tokeniser + matcher (pure functions)
    confirm.py       # preview + single-use token store (TTL 300 s)
    tools/           # one module per tool group: stock, dock, exceptions
tests/               # pytest-asyncio suite (see §6)
evidence/            # runtime transcripts, pytest output, git log --stat
.mcp.json  .claude/settings.json  CLAUDE.md  AGENT_INSTRUCTIONS.md
REFLECTION.md
```

## 4. Key implementation decisions

| Decision                                         | Approach                                                                                                                                                                                                                                                                                                                                                                                                                           | Risk it addresses                                                                 |
| ------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| **Schema rejection must return our error shape** | Validate inside the toolkit with Pydantic models (`extra="forbid"`), and publish the same JSON Schema as each tool's `inputSchema`. Map `ValidationError` → `INVALID_ARGUMENT` with `field`, `details.allowed_values` and `example_call`. Verify early against the installed SDK version (spike, task 4.1): the SDK's default path can turn validation failures into a generic error string, which would fail "actionable errors". | Model sees closed sets **and** gets self-correctable errors.                      |
| **Trusted session context**                      | `KESTREL_CALLER_ID` / `KESTREL_ASSIGNED_SITE` read once at startup from the launcher's environment; server exits on missing/invalid values. No tool reads a site from arguments except the optional `site` _assertion_, compared to context.                                                                                                                                                                                       | Site scope cannot be widened by the model.                                        |
| **Scoping in one place**                         | A single `scope` helper used by every tool: filters rows by session site, resolves whether a SKU/exception belongs to another site, and builds `SITE_ACCESS_DENIED` with no foreign data. Tools never touch unfiltered rows directly.                                                                                                                                                                                              | No tool can forget to scope.                                                      |
| **Tiered confirmation**                          | Tier 1: `confirm` flag. Tier 2: `confirm.py` issues a random single-use token bound to (caller, tool, canonical args), TTL 300 s. Validation runs _before_ a preview is issued and again at execution.                                                                                                                                                                                                                             | Preview never offered for a call that would fail; state re-checked at commit.     |
| **Search**                                       | Pure function implementing spec §9 rules; the §9 outcome table is the test oracle. Site filter first, then match.                                                                                                                                                                                                                                                                                                                  | Ambiguity handled by data, not model judgement; single matches answered directly. |
| **State and ledger**                             | In-memory copies of the data files; append-only audit list; `store.py` has no MCP dependency so it is unit-testable.                                                                                                                                                                                                                                                                                                               | Corrections auditable; tests reset state per test.                                |
| **Guidance ships with the server**               | Tool descriptions (spec §8 verbatim), result `next_step` fields, and MCP server `instructions` carry the behavioural rules. `AGENT_INSTRUCTIONS.md` is a convenience layer, not a dependency.                                                                                                                                                                                                                                      | The assessing agent may never see our instructions file.                          |
| **Read/write distinction in the interface**      | Name prefixes, description prefixes, and MCP annotations (`readOnlyHint`, `destructiveHint`).                                                                                                                                                                                                                                                                                                                                      | Model and host can tell reads from writes without reading prose.                  |

## 5. Phases

Each phase lists the spec sections it implements.

1. **Project setup** — environment, dependencies, data files under `data/`. _(All)_
2. **Errors and envelope** — error codes, envelope builders, `example_call` helper. _(§7)_
3. **Session context and scope helper** — startup validation, `site` assertion, cross-site cases. _(§5)_
4. **Models** — Pydantic inputs, patterns, enums, ranges, `extra="forbid"`. _(§7.5, §8)_
5. **Store and ledger** — stock rows per (SKU, bin), dock slots, exceptions, audit entries. _(§2, §6)_
6. **Search** — tokeniser, matcher, `unique`/`multiple`/`NOT_FOUND`. _(§9)_
7. **Read tools** — `get_stock`, `search_stock`, `list_dock_slots`, `list_exceptions`. _(§8.1–8.3, 8.9)_
8. **Confirmation** — tier-1 preview; tier-2 token store. _(§6)_
9. **Write tools** — `book_dock_slot`, `cancel_dock_booking`, `correct_stock`, `move_stock`, `raise_exception`, `close_exception`. _(§8.4–8.8, 8.10)_
10. **MCP server** — register 10 tools with schemas, descriptions, annotations, server `instructions`; stdio entry point. _(§7.1)_
11. **Tests** — see §6.
12. **Claude Code integration** — `.mcp.json`, permissions, `CLAUDE.md`, `AGENT_INSTRUCTIONS.md`. _(§11)_
13. **Runtime demonstration** — see §7.
14. **Documentation** — changes-from-request summary (from spec §3), `REFLECTION.md`, declared-effort statement.

## 6. Test strategy (pytest-asyncio)

Tests drive the server **through the MCP protocol** (in-memory client session, or a stdio
subprocess), not by calling Python functions, because the toolkit will be exercised by an
agent. State resets per test. Site-dependent tests are parametrised over all three sites.

| Area             | What is asserted                                                                                                                                                                                                                                                                                                                                                                    |
| ---------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Invocation       | Each of the 10 tools succeeds on a valid same-site call; `list_tools` shows enums, patterns and annotations.                                                                                                                                                                                                                                                                        |
| Schema rejection | Bad SKU pattern, bad slot (`"10am"`), bad category, negative/zero quantity, missing field, extra property → `INVALID_ARGUMENT` with `field` and `example_call`.                                                                                                                                                                                                                     |
| Search oracle    | Every row of the spec §9 table, at the right site, including `void fill` (unique at Leeds and Glasgow) and zero-stock `600mm shrink film` returned as success.                                                                                                                                                                                                                      |
| Ambiguity        | `multiple` results contain **no quantities**; zero-stock candidates are present.                                                                                                                                                                                                                                                                                                    |
| Site scoping     | For each session site: same-site SKU works; another site's SKU → `SITE_ACCESS_DENIED`; `site=<other>` on every tool → denied; `site=<own>` accepted; `to_bin` in another site's zone rejected; responses for a denied call contain no foreign SKU description, quantity or bin (scan the serialised response). Docks: Leeds session never sees Reading rows for the same slot time. |
| Confirmation     | Tier 1: no `confirm` → nothing changed + preview. Tier 2: no token → preview + token, state unchanged; correct token → executes; reused, expired, foreign-caller and changed-argument tokens → `INVALID_CONFIRMATION`; no preview issued for a failing call.                                                                                                                        |
| Business rules   | Booking a booked slot → `SLOT_ALREADY_BOOKED` with alternatives; cancel of an available slot → `NOT_FOUND`; move more than available → `INSUFFICIENT_STOCK`; correction with wrong `expected_current_quantity` → `STALE_QUANTITY`; second close → `ALREADY_CLOSED`.                                                                                                                 |
| Error shape      | Every error code returns `code`, `message`, `field`, `details`, `suggested_action` (and `example_call` where constructible); no error contains another site's data.                                                                                                                                                                                                                 |
| Ledger           | Each executed write appends one audit entry with before/after; failed and preview calls append none.                                                                                                                                                                                                                                                                                |
| Startup          | Missing or invalid `KESTREL_ASSIGNED_SITE` prevents startup.                                                                                                                                                                                                                                                                                                                        |

Capture the full passing output to `evidence/pytest_output.txt`.

## 7. Runtime demonstration with Claude Code

- `spec.md` contains the complete tool interface design.
- `plan.md` and `tasks.md` reflect the implementation approach.
- All nine MCP tools are implemented.
- Input schemas reject invalid values.
- Closed sets are represented by schemas.
- Read-only and state-changing tools are clearly separated.
- State-changing operations require confirmation.
- Site access is enforced inside the toolkit.
- Ambiguous stock searches return candidates instead of guessing.
- Unambiguous searches do not require unnecessary clarification.
- Actionable errors are returned.
- `AGENT_INSTRUCTIONS.md` provides Claude-specific tool-use guidance.
- Claude Code can discover and use the MCP server.
- Claude asks a clarification question for an ambiguous stock lookup.
- Claude requires confirmation before state-changing operations.
- Cross-site access is rejected by the toolkit.
- `pytest-asyncio` tests pass.
- Runtime evidence is captured.
- Required documentation and reflection are included.
- The required Git commit sequence is preserved.

## 6. Requirement Traceability and Implementation Gates

The supplied data is part of the design evidence, not just test input. Before implementation is accepted, record these observations:

- `SKU-8801` and `SKU-8802` are both pallet wrap variants at Leeds, so a broad "pallet wrap" request is ambiguous.
- `SKU-8803` and `SKU-8804` are distinct strapping-band sizes, so description search must return candidates rather than a fuzzy winner.
- `SKU-8809` exists with quantity `0`, so zero stock must be reported as a valid record rather than `NOT_FOUND`.
- Dock records contain both available and booked slots at each site, so booking must validate current state and cannot overwrite an existing booking.
- Stock corrections affect the month-end count according to the Ops brief; therefore they are confirmed writes, separate from physical bin movements.

The implementation is complete only when these gates pass:

1. `spec.md` is the frozen contract: all nine tools have typed parameters, model-facing descriptions, closed sets, response rules, and error behavior.
2. A real MCP entry point registers the nine tools and injects trusted `CallerContext`; no public tool accepts `site` as an authorization parameter.
3. The state layer persists changes for the lifetime of the server session and exposes them to subsequent reads; no tool reports success before applying its mutation.
4. Schema validation runs before business logic, while business errors use the common actionable error shape.
5. Tests prove both same-site success and cross-site refusal, ambiguous and unambiguous lookup behavior, zero stock, confirmation refusal, successful confirmation, invalid enums, already-booked slots, insufficient stock, and exception lifecycle rules.
6. The MCP host transcript demonstrates discovery, tool selection, clarification, confirmation, and correction from an actionable error. Store the registration/configuration and test output as repository evidence.
7. `.claude/CLAUDE.md` contains the project workflow and safety rules; `.claude/instructions/AGENT_INSTRUCTIONS.md` contains the model-facing tool-use guidance. Neither replaces server enforcement.

## 7. Known Gaps to Close Before `04-implement`

The current service modules are useful building blocks, but they are not by themselves a registered MCP server. The implementation phase must still add or verify:

- an MCP server entry point and tool registration
- Pydantic/MCP schemas matching `spec.md`, including `confirmation: true`
- durable in-session mutation for corrections, movements, bookings, cancellations, and exceptions
- server-generated exception IDs and site-scoped exception persistence
- an MCP-host registration file and runtime transcript
- focused async tests for the contract and evidence listed above
