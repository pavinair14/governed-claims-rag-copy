# Warehouse Ops MCP Toolkit: Tasks

Ordered work breakdown for `plan.md`, implementing `spec.md`. Each task has a
**Done when** line so progress is checkable. Tests are written with the code they cover,
not afterwards. "Spec" references point to sections of `spec.md`.

## Process rules (apply to every task)

- `01-spec` (spec.md), `02-plan` (plan.md) and `03-tasks` (tasks.md) are already one file each.
- No source, config or test file is committed before `04-implement`. Work in the working
  tree and commit it as `04-implement` once the server runs and the core tests pass.
- Later commits (evidence, reflection, documented spec amendments) are expected.
- If a task reveals a flaw in `spec.md`, do not edit `01-spec`; amend the spec in a later
  commit and record the reason in `REFLECTION.md`.

---

## Phase 1: Setup

| ID | Task | Done when |
| --- | --- | --- |
| 1.1 | Create `pyproject.toml`, virtual environment and install Python 3.11, MCP SDK, Pydantic v2, pytest, pytest-asyncio | `pytest` runs (zero tests) with asyncio mode configured |
| 1.2 | Place `stock_snapshot.csv` and `dock_schedule.jsonl` under `data/`; create the `src/warehouse_mcp/` and `tests/` package skeletons | Package imports without error |
| 1.3 | Add shared fixtures: fresh store per test, session context for each of the three sites, injectable clock | A test can start with a clean state for any site |

## Phase 2: Foundations (spec 2, 5, 6)

| ID | Task | Done when |
| --- | --- | --- |
| 2.1 | `errors.py`: the nine codes from spec 6, one envelope builder, an `example_call` helper | Unit tests show every code produces `code`, `message`, `field`, `details`, `suggested_action` |
| 2.2 | `context.py`: read `KESTREL_CALLER_ID` and `KESTREL_ASSIGNED_SITE`; refuse to start if missing or not one of the three sites | Tests: valid for each site; missing and invalid values fail |
| 2.3 | `models.py`: Pydantic input models with `extra="forbid"`, enums for slot, status and category, patterns for SKU and exception ID, ranges and lengths exactly as spec 4.x | Each model rejects the bad values listed in plan section 7 |
| 2.4 | `store.py`: load the CSV into one row per (SKU, bin) and the JSONL into slots; empty exceptions list; no MCP imports | Loaded counts: 16 SKUs, 18 slots, 5 booked; SKU-8809 has quantity 0 |
| 2.5 | `scope.py`: filter by session site; detect that a caller-named SKU, bin prefix or exception ID belongs to another site; build `SITE_ACCESS_DENIED` with no foreign data | Tests: same-site passes, other-site denied, denial text contains no foreign description, quantity, bin or site name |
| 2.6 | `search.py`: tokenise (case-insensitive, trailing "s" ignored on words over 3 letters), match when every word appears, return `single` or `multiple` | The search oracle table in plan section 7 passes for all three sites |

## Phase 3: Read tools (spec 4.1 to 4.4)

| ID | Task | Done when |
| --- | --- | --- |
| 3.1 | `get_stock` | Same-site SKU returns locations and total; SKU-8809 returns quantity 0 as success; unknown SKU is `NOT_FOUND`; SKU-8805 from Leeds is `SITE_ACCESS_DENIED` |
| 3.2 | `search_stock` | `single` carries quantity; `multiple` carries no quantity or bin and includes `next_step`; no match is `NOT_FOUND`; other-site products never appear |
| 3.3 | `list_dock_slots` | Status filter works; booked slots show carrier; unscheduled date is `NOT_FOUND` with `scheduled_dates`; a Leeds session never sees Reading rows |
| 3.4 | `list_exceptions` | Empty store returns an empty list as success; status filter works; site-filtered |

## Phase 4: Server skeleton and validation spike (spec 4.0, 6)

| ID | Task | Done when |
| --- | --- | --- |
| 4.1 | **Spike:** with the installed SDK version, send an invalid argument (`slot: "11:00"`) and see what the client receives. Decide: disable SDK input validation, or catch and re-raise. Write the finding in a short note for `REFLECTION.md` | A call with a bad enum returns our `INVALID_ARGUMENT` envelope with `field` and `example_call` |
| 4.2 | `server.py`: register the four read tools with schemas published from the Pydantic models, description text verbatim from spec 4.x, `readOnlyHint: true`, and the server `instructions` field | `list_tools` through an in-memory client shows four tools with enums and patterns |
| 4.3 | Test harness that drives the server through the MCP protocol (in-memory client session) | An invocation test for each read tool passes through the protocol, not direct calls |
| 4.4 | Register the server in Claude Code with a single `.mcp.json` entry and a Leeds site value; ask one question | Claude Code discovers the tools and answers "how much void fill have we got" |

## Phase 5: Confirmation (spec 7.1)

| ID | Task | Done when |
| --- | --- | --- |
| 5.1 | `confirm.py`: random single-use tokens bound to caller, tool and canonical arguments; 300 second TTL with injectable clock | Unit tests: valid token passes once; reuse, expiry, other tool, other arguments and other caller are rejected |
| 5.2 | Shared write-tool flow: validate fully, then preview without a token, or commit with a token after re-checking state | A failing call returns its business error at preview time and issues no token |

## Phase 6: Write tools (spec 4.5 to 4.10)

Each write-tool task includes tests for: preview changes nothing; commit changes state and a
later read sees it; the tool's business errors; cross-site refusal where an identifier is
involved; token misuse gives `CONFIRMATION_INVALID`.

| ID | Task | Done when |
| --- | --- | --- |
| 6.1 | `book_dock_slot` | Booking an available slot works; a booked slot gives `SLOT_ALREADY_BOOKED` with alternatives; unscheduled date is `NOT_FOUND` |
| 6.2 | `cancel_dock_booking` | Preview names the carrier; cancelling an available slot gives `SLOT_NOT_BOOKED`; the freed slot lists as available |
| 6.3 | `correct_stock` | Preview shows old, new and difference; wrong bin gives `NOT_FOUND` listing the bins that hold the SKU; other-site SKU gives `SITE_ACCESS_DENIED` |
| 6.4 | `move_stock` | Partial move leaves the remainder and creates the destination row; total unchanged; too many gives `INSUFFICIENT_STOCK` with `available` and `requested`; same bin is `INVALID_ARGUMENT`; other-site bin prefix is `SITE_ACCESS_DENIED` |
| 6.5 | `raise_exception` | Returns a server-generated `EX-` ID; category outside the enum is rejected; other-site SKU is denied |
| 6.6 | `close_exception` | Closing works with a note; second close gives `ALREADY_CLOSED`; unknown ID is `NOT_FOUND`; other-site ID is `SITE_ACCESS_DENIED` |
| 6.7 | Audit list | Each executed write adds one entry with before and after; previews and failures add none |

## Phase 7: Complete the server (spec 4.0)

| ID | Task | Done when |
| --- | --- | --- |
| 7.1 | Register the six write tools with `readOnlyHint: false`, `destructiveHint` on cancel, correct and close, and `CHANGES STATE.` description prefixes | `list_tools` shows ten tools, annotations correct |
| 7.2 | Contract test over `list_tools` | Asserts: ten tools; no tool has a `site` property; slot, status and category are enums; every schema forbids extra properties |
| 7.3 | **Commit point:** run the full suite, then commit everything as `04-implement` | `git show --stat` shows the implementation; the first four commits are in order |

## Phase 8: Test completion (plan section 7)

| ID | Task | Done when |
| --- | --- | --- |
| 8.1 | Site-scoping matrix, parametrised over the three sites | Every same-site call succeeds and every cross-site identifier is refused, in the same run |
| 8.2 | Error-shape sweep over all nine codes | Every code has `code`, `message`, `field`, `details`, `suggested_action`, with `example_call` where constructible |
| 8.3 | Schema-rejection suite | Bad SKU pattern, slot `"11:00"` and `"10am"`, bad category, zero and negative quantity, missing field and extra property (including `site`) all return `INVALID_ARGUMENT` with `field` |
| 8.4 | Full run saved | `evidence/pytest_output.txt` shows all tests passing |

## Phase 9: Host integration

| ID | Task | Done when |
| --- | --- | --- |
| 9.1 | Finalise `.mcp.json`: one server, one site per session; document how to switch site | Restarting with a different site value changes which site the agent can see |
| 9.2 | `.claude/settings.json`: pre-approve only the four read-only tools | Claude Code prompts before any write tool runs |
| 9.3 | `CLAUDE.md`: project workflow and safety rules | Present and short |
| 9.4 | Update `AGENT_INSTRUCTIONS.md` to ten tools, including `list_exceptions`, the two-step token flow, and the nine error codes (add `CONFIRMATION_INVALID` and `SLOT_NOT_BOOKED`) | No reference to a `confirmation: true` parameter or to seven codes remains |

## Phase 10: Runtime demonstration (plan section 8)

| ID | Task | Done when |
| --- | --- | --- |
| 10.1 | Leeds session: prompts 1 to 9 phrased the way Ops would phrase them | Transcript shows an unambiguous answer without a question, a clarification question for "pallet wrap", a cross-site refusal, the preview then commit flow, a booked-slot error, an invalid-slot correction, and the raise-list-close flow |
| 10.2 | Glasgow session: prompt 10, zero stock | Agent reports quantity zero, not "not found" |
| 10.3 | Save evidence | `evidence/agent_transcript.md`, `evidence/registration/`, `evidence/git_log.txt` exist |

## Phase 11: Documentation

| ID | Task | Done when |
| --- | --- | --- |
| 11.1 | Changes-from-request list taken from spec 3, each change with its reason and data evidence | Standalone file or README section |
| 11.2 | `REFLECTION.md`: the validation spike result, what the data forced, what was left out and why, any spec amendment | Every design claim names the data or requirement behind it |
| 11.3 | Declared-effort statement | Included in the submission |

## Phase 12: Final check

| ID | Task | Done when |
| --- | --- | --- |
| 12.1 | Walk `criteria_checklist.md` item by item and tick or fix each | No unchecked item |
| 12.2 | Answer the "challenge your own work" questions in writing, in particular: does lookup ever return one item when the data supports more, and does it ever ask when only one matches | Written answers ready for the submission-time questions |
| 12.3 | Run `git log --stat` and confirm four ordered commits, spec commit containing only `spec.md`, no source before `04-implement` | Output saved |