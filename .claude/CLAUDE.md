# Warehouse Ops Project Rules

## Scope

This repository implements the Kestrel Warehouse Ops MCP toolkit described in `spec.md`. Treat `spec.md` as the interface contract and `data/tool_specification.md` as business input, not as an implementation design.

## Required workflow

- Read the supplied stock and dock data before changing lookup or state behavior.
- Keep read-only tools separate from state-changing tools.
- Preserve the nine-tool contract: `get_stock`, `search_stock`, `list_dock_slots`, `book_dock_slot`, `cancel_dock_booking`, `correct_stock`, `move_stock`, `raise_exception`, and `close_exception`.
- Before implementation is complete, register all nine tools in a real MCP server and exercise them through an MCP-compatible host.
- Keep tests asynchronous with `pytest-asyncio` where they invoke the MCP layer.
- Do not commit changes unless explicitly asked.

## Security and safety rules

- Site scope comes from trusted `CallerContext`; never add a user-controlled `site` authorization parameter.
- Enforce site filtering in the server and service layer, not only in agent instructions.
- Require schema-valid `confirmation: true` for every state-changing operation.
- Validate the complete proposed change before mutating state, and expose successful mutations to later reads in the same server session.
- Never guess an SKU, product variant, quantity, bin, slot, carrier, date, or exception ID.
- Return all plausible stock candidates when a description search is ambiguous. Ask for clarification instead of selecting a fuzzy best match.
- Treat zero quantity as a valid stock record.
- Use the common actionable error shape from `spec.md`; do not leak another site's stock, bins, carriers, or schedule details.

## Documentation and evidence

- Keep `spec.md`, `plan.md`, and `tasks.md` consistent with the implementation.
- Update `.claude/instructions/AGENT_INSTRUCTIONS.md` when model-facing tool behavior changes, but do not use it as a replacement for server validation.
- Preserve the required first-four commit sequence: `01-spec`, `02-plan`, `03-tasks`, `04-implement`. No source file may appear before `04-implement`.
- Capture MCP registration, tool discovery, clarification, confirmation, cross-site refusal, schema/error handling, and passing test output before submission.
- Add `REFLECTION.md` and the declared-effort statement required by the checklist.

## Validation

After changes, run the narrowest relevant test first, then the full `pytest` suite. Review `git diff` and `git log --stat` before submission.
