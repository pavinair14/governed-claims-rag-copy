# Warehouse Ops MCP Toolkit Tasks

## Phase 1 — Project Setup

- [ ] Create the Python project structure.
- [ ] Create the Python 3.11 environment.
- [ ] Add MCP Python SDK dependency.
- [ ] Add Pydantic dependency.
- [ ] Add pytest and pytest-asyncio dependencies.
- [ ] Add a dependency/configuration file for the project.
- [ ] Confirm the supplied data files are available to the application.

## Phase 2 — Data Layer

- [ ] Implement loading of `stock_snapshot.csv`.
- [ ] Implement loading of `dock_schedule.jsonl`.
- [ ] Create functions for retrieving stock records.
- [ ] Create functions for searching stock descriptions.
- [ ] Create functions for reading dock slots.
- [ ] Add an in-memory representation for state changes where required.
- [ ] Keep the data layer independent from MCP tool definitions.

## Phase 3 — Caller Context and Site Scoping

- [ ] Define the caller context with `caller_id` and `assigned_site`.
- [ ] Restrict valid sites to `LEEDS-01`, `READING-02`, and `GLASGOW-03`.
- [ ] Implement server-side site filtering.
- [ ] Prevent a user-supplied site value from bypassing site authorization.
- [ ] Return `SITE_ACCESS_DENIED` for cross-site requests.
- [ ] Verify that valid same-site requests continue to work.

## Phase 4 — Stock Tools

### `get_stock`

- [ ] Define the `sku` parameter schema.
- [ ] Implement exact SKU lookup.
- [ ] Restrict lookup to the caller's assigned site.
- [ ] Return valid zero-quantity records.
- [ ] Return `NOT_FOUND` for an unknown SKU.

### `search_stock`

- [ ] Define the `query` parameter schema.
- [ ] Implement product-description search.
- [ ] Restrict search to the caller's assigned site.
- [ ] Return all plausible candidates for ambiguous searches.
- [ ] Return one result when there is one clear match.
- [ ] Return `NOT_FOUND` when no candidate exists.
- [ ] Ensure the tool does not modify stock.

## Phase 5 — Dock Tools

### `list_dock_slots`

- [ ] Define the `date` parameter.
- [ ] Define the `status` enum.
- [ ] Implement `available`, `booked`, and `all` filtering.
- [ ] Restrict results to the caller's assigned site.
- [ ] Keep the operation read-only.

### `book_dock_slot`

- [ ] Define the date, slot, carrier, and confirmation parameters.
- [ ] Validate that the requested slot exists.
- [ ] Validate that the slot is available.
- [ ] Require explicit confirmation.
- [ ] Return `CONFIRMATION_REQUIRED` when confirmation is missing.
- [ ] Return `SLOT_ALREADY_BOOKED` when the slot is already booked.
- [ ] Update the stub schedule only after successful validation and confirmation.

### `cancel_dock_booking`

- [ ] Define the date, slot, and confirmation parameters.
- [ ] Validate that the booking exists.
- [ ] Require explicit confirmation.
- [ ] Return `CONFIRMATION_REQUIRED` when confirmation is missing.
- [ ] Cancel the booking only after successful validation and confirmation.
- [ ] Make the cancelled slot available again.

## Phase 6 — Stock Change Tools

### `correct_stock`

- [ ] Define the SKU parameter.
- [ ] Define `corrected_quantity` as a non-negative integer.
- [ ] Require a correction reason.
- [ ] Require explicit confirmation.
- [ ] Validate that the SKU belongs to the caller's assigned site.
- [ ] Return `CONFIRMATION_REQUIRED` before an unconfirmed change.
- [ ] Prevent negative quantities.
- [ ] Apply the correction only after confirmation.

### `move_stock`

- [ ] Define SKU, source bin, destination bin, quantity, and confirmation parameters.
- [ ] Require a positive movement quantity.
- [ ] Validate the source bin.
- [ ] Validate that source and destination bins differ.
- [ ] Validate that enough stock is available.
- [ ] Require explicit confirmation.
- [ ] Return `INSUFFICIENT_STOCK` when the requested quantity is too high.
- [ ] Apply the movement only after confirmation.

## Phase 7 — Exception Tools

### `raise_exception`

- [ ] Define the exception category enum.
- [ ] Allow only `damaged` and `missing`.
- [ ] Require a description.
- [ ] Allow an optional related SKU.
- [ ] Validate the SKU against the caller's assigned site when supplied.
- [ ] Require explicit confirmation.
- [ ] Associate the exception with the caller's assigned site.

### `close_exception`

- [ ] Define the exception ID parameter.
- [ ] Require a resolution note.
- [ ] Require explicit confirmation.
- [ ] Validate that the exception exists.
- [ ] Validate that the exception belongs to the caller's assigned site.
- [ ] Prevent an already-closed exception from being closed again.
- [ ] Return `ALREADY_CLOSED` when appropriate.

## Phase 8 — Error Handling

- [ ] Define the common error response structure.
- [ ] Implement machine-readable error codes.
- [ ] Include a clear human/model-readable message.
- [ ] Include the relevant field when applicable.
- [ ] Include useful details where required.
- [ ] Include a suggested corrective action.
- [ ] Ensure errors do not expose data from another site.
- [ ] Test invalid arguments.
- [ ] Test `NOT_FOUND`.
- [ ] Test `SITE_ACCESS_DENIED`.
- [ ] Test `CONFIRMATION_REQUIRED`.
- [ ] Test `SLOT_ALREADY_BOOKED`.
- [ ] Test `INSUFFICIENT_STOCK`.
- [ ] Test `ALREADY_CLOSED`.

## Phase 9 — MCP Server

- [ ] Create the MCP server entry point.
- [ ] Register all tools defined in `spec.md`.
- [ ] Add model-facing tool descriptions.
- [ ] Add typed input schemas.
- [ ] Connect each tool to the data/service layer.
- [ ] Ensure read-only tools do not perform state changes.
- [ ] Ensure state-changing tools enforce confirmation.
- [ ] Ensure all tools enforce caller site scope.

## Phase 10 — Automated Tests

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

## Phase 11 — Agent Runtime Demonstration

- [ ] Choose a real MCP-compatible agent host.
- [ ] Register the MCP server.
- [ ] Verify that the agent can discover the tools.
- [ ] Run an exact stock lookup using an Ops-style question.
- [ ] Run an unambiguous product-name lookup.
- [ ] Run an ambiguous product-name lookup.
- [ ] Verify that the agent asks a clarification question instead of guessing.
- [ ] Run a dock availability request.
- [ ] Run a state-changing request without confirmation.
- [ ] Verify that confirmation is requested.
- [ ] Confirm the operation and verify the state change.
- [ ] Run a cross-site request.
- [ ] Verify that access is denied by the toolkit.
- [ ] Run an invalid request.
- [ ] Verify that the agent receives an actionable error.

## Phase 12 — Documentation and Evidence

- [ ] Document the changes made from the original Ops wish-list.
- [ ] Document the reason for splitting the requested tools.
- [ ] Document the ambiguity-handling approach.
- [ ] Document the confirmation approach.
- [ ] Document the site-scoping approach.
- [ ] Document the actionable error approach.
- [ ] Save the MCP registration configuration.
- [ ] Save the runtime transcript.
- [ ] Save the passing test output.
- [ ] Create `REFLECTION.md`.
- [ ] Add the declared-effort statement.
- [ ] Review the repository against the submission checklist.

## Phase 13 — Git History

- [ ] Commit `spec.md` as `01-spec`.
- [ ] Verify that `01-spec` contains no source files.
- [ ] Commit `plan.md` as `02-plan`.
- [ ] Commit `tasks.md` as `03-tasks`.
- [ ] Commit the implementation as `04-implement`.
- [ ] Verify that no source file appears before `04-implement`.
- [ ] Make any required follow-up commits after `04-implement`.
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
- [ ] `pytest-asyncio` tests pass.
- [ ] Runtime agent demonstration is complete.
- [ ] Clarification behaviour is demonstrated.
- [ ] Required documentation and evidence are included.
- [ ] Required Git commit sequence is preserved.
