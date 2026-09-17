# Warehouse Ops MCP Toolkit Implementation Plan

## 1. Objective

Build a safe, agent-friendly MCP toolkit for Kestrel warehouse operations across:

* `LEEDS-01`
* `READING-02`
* `GLASGOW-03`

The implementation will use the supplied warehouse data as a stub backend and expose the tool interface defined in `spec.md`.

The main focus is to demonstrate safe tool design for an AI agent, including schema validation, site scoping, ambiguity handling, confirmation for state-changing operations, actionable errors, testing, and runtime agent usage.

## 2. Technology

The implementation will use:

* Python 3.11
* MCP Python SDK
* Pydantic for parameter validation and schemas
* `pytest`
* `pytest-asyncio`
* Supplied CSV and JSONL files as the stub data source

A real agent host such as Claude Code, VS Code, or an equivalent MCP-compatible host will be used for the runtime demonstration.

## 3. Implementation Approach

### Phase 1 — Prepare the project

Create the Python project structure and install the required dependencies.

The implementation will not modify the committed `spec.md`.

### Phase 2 — Implement data access

Create a small data-access layer for:

* `stock_snapshot.csv`
* `dock_schedule.jsonl`

The data layer will provide the information required by the MCP tools without introducing a production warehouse-system integration.

### Phase 3 — Implement site context

Create trusted caller context containing:

* `caller_id`
* `assigned_site`

The assigned site will be controlled by the server/toolkit rather than accepted as an authorization parameter from the user or agent.

Every tool that accesses warehouse data will apply the caller's assigned-site restriction.

### Phase 4 — Implement MCP tools

Implement the tools defined in `spec.md`:

1. `get_stock`
2. `search_stock`
3. `list_dock_slots`
4. `book_dock_slot`
5. `cancel_dock_booking`
6. `correct_stock`
7. `move_stock`
8. `raise_exception`
9. `close_exception`

Read-only and state-changing tools will remain separate.

### Phase 5 — Implement validation and safety rules

Use Pydantic/MCP schemas to enforce valid inputs.

Validation will cover:

* required fields
* valid data types
* non-negative stock quantities
* positive movement quantities
* valid dock statuses
* valid exception categories
* confirmation requirements

State-changing operations will not execute unless explicit confirmation is supplied.

### Phase 6 — Implement lookup behaviour

Implement two different stock lookup paths:

* exact SKU lookup
* product-description search

Description searches will not automatically select a best match when multiple products are plausible.

The search result will provide candidates so the agent can ask the user for clarification.

If there is one clear match, the agent can proceed without unnecessary clarification.

### Phase 7 — Implement actionable errors

Create a common error response structure containing:

* error code
* message
* affected field when applicable
* additional details
* suggested action

Errors will allow the agent to understand what went wrong and determine how to correct the request.

### Phase 8 — Implement state changes

Implement the state-changing operations for:

* dock booking
* dock cancellation
* stock correction
* stock movement
* exception creation
* exception closure

Each operation will validate the requested state change before modifying the stub data.

### Phase 9 — Test the toolkit

Create an asynchronous test suite using `pytest-asyncio`.

Tests will cover:

* normal tool invocation
* schema rejection
* ambiguous lookup behaviour
* unambiguous lookup behaviour
* site scoping
* valid same-site access
* cross-site rejection
* confirmation-required behaviour
* state-changing operations
* actionable error shape
* already-booked dock handling
* insufficient-stock handling
* invalid enum values

### Phase 10 — Register and exercise the MCP server

Register the MCP server with a real agent host.

Run agent-driven scenarios using questions phrased like warehouse staff would ask them.

The runtime demonstration will include:

* a stock lookup
* a product-name search
* an ambiguous lookup requiring clarification
* a dock availability request
* a state-changing operation requiring confirmation
* a cross-site access attempt
* an invalid request that produces an actionable error

### Phase 11 — Capture evidence

Capture:

* MCP server registration configuration
* runtime transcript
* test output
* tool selection by the agent
* clarification behaviour
* confirmation behaviour
* site-scoping behaviour

The repository will also document the changes made from the original Ops wish-list and the reasons for those changes.

## 4. Git Commit Sequence

The required initial commit sequence will be:

| Commit         | Content                         |
| -------------- | ------------------------------- |
| `01-spec`      | `spec.md` only; no source files |
| `02-plan`      | Adds `plan.md`                  |
| `03-tasks`     | Adds `tasks.md`                 |
| `04-implement` | Adds the implementation         |

No source files will be committed before `04-implement`.

Additional commits may be made after `04-implement` for testing, fixes, runtime configuration, documentation, and final evidence.

## 5. Definition of Done

The implementation is complete when:

* All tools in `spec.md` are implemented.
* MCP schemas reject invalid inputs.
* Read-only and state-changing tools are clearly separated.
* State-changing operations require confirmation.
* Site access is enforced inside the toolkit.
* Ambiguous stock searches return candidates instead of guessing.
* Unambiguous searches can return a single result.
* Errors use the defined actionable structure.
* Tests pass using `pytest-asyncio`.
* The MCP server is registered with a real agent host.
* Runtime evidence shows the agent selecting tools.
* Runtime evidence shows the agent asking a clarification question when appropriate.
* The repository contains the required documentation and evidence.
