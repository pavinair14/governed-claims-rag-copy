# Submission Checklist — L2_Case04_Warehouse_Ops_MCP_Toolkit

## The process requirement — read this first

- [ ] Four commits in order: `01-spec` (containing `spec.md` and **no source files**), `02-plan`, `03-tasks`, `04-implement`.
- [ ] `spec.md` contains the **actual tool interface design** — names, parameters with types, model-facing descriptions, error shape — not a restatement of what Ops asked for.
- [ ] No source file appears before `04-implement`. Timestamps distinct and increasing.

## Deliverables

- [ ] Working MCP server, registered in a real agent host, with a transcript of an agent selecting tools at runtime.
- [ ] A transcript showing the agent asking a clarifying question rather than guessing, where the data makes guessing unsafe.
- [ ] Your list of changes from the requested design, each with its reasoning.
- [ ] Schema-constrained parameters, with closed value sets expressed in the schema.
- [ ] State-changing tools distinguishable from read-only ones in the interface, and confirmation before anything irreversible.
- [ ] Site scoping enforced in the toolkit, not delegated to the agent or to a trusted parameter.
- [ ] Actionable error objects the model can self-correct from.
- [ ] Passing `pytest-asyncio` output covering invocation, schema rejection, site scoping, confirmation, and error shape.
- [ ] `REFLECTION.md` and a declared-effort statement.

## Evidence standard

Every design claim names the data or requirement that drove it. "I split the lookup
tool for clarity" scores nothing. "SKU-8801 and SKU-8802 differ by one word, as do
six other pairs in the stock file, so a single fuzzy lookup returning a best match
would confidently return the wrong item — I split it and made search return all
candidates" scores.

## Before you submit — challenge your own work

- [ ] **Did I read `stock_snapshot.csv` before designing the lookup?** Look at the descriptions side by side. What can a name-based lookup honestly promise given what is in there?
- [ ] Does my lookup ever return one item when the data supports more than one plausible match? What does the agent see in that case?
- [ ] Conversely — does my design demand disambiguation even where there is genuinely only one match? Both failures matter.
- [ ] Which of the requested operations are irreversible, or feed something that is hard to unwind? Ops mentioned one in passing without drawing the conclusion.
- [ ] Did Ops describe any single tool that is really two or three? What happens when a model has to choose between reading and writing through one name?
- [ ] Which parameters have a closed set of valid values? Are they enums in my schema, or prose I validate afterwards?
- [ ] Is my site scoping enforceable, or does it trust a parameter the caller supplies?
- [ ] If a tool call fails, could the agent fix the call from my error alone, without a human?
- [ ] Did Ops ask for an operation whose reverse they did not ask for? Have I taken a position?

## How this will be assessed

Your toolkit is exercised by an agent, not by direct function calls, using questions
phrased the way Ops phrase them. Probes cover ambiguous lookups, an unambiguous
lookup (a design that always demands disambiguation fails this), out-of-stock,
booking an already-booked slot, a ledger-affecting write, cross-site access, and a
deliberately invalid argument.

Cross-site refusal is always tested alongside same-site access. A toolkit that
blocks everything fails as surely as one that blocks nothing.

The process check is graded first. A missing or out-of-order history caps
*Spec-Driven Development* at Not Yet whatever the documents say.

You will also answer several questions about your own submission at submission time.
