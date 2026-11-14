# Reflection: Warehouse Ops MCP Toolkit

Items in square brackets are for me to fill in before submitting.

## 1. What I built

A Python MCP server with **10 tools** (4 read-only, 6 state-changing) over the supplied stock
and dock data. Ops asked for 5. The site comes from server configuration and no tool takes a
site. Every write is a two-step preview and token. 291 automated tests pass
(`evidence/pytest_output.txt`), including tests that drive the server through the protocol
with a real client. I demonstrated it with VS Code and GitHub Copilot in Agent mode.

`CHANGES.md` has the full list of changes, each with its evidence. This document covers what
I learned and where the design is weak.

## 2. What the data forced

I read `stock_snapshot.csv` before designing the lookup, and it decided the interface.

- **12 of 16 SKUs have a same-site twin** that differs by one word or number (SKU-8801/8802
  clear vs black wrap, and five other pairs). A lookup that returns a best match would return
  the wrong product for 75% of the catalogue. So `lookup` became `get_stock` (exact SKU) and
  `search_stock` (returns every candidate).
- **Ambiguity depends on the site.** "Void fill" matches two products across the company but
  exactly one at Leeds (SKU-8811) and one at Glasgow (SKU-8810). "Pallet" matches four
  products at Leeds. A design that always asks fails the first case, and one that never asks
  fails the second, so the search decides after filtering by site.
- **Zero stock is real data.** SKU-8809 has quantity 0 while its sibling SKU-8808 has 150.
  Treating 0 as "not found" would make an agent quote 150 for the 600mm film.
- **Every booking is Northbound Freight, and Leeds and Reading have two each.** So bookings
  are identified by date and slot, never by carrier.
- **A SKU lives at exactly one site, and bin names carry a site prefix.** That made a
  cross-site refusal decidable, and showed that `to_bin` on a move is also a cross-site route.

## 3. Design decisions and why

- **Site scoping without a parameter.** A `site` argument has to be trusted or verified.
  A parameter that does not exist cannot be misused. The server reads the site from its
  environment and refuses to start without a valid one. A `site` argument is rejected.
  Tests run all 16 SKUs against each of the three sites in one session, so same-site access
  and cross-site refusal are proven together.
- **`SITE_ACCESS_DENIED`, not `NOT_FOUND`, for another site's identifier.** "Not found"
  would be untrue and would send the agent to check a correct code for typos. The denial
  reveals one fact, that the identifier exists elsewhere, and nothing else.
- **Confirmation on all six writes.** I considered a lighter tier for booking and raising,
  and chose one uniform rule because it is harder for an agent to get wrong. The cost is one
  extra step on a forklift terminal, which I accepted knowingly.
- **A preview that issues a token, not a `confirmation: true` flag.** A required boolean
  would make the preview unreachable and would let the agent type `true` without asking.
- **No reopen for closed exceptions.** Ops asked for close but not its reverse. I took the
  position that closing is final, say so in the preview, and answer a mistake by raising a
  new exception.

## 4. What I got wrong, and what testing taught me

- **The token was not tied to what the user saw.** While writing the cancel tests I saw that
  the token covered the arguments but not the situation. If another booking took the slot
  between preview and commit, the same arguments would have cancelled a booking nobody
  confirmed. A correction could have applied to a quantity that had since changed. I bound
  the token to the preview text, and both cases now have tests.
- **My own test expectations were wrong twice, and the code was right both times.** I
  expected `CONFIRMATION_INVALID` when a used correction token was replayed, and when a bogus
  token was sent for an already-closed exception. The server returned the real reason
  instead (nothing to correct, already closed), because business rules run before the token
  check. That is the better behaviour, since the agent gets the most specific explanation.
- **I checked the SDK instead of assuming.** The installed `mcp` is version 2.2.0, a major
  version newer than the one I knew. I read its signatures and sent a throwaway server four
  bad calls (an enum violation, an extra `site`, a missing field, and a valid one). All four
  reached my handler unchecked, so the SDK validates nothing here, and my Pydantic models are
  the only enforcement. That meant my own error shape survives, and it is why a test
  asserts that a `site` argument is rejected through the protocol and not only in the models.

## 5. What the live demos showed

I ran the demos in VS Code with Copilot in Agent mode. Copilot picked its own model, and it
changed between chats. The server's own log (`KESTREL_AUDIT_LOG`) is the reliable record,
because the chat view hid the preview call and made it look as if a commit had no preview.

| Prompt (as Ops might say it) | What happened |
| --- | --- |
| "how much void fill have we got" | One `search_stock` call, single match, answered directly with no question. |
| "how many rolls of pallet wrap" | Two candidates returned with no quantity; the agent asked clear or black; then `get_stock`. |
| "what's the stock on SKU-8805" (Leeds) | `SITE_ACCESS_DENIED`; the agent said it is not held at the site and quoted nothing. |
| Book the 10:00 slot | Preview, my confirmation, then the booking. |
| "what docks are free on 9 April" | `NOT_FOUND` with the scheduled dates; the agent reported 8 April is the only schedule. |
| "move 500 of SKU-8801" | The agent moved nothing at 500, asked what to do, offered the 240 available, then asked once more before committing. |
| Correct the black wrap count to 175 | Search, preview, my confirmation, commit; the server log shows all three steps. |
| Raise, list and close an exception | The agent found the ID itself, used my words, and warned that closing is permanent. |
| 600mm shrink film (Glasgow) | Quantity 0 reported as zero, not "not found". |
| SKU-8801 (Glasgow) | `SITE_ACCESS_DENIED`. |

The agent also recovered from a server error with no help from me: a search for "black pallet
wrap rolls" returned `NOT_FOUND`, and the agent retried with fewer words.

### The workspace can undermine the toolkit

With the repo open, the agent read `data/stock_snapshot.csv` and answered "240" for SKU-8801
in a **Glasgow** session, which is the leak Ops described. With an empty folder containing only
`.vscode/mcp.json`, the same prompt and the same model called `get_stock` and was refused. The
server enforced the boundary on every call it received, but it cannot stop a host that reads
the data file directly. In a real deployment the stock data would not sit in the agent's
workspace, so I treat the empty-folder run as the fair test of the toolkit and report the
other as a limit, not a pass.

### Problems the demos found, and the fixes

| Problem seen | Fix | Before and after |
| --- | --- | --- |
| The agent invented the correction reason ("Physical count correction") | `correct_stock` and `close_exception` descriptions say to use the user's words and ask if none were given | Before: screenshots. After: `log_1_correction.txt` shows my words, "recount after the delivery". |
| Two confirmation questions per raise or close | Descriptions say to preview first and ask once | `log_2_exceptions_before_fix.txt` vs `log_3_exceptions_after_fix.txt` |
| After a failed search the agent dropped "black" and asked which product | The `NOT_FOUND` suggestion says to drop generic words and keep colour and size | `log_2` vs `log_3` |

All three are changes to wording the agent reads, driven by what the agent actually did, and not
by how I expected it to behave.

## 6. Where the design is weak

- **The site is only as trustworthy as whatever launches the server.** The environment
  variable stands in for an authenticated terminal session. Anyone who can edit the
  registration can change the site.
- **The token proves the commit matches the preview, not that a human agreed.** The human
  decision rests on the agent showing the preview and on the host's own approval prompt.
  In the demos I answered every confirmation myself.
- **Free text is stored and shown back to agents.** Exception descriptions and notes written
  by one user are returned by `list_exceptions` to a later agent session. I did not test
  whether such text could carry instructions to the agent. I would treat that as the first
  thing to test next.
- **`SITE_ACCESS_DENIED` confirms that an identifier exists elsewhere**, and the shared
  exception counter lets a user infer a count of other sites' exceptions. No content leaks.
- **State is in memory.** Restarting the server resets it, and there is no real concurrency
  control beyond re-checking rules at commit time.
- **The agent paraphrases.** It added a capital and a full stop to my close note. It also
  once listed all six slot times as "available" after saying only three were free.
- **Only one date has a schedule**, and bins are validated by prefix, not against a real
  list of bins.

## 7. Answers to my own challenge questions

- **Read the stock file before designing lookup?** Yes (Section 2).
- **Does lookup ever return one item when the data supports more?** No. `search_stock`
  returns every match, and a test confirms "pallet" at Leeds returns four.
- **Does it demand disambiguation where there is one match?** No. A test types the full
  description of each of the 16 products at its own site and expects exactly one match each.
  Live, "void fill" at Leeds was answered with no question.
- **Irreversible or hard-to-unwind operations?** `correct_stock` (feeds month-end),
  `close_exception` (no reopen), and `cancel_dock_booking` (the carrier may be en route).
- **Tools that were really two or three?** `lookup` was two, `check_dock` three, and
  `stock_change` two.
- **Closed sets in the schema?** Slot, status and category are enums, and SKU and exception
  IDs have patterns. The server rejects what the schema forbids and returns our error shape.
- **Is site scoping enforceable?** Yes at the toolkit (no parameter, scoping in one place,
  refusal checked for all 16 SKUs from all three sites), with the limits in Section 6.
- **Can the agent fix a failed call from the error alone?** Yes. All nine codes are
  reachable through the protocol, each has `suggested_action`, and a test checks that every
  `example_call` is itself a valid call. Live, the agent recovered from `NOT_FOUND` unaided.
- **An operation whose reverse was not requested?** `close_exception`. I chose no reopen.

## 8. Declared effort

**Time:** roughly 5 to 7 days, covering reading the brief and data, spec, plan, tasks,
implementation, tests, live demos and documents.

**AI assistance:** I used Claude as an assistant throughout, working one step at a time in a
chat. It wrote most of the code, tests and documents, and reviewed drafts I wrote or pasted
[adjust: say which drafts, for example my first spec and plan]. I used VS Code with GitHub
Copilot (Agent mode) as the agent host for the demonstration.

**What I did myself:**
- Made the design decisions I was asked to make: keeping confirmation on all six
  state-changing tools, and returning `SITE_ACCESS_DENIED` for another site's identifier.
- Chose the tooling for my setup (`requirements.txt` with `pytest.ini`, VS Code with Copilot
  as the host).
- Ran every test and every live demo on my own machine, answered the confirmation prompts
  myself, and saved the logs and screenshots in `evidence/`.
- Found and fixed environment problems in my setup, including the duplicate server
  registration and the stale test-output file.

**What I did not do alone:** the code, the tests and the wording of the documents were
produced with AI help and then run and checked by me.
