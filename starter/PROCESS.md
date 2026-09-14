# Required build process

This case grades **how** you built the toolkit as well as the toolkit itself. The
sequence below is checked against your git history.

## Four commits, in order

| Commit message | Contains |
|---|---|
| `01-spec` | `spec.md` only. **No source files.** Your tool interface design, decided before you build it. |
| `02-plan` | adds `plan.md` |
| `03-tasks` | adds `tasks.md` |
| `04-implement` | adds your implementation |

Further commits after `04-implement` are expected. What is graded is that the
first four exist in that order, and that **no source file appears before
`04-implement`**.

Submit the repository, or `git log --stat` covering all four commits with timestamps.

## Why the spec matters more than usual here

Tool design *is* the deliverable in this case. `spec.md` should contain your tool
list, each tool's name, its parameters and their types, its description as the
model will see it, and its error shape - decided before any code exists.

The requirements document you were given (`data/tool_specification.md`) is what
Ops asked for, in their words. It is not a design, and treating it as one is the
most common way this case goes wrong. Several of the tools they described should not be built the
way they described them. Work out which, and record the reasoning in `spec.md`.

A learner who implements the requirements literally will produce a working toolkit
that an agent uses badly.
