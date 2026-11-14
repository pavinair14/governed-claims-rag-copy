# Warehouse Ops toolkit: agent instructions

For any agent using the `kestrel-warehouse` MCP server (Claude Code, GitHub Copilot, or
another host). This file is guidance. It is **not** the security boundary: the server
enforces schemas, site scope, confirmation and stock rules itself. The tool descriptions
carry the same rules, so nothing here should be needed to use the tools correctly.

## Ground rules

1. **Answer warehouse questions from the tools only.** Do not read data files
   (`stock_snapshot.csv`, `dock_schedule.jsonl`) or source code, and do not run code, to
   answer stock, dock or exception questions, even if they are in the workspace. That
   bypasses the toolkit's site scoping.
2. **Your site is fixed by the server.** No tool takes a site. Never ask the user which
   site, and never quote figures for another site.
3. **Never invent** SKUs, variants, quantities, bins, slots, carriers, exception IDs,
   dates, reasons or notes. If something is missing or ambiguous, ask a short question.
4. **Use the user's own words** for any reason, description or note that is written into a
   record. If they have not said why, ask.

## Which tool

| User says | Tool |
| --- | --- |
| "How much is SKU-8801?" | `get_stock` |
| "How much pallet wrap do we have?" | `search_stock` |
| "What docks are free on 8 April?" | `list_dock_slots` |
| "What exceptions are open?" | `list_exceptions` |
| "Book the 10:00 for Northbound." | `book_dock_slot` |
| "Cancel the 12:00 booking." | `cancel_dock_booking` |
| "The count for SKU-8801 is wrong." | `correct_stock` |
| "Move 20 of SKU-8801 from A-12-3 to A-13-1." | `move_stock` |
| "That pallet is damaged." | `raise_exception` |
| "Close it, we replaced the rolls." | `close_exception` |

Use read-only tools for questions. Use a state-changing tool only when the user asks for a
change. Tools starting `READ-ONLY` never change anything; tools starting `CHANGES STATE`
need the two-step flow below.

## Stock lookups

- **SKU given:** `get_stock`. Do not search by description when the SKU is known.
- **Description only:** `search_stock`.
  - `single`: one product, with its quantity. Answer directly; do not ask a question.
  - `multiple`: candidates only, no quantities. Do **not** pick one. List them and ask
    which the user means, then call `get_stock` with that SKU.
  - `NOT_FOUND`: every query word must appear in the description. Drop generic words
    (such as "rolls") and keep distinguishing words (colour, size) before asking the user.
- **A quantity of 0 is a valid answer.** Say the item exists and none is in stock. Do not
  call it "not found" and do not substitute a sibling product's quantity.

## Dock slots

- Check `list_dock_slots` before booking or cancelling, and make sure the date and slot are
  clear. Never invent a slot or a date.
- A slot is identified by **date and time**, never by carrier.
- The six slot times (06:00, 08:00, 10:00, 12:00, 14:00, 16:00) are the *valid* slots, not
  the *free* ones. Report free slots from the listing.

## State-changing tools: two steps

1. Call the tool **without** `confirmation_token`. This changes nothing and returns
   `CONFIRMATION_REQUIRED` with `proposed_action` and a token.
2. Show `proposed_action` to the user and ask **once**. Do not ask a separate yes/no before
   the preview.
3. Only after the user agrees, call again with the **same arguments** plus the token.

Never confirm on the user's behalf. A token covers one exact action: if anything changes
(the arguments, or the situation since the preview), get a fresh preview. An earlier "yes"
does not cover a different action.

### Details by tool

- **`correct_stock`** fixes a wrong count and feeds the month-end count. It needs the bin
  (take it from `get_stock` or a single `search_stock` match) and the user's reason.
  Do not use it to record a physical move.
- **`move_stock`** records stock moving between bins at your site. The total does not
  change. Do not use it to fix a count. Do not move more than the source bin holds.
- **`raise_exception`** needs a category, a SKU and a description. The category is
  `damaged` or `missing`. Find the SKU with `search_stock` if the user has none.
- **`close_exception`** is **final**: there is no reopen. Get the ID from `list_exceptions`;
  never ask the user to type it. A wrongly closed exception is handled by raising a new one.

## Errors

Errors tell you what to do. Read `code`, `field` and `suggested_action`, and use
`example_call` if present. Do not repeat the same invalid call, and do not invent a value to
make a call succeed.

| Code | What to do |
| --- | --- |
| `INVALID_ARGUMENT` | Fix the named field using the allowed values or format shown, or ask the user. |
| `NOT_FOUND` | Follow `suggested_action` (rephrase the search, pick a listed date or bin). |
| `SITE_ACCESS_DENIED` | Hard boundary. Do not retry. Say it is not held at the user's site and quote nothing about it. |
| `CONFIRMATION_REQUIRED` | Not a failure. Show the preview and ask once (see above). |
| `CONFIRMATION_INVALID` | Token expired, used, or for different arguments. Nothing changed. Get a fresh preview. |
| `SLOT_ALREADY_BOOKED` | Offer the available slots listed. Do not book another without asking. |
| `SLOT_NOT_BOOKED` | Nothing to cancel. Show the booked slots and ask which was meant. |
| `INSUFFICIENT_STOCK` | Show available versus requested. Ask whether to move what is available. |
| `ALREADY_CLOSED` | Do not retry. Quote the existing resolution note. |

## Answering

- Use only what the tools returned or the user said.
- Be concise and operational. Name the SKU, site, bin, quantity, slot or exception ID.
- Keep current state separate from a requested change.
- Do not hide an ambiguity to sound more confident.
