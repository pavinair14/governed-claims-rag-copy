# Warehouse Ops MCP Toolkit — Tasks

Task numbers follow the phases in `plan.md`. `§` references point to `spec.md`.
Tasks tagged **[test]** produce a passing pytest-asyncio test as their completion evidence.

## 1. Project setup

- [ ] 1.1 Create the repository layout from `plan.md` §3 (source only in `04-implement`).
- [ ] 1.2 Create a Python 3.11 environment; `pyproject.toml` with `mcp`, `pydantic`, `pytest`, `pytest-asyncio`.
- [ ] 1.3 Configure `pytest-asyncio` (`asyncio_mode = "auto"` or explicit markers).
- [ ] 1.4 Copy `stock_snapshot.csv` and `dock_schedule.jsonl` into `data/`; confirm the loader finds them (16 stock rows, 18 dock rows).

## 2. Errors and envelope (§7.2–7.4)

- [ ] 2.1 Define the closed error-code set: `INVALID_ARGUMENT`, `NOT_FOUND`, `SITE_ACCESS_DENIED`, `CONFIRMATION_REQUIRED`, `INVALID_CONFIRMATION`, `SLOT_ALREADY_BOOKED`, `INSUFFICIENT_STOCK`, `STALE_QUANTITY`, `ALREADY_CLOSED`.
- [ ] 2.2 Implement the error object: `code`, `message`, `field`, `details`, `suggested_action`, `example_call`.
- [ ] 2.3 Implement success/failure envelopes (`ok`, `site`, `data` / `error`; `isError` on failures).
- [ ] 2.4 `example_call` builder that uses `"<ask the user>"` for values only the user can supply.
- [ ] 2.5 **[test]** Every error code produces all required fields.

## 3. Session context and scope (§5)

- [ ] 3.1 Read `KESTREL_CALLER_ID` and `KESTREL_ASSIGNED_SITE` at startup; fail fast if missing or not in the closed set.
- [ ] 3.2 **[test]** Startup fails on missing/invalid site.
- [ ] 3.3 Implement the single `scope` helper: row filtering by session site, foreign-record detection, `site` assertion check.
- [ ] 3.4 `SITE_ACCESS_DENIED` builder that returns only the submitted value and the session site — no foreign description, quantity or bin.
- [ ] 3.5 Echo `site` in every success result.

## 4. Models and schemas (§7.5, §8)

- [ ] 4.1 **Spike:** with the installed MCP SDK, confirm how validation failures surface; pick the approach that lets the toolkit return its own `INVALID_ARGUMENT` object while still publishing the full JSON Schema.
- [ ] 4.2 Shared types: `SKU`, `BIN`, `EXID`, `DATE`, `SLOT` enum (six values), `Site` enum, `DockStatus` enum, `ExceptionCategory` enum (`damaged`, `missing`), `ExceptionStatusFilter` enum.
- [ ] 4.3 One Pydantic input model per tool with `extra="forbid"`, ranges (`quantity` ≥ 1; `counted_quantity` 0–100000), string lengths, and the common optional `site` field.
- [ ] 4.4 Map `ValidationError` → `INVALID_ARGUMENT` with `field` and `details.allowed_values`.
- [ ] 4.5 Special hints: SKU-like text passed to `search_stock` → point to `get_stock`; description-like text passed to `get_stock` → point to `search_stock`; `"8801"` → suggest `"SKU-8801"`.
- [ ] 4.6 **[test]** Schema rejection: bad SKU pattern, slot `"10am"`, category `"broken"`, quantity 0 and −5, missing required field, extra property (`site_id`), `status` value outside the enum.
- [ ] 4.7 **[test]** `list_tools` exposes enums, patterns and ranges in each `inputSchema`.

## 5. Store and ledger (§2, §6)

- [ ] 5.1 Load stock rows keyed by (SKU, bin) and dock slots keyed by (site, date, slot); keep loading independent of MCP.
- [ ] 5.2 Reset function for tests (fresh state per test).
- [ ] 5.3 Exception store starting empty; ID generator `EX-0001…`.
- [ ] 5.4 Append-only audit ledger (`audit_id`, caller, site, tool, arguments, before/after, UTC time).
- [ ] 5.5 Site bin zones derived from the snapshot (`A-`/`YARD-`, `B-`, `C-`).
- [ ] 5.6 Operating date pinned to `2026-04-08`, overridable by config for tests.

## 6. Search (§9)

- [ ] 6.1 Tokeniser: lower-case, split on whitespace/punctuation, keep `500mm`/`100x150` whole.
- [ ] 6.2 Matcher: alphabetic prefix (min 3 chars, plural `s` ignored); numeric exact or unit-less; AND across tokens.
- [ ] 6.3 Site filter applied **before** matching; zero-stock products never filtered.
- [ ] 6.4 Resolution: `unique` (with stock details) / `multiple` (identity only, no quantities, `next_step` text) / `NOT_FOUND`.
- [ ] 6.5 **[test]** Every row of the §9 outcome table, at the correct session site.
- [ ] 6.6 **[test]** `multiple` responses contain no `quantity`, `total_quantity` or `locations` keys.
- [ ] 6.7 **[test]** Unambiguous queries never return `multiple` (`void fill` at Leeds and Glasgow, `edge board`, `label`, `black pallet wrap`, `50mm corner protector`).

## 7. Read tools (§8.1–8.3, 8.9)

- [ ] 7.1 `get_stock`: exact SKU, total + per-bin locations, `in_stock`; zero quantity is success.
- [ ] 7.2 `search_stock` wired to §6.
- [ ] 7.3 `list_dock_slots`: `date` optional (default operating date, echoed), `status` enum default `all`, `counts`, `NOT_FOUND` with `details.available_dates`.
- [ ] 7.4 `list_exceptions`: `status` enum default `open`, optional `sku`, newest first, empty list is success.
- [ ] 7.5 **[test]** Each read tool succeeds for a valid same-site call, at all three sites.
- [ ] 7.6 **[test]** `get_stock("SKU-8809")` at Glasgow → success, quantity 0, `in_stock: false`.
- [ ] 7.7 **[test]** Read tools do not change state (state snapshot equal before/after).

## 8. Confirmation (§6)

- [ ] 8.1 Tier 1: missing/false `confirm` → `CONFIRMATION_REQUIRED` with `details.preview`; nothing changed.
- [ ] 8.2 Tier 2: token store — random, single-use, TTL 300 s, bound to caller + tool + canonical arguments.
- [ ] 8.3 Order of checks: schema → scope → existence/state → confirmation; **never issue a preview for a call that would fail**; re-validate at execution.
- [ ] 8.4 `INVALID_CONFIRMATION` for expired, reused, foreign-caller and changed-argument tokens, with instructions to restart.
- [ ] 8.5 **[test]** Tier 1 preview leaves state unchanged; `confirm=true` executes.
- [ ] 8.6 **[test]** Tier 2: no token → preview + token, state unchanged; correct token → executes; each invalid-token case → `INVALID_CONFIRMATION` and state unchanged.
- [ ] 8.7 **[test]** A failing call (e.g. booked slot, stale quantity) returns its own error, not a preview.

## 9. Write tools (§8.4–8.8, 8.10)

- [ ] 9.1 `book_dock_slot`: validate date exists, slot free; `SLOT_ALREADY_BOOKED` with `details.available_slots` and `example_call`; tier 1.
- [ ] 9.2 `cancel_dock_booking`: by date + slot; preview names the carrier; `NOT_FOUND` if the slot has no booking (message states actual status); slot returns to `available`; tier 2.
- [ ] 9.3 `correct_stock`: SKU, bin, `counted_quantity`, `expected_current_quantity`, `reason`; `STALE_QUANTITY` with `details.current_quantity`; bin must hold SKU (`details.bins_holding_sku`); ledger records before/after/reason; tier 2.
- [ ] 9.4 `move_stock`: SKU, `from_bin`, `to_bin`, `quantity`; `INSUFFICIENT_STOCK` with `details.available_in_bin`; same-bin → `INVALID_ARGUMENT`; `to_bin` outside site zones → `INVALID_ARGUMENT` with `details.valid_bin_prefixes`; total unchanged; empty source bin removed unless it is the SKU's only row; tier 1.
- [ ] 9.5 `raise_exception`: `category` enum, SKU required and site-checked, description 5–500; returns `exception_id`; tier 1.
- [ ] 9.6 `close_exception`: exception exists and belongs to site; resolution note required; `ALREADY_CLOSED` with `closed_at` and prior note; tier 2; no reopen.
- [ ] 9.7 Every executed write appends exactly one audit entry; previews and failures append none.
- [ ] 9.8 **[test]** Booking a booked slot; booking a free slot (Leeds 10:00) with `confirm`; cancelling Leeds 12:00 through the two-step path; cancel on an available slot → `NOT_FOUND`.
- [ ] 9.9 **[test]** Correction happy path (8802: 180 → 176); wrong `expected_current_quantity` → `STALE_QUANTITY`; ledger entry has before, after, reason.
- [ ] 9.10 **[test]** Move happy path (total preserved); insufficient stock; same bin; `to_bin` `B-03-7` from a Leeds session rejected.
- [ ] 9.11 **[test]** Raise → list → close → close again (`ALREADY_CLOSED`); invalid category rejected; SKU from another site → `SITE_ACCESS_DENIED`.

## 10. Site-scoping tests (§5)

- [ ] 10.1 **[test]** Parametrise over all three session sites: own-site SKU works on `get_stock`.
- [ ] 10.2 **[test]** Another site's SKU → `SITE_ACCESS_DENIED` on `get_stock`, `correct_stock`, `move_stock`, `raise_exception`.
- [ ] 10.3 **[test]** `site=<other site>` on **every** tool → `SITE_ACCESS_DENIED`; `site=<own site>` accepted.
- [ ] 10.4 **[test]** Denied responses, serialised, contain none of the foreign SKU's description, quantity or bin.
- [ ] 10.5 **[test]** Dock tools at Leeds never return Reading/Glasgow rows for the same slot time; results echo `site`.
- [ ] 10.6 **[test]** `search_stock` for another site's product → `NOT_FOUND`, no leakage.
- [ ] 10.7 **[test]** Exception records raised in one session are not returned or closable from a session at another site.
- [ ] 10.8 **[test]** Unknown `site` value (`"YORK-04"`) → `INVALID_ARGUMENT` listing the three valid sites.

## 11. MCP server (§7.1, §8)

- [ ] 11.1 stdio entry point registering all 10 tools with the verbatim model-facing descriptions from `spec.md` §8.
- [ ] 11.2 Annotations: reads `readOnlyHint: true`; writes `readOnlyHint: false`; `destructiveHint: true` for `correct_stock`, `cancel_dock_booking`, `close_exception`; `false` for the other three writes; `openWorldHint: false`.
- [ ] 11.3 Description prefixes `[READ-ONLY]` / `[CHANGES STATE — …]` match annotations.
- [ ] 11.4 Server-level `instructions`: identify-before-read, never guess, ask when `multiple`, confirm before writes, `SITE_ACCESS_DENIED` is final.
- [ ] 11.5 **[test]** Tool count is 10; annotations and prefixes are consistent for each tool.
- [ ] 11.6 **[test]** Error results carry `isError: true` and the structured object.
- [ ] 11.7 Run the complete suite; save passing output to `evidence/pytest_output.txt`.

## 12. Claude Code integration (§11)

- [ ] 12.1 `.mcp.json`: stdio command, args, and `env` with `KESTREL_CALLER_ID` and `KESTREL_ASSIGNED_SITE=LEEDS-01`.
- [ ] 12.2 `.claude/settings.json`: allow the four read-only tools; leave the six write tools to prompt.
- [ ] 12.3 `AGENT_INSTRUCTIONS.md`: update to the final tool set (add `list_exceptions`, `confirm` vs `confirmation_token`, `STALE_QUANTITY`, `INVALID_CONFIRMATION`, the optional `site` assertion, no-quantities-in-multiple).
- [ ] 12.4 `CLAUDE.md` importing `AGENT_INSTRUCTIONS.md`, used **only** for the second demo run.
- [ ] 12.5 Capture the `/mcp` output showing the server connected with all 10 tools listed.

## 13. Runtime demonstration (`plan.md` §7)

- [ ] 13.1 **Bare run** (no `CLAUDE.md`, no instructions): scenarios 1–17.
- [ ] 13.2 **Run with instructions**: same scenarios.
- [ ] 13.3 Scenario 3 — ambiguous "pallet wrap": agent asks which; does not pick.
- [ ] 13.4 Scenario 2 — "void fill": agent answers directly with no clarification.
- [ ] 13.5 Scenarios 6, 8, 9 — agent shows the preview and waits for an explicit yes; no write before it.
- [ ] 13.6 Scenario 12/13 — cross-site refused by the toolkit; agent quotes no other-site figures.
- [ ] 13.7 Scenario 14 is completed through to a raised exception so scenario 15 has a ticket to close.
- [ ] 13.8 Scenarios 16–17 — invalid enum corrected from the error; zero-stock reported as success.
- [ ] 13.9 Any behaviour seen only in run 2 → fix in descriptions/results and re-run bare.
- [ ] 13.10 Save both transcripts and the registration config under `evidence/`.

## 14. Documentation and evidence

- [ ] 14.1 List of changes from the Ops request with reasoning (from `spec.md` §3), as a standalone section or file for submission.
- [ ] 14.2 Document why critical rules live in the server (schemas, scope, tokens) rather than only in instructions.
- [ ] 14.3 Write `REFLECTION.md`: what changed and why, what the data forced, what would fail without the changes, what was not built, open questions for Ops.
- [ ] 14.4 Add the declared-effort statement.
- [ ] 14.5 Prepare short answers for submission-time questions: the 12/16 same-site-sibling figure; why `void fill` is unique at two sites; which three tools are irreversible and why; why `site` is an assertion; why quantities are withheld from `multiple`; why there is no reopen.
- [ ] 14.6 Review the repository against `criteria_checklist.md`, item by item.

## 15. Git history

- [ ] 15.1 Finish `spec.md`, `plan.md`, `tasks.md` before any commit.
- [ ] 15.2 Initialise the repo; commit only `spec.md` as `01-spec`.
- [ ] 15.3 Verify `git show --stat 01-spec` lists only `spec.md` and no source files exist.
- [ ] 15.4 Commit only `plan.md` as `02-plan`.
- [ ] 15.5 Commit only `tasks.md` as `03-tasks`.
- [ ] 15.6 Commit implementation, data, tests, config and `AGENT_INSTRUCTIONS.md` as `04-implement`.
- [ ] 15.7 Follow-up commits (fixes, evidence, `REFLECTION.md`, any documented spec amendment) come after `04-implement`.
- [ ] 15.8 Verify order and timestamps: `git log --reverse --stat --format="%h %ad %s"`; save to `evidence/`.

## Final definition of done

## Phase 10 — Claude Agent Instructions

- [ ] Create `AGENT_INSTRUCTIONS.md`.
- [ ] Document when Claude should use `get_stock`.
- [ ] Document when Claude should use `search_stock`.
- [ ] Document ambiguous-search behaviour.
- [ ] Document that Claude must not guess warehouse facts.
- [ ] Document confirmation requirements for state-changing tools.
- [ ] Document site-boundary behaviour.
- [ ] Document how Claude should respond to actionable errors.
- [ ] Document that MCP-server enforcement remains the security boundary.
- [ ] Keep instructions concise and focused on tool usage.

## Phase 11 — Automated Tests

- [ ] Configure `pytest-asyncio`.
- [ ] Test normal tool invocation.
- [ ] Test exact stock lookup.
- [ ] Test unambiguous stock search.
- [ ] Test ambiguous stock search.
- [ ] Test zero-quantity stock.
- [ ] Test dock availability lookup.
- [ ] Test booking confirmation path.
- [ ] Test booking without confirmation.
- [ ] Test already-booked slot.
- [ ] Test stock correction confirmation path.
- [ ] Test stock movement validation.
- [ ] Test insufficient stock.
- [ ] Test exception creation.
- [ ] Test exception closure.
- [ ] Test schema rejection.
- [ ] Test invalid enum values.
- [ ] Test same-site access.
- [ ] Test cross-site access denial.
- [ ] Test common error response shape.
- [ ] Run the complete test suite and capture the passing output.

## Phase 12 — Claude Code Runtime Demonstration

- [ ] Configure Claude Code as the MCP agent host.
- [ ] Register the MCP server.
- [ ] Verify that Claude can discover all tools.
- [ ] Run an exact stock lookup using an Ops-style question.
- [ ] Run an unambiguous product-name lookup.
- [ ] Run an ambiguous product-name lookup.
- [ ] Verify that Claude asks a clarification question instead of guessing.
- [ ] Run a dock availability request.
- [ ] Run a state-changing request without confirmation.
- [ ] Verify that the operation is not executed without confirmation.
- [ ] Confirm the operation.
- [ ] Verify the resulting state change.
- [ ] Run a cross-site request.
- [ ] Verify that access is denied by the toolkit.
- [ ] Run an invalid request.
- [ ] Verify that Claude receives an actionable error.

## Phase 13 — Documentation and Evidence

- [ ] Document the changes made from the original Ops wish-list.
- [ ] Document the reason for splitting the requested tools.
- [ ] Document the ambiguity-handling approach.
- [ ] Document the confirmation approach.
- [ ] Document the site-scoping approach.
- [ ] Document the actionable error approach.
- [ ] Document the role of `AGENT_INSTRUCTIONS.md`.
- [ ] Explain why critical rules are enforced in the MCP server rather than only in agent instructions.
- [ ] Save the Claude Code MCP registration configuration.
- [ ] Save the runtime transcript.
- [ ] Save the passing test output.
- [ ] Create `REFLECTION.md`.
- [ ] Add the declared-effort statement.
- [ ] Review the repository against the submission checklist.

## Phase 14 — Git History

- [ ] Commit `spec.md` as `01-spec`.
- [ ] Verify that `01-spec` contains no source files.
- [ ] Commit `plan.md` as `02-plan`.
- [ ] Commit `tasks.md` as `03-tasks`.
- [ ] Commit the implementation as `04-implement`.
- [ ] Add `AGENT_INSTRUCTIONS.md` as part of the implementation.
- [ ] Verify that no source file appears before `04-implement`.
- [ ] Make required follow-up commits after `04-implement`.
- [ ] Verify the first four commits are in the required order.
- [ ] Verify commit timestamps are distinct and increasing.
- [ ] Verify `git log --stat` provides evidence of the required sequence.

## Final Definition of Done

- [ ] `spec.md` contains the complete tool interface design.
- [ ] `plan.md` is committed separately as `02-plan`.
- [ ] `tasks.md` is committed separately as `03-tasks`.
- [ ] MCP server is implemented.
- [ ] All nine specified tools are available.
- [ ] Input schemas are enforced.
- [ ] Closed-set values use enums.
- [ ] Site scoping is enforced inside the toolkit.
- [ ] Ambiguous searches do not guess.
- [ ] Unambiguous searches do not require unnecessary clarification.
- [ ] State-changing operations require confirmation.
- [ ] Errors are structured and actionable.
- [ ] `AGENT_INSTRUCTIONS.md` is implemented.
- [ ] Claude Code can discover and use the MCP server.
- [ ] Claude demonstrates appropriate tool selection.
- [ ] Claude asks for clarification when required.
- [ ] Claude does not execute state changes without confirmation.
- [ ] Cross-site access is rejected by the toolkit.
- [ ] `pytest-asyncio` tests pass.
- [ ] Runtime demonstration is complete.
- [ ] Required documentation and evidence are included.
- [ ] Required Git commit sequence is preserved.

## Phase 15 — Contract Audit Before Submission

- [ ] Verify `spec.md` is complete and no tool definition ends mid-section.
- [ ] Verify each tool schema uses typed fields, `additionalProperties: false`, and enums or constants for closed values.
- [ ] Verify write schemas require `confirmation: true`; verify the server checks confirmation again.
- [ ] Verify public tool inputs do not include `site`; construct trusted `CallerContext` at the host/server boundary.
- [ ] Verify every mutation is visible to a subsequent read in the same server session.
- [ ] Verify exception IDs are generated and exception ownership/state are persisted and enforced.
- [ ] Verify `SKU-8809` returns a valid zero-quantity record and broad pallet-wrap search returns both Leeds candidates.
- [ ] Verify the MCP host discovers all nine tools and the saved transcript includes clarification, confirmation, same-site access, cross-site refusal, and actionable error recovery.
- [ ] Verify `.claude/CLAUDE.md` and `.claude/instructions/AGENT_INSTRUCTIONS.md` are present and agree with `spec.md`.
- [ ] Verify `git log --stat` shows the required first four commits in order, with no source file before `04-implement`.
