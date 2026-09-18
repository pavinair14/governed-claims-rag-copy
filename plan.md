# Warehouse Ops MCP Toolkit Implementation Plan

## 1. Objective

Build a safe, agent-friendly MCP toolkit for Kestrel warehouse operations across:

- `LEEDS-01`
- `READING-02`
- `GLASGOW-03`

The implementation will use the supplied warehouse data as a stub backend and expose the tool interface defined in `spec.md`.

Claude Code will be used as the real MCP-compatible agent host for the runtime demonstration.

The implementation will demonstrate:

- schema validation
- site scoping
- ambiguity handling
- confirmation for state-changing operations
- actionable errors
- agent instructions
- runtime tool selection
- clarification when the agent cannot safely determine the requested product

The case requires the interface to be designed before implementation and the Git history to demonstrate that sequence.

## 2. Technology

The implementation will use:

- Python 3.11
- MCP Python SDK
- Pydantic
- pytest
- pytest-asyncio
- supplied CSV and JSONL files as stub data

Agent runtime:

- Claude Code
- MCP server registration through Claude Code configuration

## 3. Implementation Approach

### Phase 1 — Prepare the project

Create the Python project structure and install the required dependencies.

Do not modify the committed `spec.md` during implementation unless a genuine design issue is discovered and documented appropriately.

### Phase 2 — Implement data access

Create a small data-access layer for:

- `stock_snapshot.csv`
- `dock_schedule.jsonl`

The data layer will provide the information required by the MCP tools without introducing a production warehouse-system integration.

### Phase 3 — Implement caller context and site scoping

Create trusted caller context containing:

- `caller_id`
- `assigned_site`

The assigned site will be controlled by the toolkit rather than accepted as a user-controlled authorization parameter.

Every site-specific operation will apply the caller's assigned-site restriction.

### Phase 4 — Implement MCP tools

Implement the nine tools defined in `spec.md`:

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

- required fields
- data types
- non-negative stock quantities
- positive movement quantities
- closed dock-status values
- closed exception-category values
- confirmation requirements

The MCP server will enforce critical rules rather than relying only on agent instructions.

### Phase 6 — Implement lookup behaviour

Implement two stock lookup paths:

- exact SKU lookup
- product-description search

Description searches will not automatically choose a best match when multiple products are plausible.

The search result will provide candidates so Claude can ask the user for clarification.

If there is one clear match, Claude can proceed without unnecessary clarification.

### Phase 7 — Implement actionable errors

Create a common error response structure containing:

- error code
- message
- affected field when applicable
- additional details
- suggested action

Errors should allow Claude to understand the failure and construct a corrected request.

### Phase 8 — Implement state changes

Implement:

- dock booking
- dock cancellation
- stock correction
- stock movement
- exception creation
- exception closure

Each state-changing operation will validate the requested state change before modifying the stub state.

### Phase 9 — Create Claude agent instructions

Create:

```text
AGENT_INSTRUCTIONS.md
```

The file will contain concise instructions for Claude Code covering:

- tool selection
- exact versus approximate stock lookup
- ambiguity handling
- confirmation before state changes
- site boundaries
- error handling
- avoiding invented warehouse facts

The instructions will guide Claude but will not replace MCP-server enforcement.

### Phase 10 — Test the toolkit

Create an asynchronous test suite using `pytest-asyncio`.

Tests will cover:

- normal tool invocation
- schema rejection
- ambiguous lookup behaviour
- unambiguous lookup behaviour
- site scoping
- valid same-site access
- cross-site rejection
- confirmation-required behaviour
- state-changing operations
- actionable error shape
- already-booked dock handling
- insufficient-stock handling
- invalid enum values

### Phase 11 — Register and exercise the MCP server with Claude Code

Register the MCP server with Claude Code.

Verify that Claude can discover the tools.

Run natural-language scenarios based on the way warehouse Ops staff would ask questions.

The runtime demonstration will include:

- exact SKU lookup
- unambiguous product search
- ambiguous product search
- clarification question
- dock availability request
- state-changing request without confirmation
- confirmation and successful state change
- cross-site access attempt
- invalid request and actionable error

### Phase 12 — Capture evidence

Capture:

- MCP registration configuration
- `AGENT_INSTRUCTIONS.md`
- runtime transcript
- tool selection evidence
- clarification behaviour
- confirmation behaviour
- site-scoping behaviour
- test output

Document the changes from the original Ops wish-list and the reasoning behind each change.

### Phase 13 — Final documentation

Create:

```text
REFLECTION.md
```

Include the declared-effort statement required by the case.

Review all documentation against the submission checklist.

## 4. Git Commit Sequence

The required initial sequence remains:

| Commit         | Content                                                |
| -------------- | ------------------------------------------------------ |
| `01-spec`      | `spec.md` only; no source files                        |
| `02-plan`      | Adds `plan.md`                                         |
| `03-tasks`     | Adds `tasks.md`                                        |
| `04-implement` | Adds implementation, including `AGENT_INSTRUCTIONS.md` |

No source files or implementation files will be committed before `04-implement`.

Further commits may be made after `04-implement` for:

- tests
- fixes
- Claude Code configuration
- documentation
- runtime evidence
- final cleanup

## 5. Definition of Done

The implementation is complete when:

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
