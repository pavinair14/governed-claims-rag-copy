# Changes from the requested design

Ops asked for 5 tools. The toolkit has **10**: 4 read-only, 6 state-changing. This
document lists every change from `data/tool_specification.md`, and each change made
afterwards while building and demonstrating the toolkit, with the evidence behind it.

Evidence files are in `evidence/`: `pytest_output.txt` (291 passed) and four server logs
(`log_1_correction.txt`, `log_2_exceptions_before_fix.txt`,
`log_3_exceptions_after_fix.txt`, `log_4_glasgow_clean_folder.txt`).

---

## Part A: changes from Ops' request

| # | Ops asked for | Built | Why (data or requirement) |
| --- | --- | --- | --- |
| 1 | `lookup` (SKU or rough name, one tool) | `get_stock` (exact SKU) and `search_stock` (description) | 12 of 16 SKUs have a same-site twin that differs by one word or number (SKU-8801/8802 clear vs black wrap, and five other pairs). A single fuzzy lookup returning a best match would return the wrong product for 75% of the catalogue. |
| 2 | "where it is and how many" from a name | `search_stock` returns all candidates, and withholds quantities and bins unless exactly one product matches | If ambiguous candidates carried quantities, an agent could add 8801 and 8802 into one confident wrong figure. Identify first, then read with `get_stock`. A single match answers directly, so the design does not demand disambiguation where the data has one answer (for example "void fill" at Leeds is only SKU-8811). |
| 3 | `check_dock` (view, book, cancel) | `list_dock_slots` (read), `book_dock_slot` and `cancel_dock_booking` (write) | One name for reading and writing lets the model change state while "checking". Book and cancel also differ in reversibility. |
| 4 | `stock_change` ("the same kind of thing really") | `correct_stock` and `move_stock` | They are different. A correction changes the total and feeds the month-end count, which Ops said must be right. A move keeps the total and is undone by a reverse move. They have different parameters and failure modes. |
| 5 | `raise_exception` (category, few words, SKU) | `raise_exception` with `category` as an enum (`damaged` or `missing`) and `sku` required | Ops named two categories and three fields. A ticket with no SKU cannot be acted on. |
| 6 | `close_exception` | `close_exception`, terminal, with no reopen tool | Ops asked for close but not its reverse. Position: closing is final and the preview says so. A wrongly closed ticket is answered by raising a new one. |
| 7 | (not requested) | `list_exceptions` (read) | `close_exception` needs an ID. Without a listing tool the agent has to invent one or ask a gloved user to type it, against Ops' "don't make us type codes". |
| 8 | "book one, cancel one" | Bookings identified by `date` and `slot`, never by carrier | Every booking is Northbound Freight, and Leeds and Reading have two each, so "cancel Northbound's booking" is ambiguous at two of three sites. The cancel preview names the carrier. |
| 9 | "someone at Leeds could see Reading's numbers" | No `site` parameter on any tool. The site comes from server configuration (`KESTREL_ASSIGNED_SITE`), and the server refuses to start without a valid one | A site parameter has to be trusted or verified. A parameter that does not exist cannot be misused. A `site` argument is rejected as `INVALID_ARGUMENT`. |
| 10 | "tell us in a way that makes sense" (not `ERR_4001`) | One error object: `code`, `message`, `field`, `details`, `suggested_action`, and `example_call` where one can be built | Nine codes, all reachable through the protocol. Every `example_call` is checked by test to be a valid call. |
| 11 | "everything fast" | Two-step confirmation on all six write tools: a preview call changes nothing and returns a token, and a second call with the token commits | Corrections feed the month-end count, closing is final, and cancelling can hit a carrier already en route. One uniform rule is harder for an agent to get wrong than a per-tool list. The cost is one extra step on a forklift terminal, accepted deliberately. |
| 12 | cross-site identifier returns "not found" or a denial | `SITE_ACCESS_DENIED` for a SKU, bin prefix or exception ID that belongs to another site, with no data from that site in the message | "Not found" would be false and would send the agent down the wrong recovery path. The denial reveals only that the identifier exists elsewhere. Accepted cost: that one fact. |

---

## Part B: changes made while building and demonstrating

These are not in the committed `spec.md`. Each one has the evidence that drove it.

| # | Change | Evidence |
| --- | --- | --- |
| B1 | The confirmation token is bound to the preview text, not only to the arguments | Writing the cancel tests showed a gap. If another booking took the slot between preview and commit, the same arguments would cancel a booking nobody confirmed. A correction would have had the same problem with a changed quantity. Tests cover both. |
| B2 | Business rules run before the token check, on the preview and again at commit | Two of my test expectations were wrong because of it (a replayed correction token, and a bogus token sent for an already-closed exception), and both times the code was right: a replayed token returns the real reason (already booked, already closed, nothing to correct) and not a vague token error. |
| B3 | `correct_stock` refuses a correction equal to the recorded quantity (`INVALID_ARGUMENT`) | Otherwise a no-op writes a meaningless entry into the audit trail of a ledger-affecting tool. |
| B4 | `move_stock`: a full move removes the source row, any own-site bin is a valid destination, and the preview says when the destination does not currently hold the SKU | A partial move splits a SKU across two bins. Flagging an unfamiliar destination catches a bin typo before it creates stock where nobody looks. |
| B5 | `correct_stock` and `close_exception` descriptions tell the agent to use the user's own words for the reason or note, and to ask if they have not given one | Live runs before the change (kept as screenshots, because the server log was cleared between runs): the agent wrote the reason "Physical count correction", and in a later run "Physical count", when the user had given none. After the change the agent asked, and `log_1_correction.txt` shows the user's words, "recount after the delivery", in both the preview and the commit. |
| B6 | `raise_exception`, `close_exception` and `move_stock` descriptions say to preview first, ask once, then commit | `log_2` run: two confirmation questions per action in the chat, with one preview and one commit in the log. After the change (`log_3`) one question, asked after the preview. `book_dock_slot` never had the extra sentence and never asked twice. |
| B7 | `search_stock` `NOT_FOUND` tells the agent to drop generic words (such as "rolls") and keep distinguishing words (colour, size) | `log_2`: "black pallet wrap rolls" found nothing, the agent retried with "pallet wrap", dropped "black", and asked the user an unnecessary product question. After the change (`log_3`) it retried with "black pallet wrap" and asked nothing. |
| B8 | An optional server log (`KESTREL_AUDIT_LOG`) of each call: tool, step (read, preview or commit), outcome and arguments, never the token | The Copilot chat view hid the preview call, so the transcript looked as if a commit happened with no preview. The server's log shows preview, then commit, with the nine seconds between them. |
| B9 | Exception IDs come from one counter shared by all sites | IDs must be unique so `close_exception` can tell "not found" from "another site's". Cost: a Leeds user can infer a count of other sites' exceptions from gaps in the numbering. No content leaks. |

---

## Part C: observed limits (not changed)

- **A host that can read files can go around the toolkit.** With the repo open, the agent read
  `data/stock_snapshot.csv` and answered "240" for SKU-8801 in a Glasgow session. With only a
  `.vscode/mcp.json` in an empty folder, the same prompt and the same model called
  `get_stock` and was refused (`log_4`). The server enforced the boundary on every call it
  received. It cannot stop a host that reads the data directly. A real deployment would not
  keep the stock file in the agent's workspace.
- **The agent can tidy the user's words.** The close note "we replaced the rolls" reached the
  log as "We replaced the rolls." The meaning is unchanged, but the record is not verbatim.
- **The agent can confuse "valid slot" with "free slot".** After booking 10:00 it listed all
  six times as "available times" when three were booked. It had stated the free slots
  correctly one turn earlier.
- **The chat shows error results as "failed".** `CONFIRMATION_REQUIRED` (a preview) and
  `SITE_ACCESS_DENIED` display as failed tool calls. They are designed results, and the
  server log is the authoritative record.
- **A capable agent pre-checks and respects the schema.** It rarely sent the server an invalid
  slot or a booked slot, so those errors appeared live less often than in the tests. The
  protocol tests cover `SLOT_ALREADY_BOOKED` and `INVALID_ARGUMENT` explicitly.

---

## Spec amendments still to record

The committed `spec.md` differs from the built toolkit in these places. Amend it in a later
commit, with the reason (Part B):

- 4.7 `correct_stock` and 4.10 `close_exception` descriptions (B5).
- 4.8 `move_stock` and 4.9 `raise_exception` descriptions, plus 4.10 (B6).
- 4.2 `search_stock` `NOT_FOUND` suggested action (B7).
- 4.7 refusal of a no-op correction and 4.8 move semantics (B3, B4).
- 7.1 token bound to the preview text (B1).
- 4.0 or 5: the optional audit log (B8).
