# Warehouse Ops MCP Toolkit: Specification (Tool Interface Design)

## 1. Purpose and scope

Build an MCP toolkit that lets an agent answer stock and dock questions and raise and
close exceptions for Kestrel warehouse staff at three sites: `LEEDS-01`, `READING-02`,
`GLASGOW-03`. Staff are assigned to one site. The warehouse systems are stubbed over the
supplied `stock_snapshot.csv` and `dock_schedule.jsonl`; the deliverable is the
**interface**, not the backend.

`data/tool_specification.md` is treated as a wish-list from people who know the job, not
as a design. Section 3 lists every change from it and why.

The toolkit must be usable by an agent **from the tool descriptions, schemas and results
alone**. Nothing here depends on a separate instructions file being loaded by the host;
any such file is a convenience layered on top.

---

## 2. What the data says (design evidence)

### 2.1 Stock (`stock_snapshot.csv`, 16 SKUs)

| Site           | SKUs                                     | Same-site pairs that differ by one attribute                                                  |
| -------------- | ---------------------------------------- | --------------------------------------------------------------------------------------------- |
| LEEDS-01 (7)   | 8801, 8802, 8803, 8804, 8811, 8815, 8816 | 8801/8802 (clear/black wrap), 8803/8804 (12mm/16mm band), 8815/8816 (standard UK/euro pallet) |
| READING-02 (5) | 8805, 8806, 8807, 8812, 8813             | 8805/8806 (50mm/75mm corner protector), 8812/8813 (clear/printed tape)                        |
| GLASGOW-03 (4) | 8808, 8809, 8810, 8814                   | 8808/8809 (400mm/600mm shrink film)                                                           |

- **12 of 16 SKUs have a same-site sibling** that differs by one word or number. Only 8807
  (Edge board), 8814 (Label roll), 8810 (Void fill, paper) and 8811 (Void fill, air
  pillow) are unique at their site. A single fuzzy `lookup` returning a "best match"
  would confidently return the wrong product for 75% of the catalogue.
- **Ambiguity depends on site.** "Void fill" matches two products globally but exactly one
  at LEEDS-01 (8811) and one at GLASGOW-03 (8810). A design that always demands
  disambiguation fails here; a design that never does fails on "pallet wrap".
- **"Pallet" is a trap at LEEDS-01:** it matches pallet wrap (8801, 8802) and pallets
  (8815, 8816): four candidates across two kinds of product.
- **Zero stock is real data.** SKU-8809 (Shrink film, 600mm) has quantity `0`; its sibling
  SKU-8808 has 150. Returning `NOT_FOUND` for 8809, or dropping zero-stock rows to
  "disambiguate", would make an agent answer "150" to a question about the 600mm film.
- **SKUs are globally unique and each is held at exactly one site, in one bin.** Bin
  prefixes are site-specific (`A-`/`YARD-` Leeds, `B-` Reading, `C-` Glasgow). A SKU
  therefore identifies its site, which makes a cross-site refusal decidable, and means
  `to_bin` on a move is also a cross-site vector.

### 2.2 Docks (`dock_schedule.jsonl`, 18 slots, one date: 2026-04-08)

- Slots are a **closed set** of six two-hourly starts: `06:00 08:00 10:00 12:00 14:00 16:00`.
- **The same slot time exists at all three sites.** "Book the 10:00" is a different
  physical slot per site, so a slot only means something inside a site scope.
- 5 of 18 slots are booked. **Every booking is "Northbound Freight"**, and Leeds
  (08:00, 12:00) and Reading (06:00, 14:00) each have two. "Cancel Northbound's booking"
  is therefore ambiguous at two of three sites, so bookings are identified by
  `date` + `slot`, never by carrier.
- The file covers a single date, so a `date` with no schedule needs a useful error.

### 2.3 Exceptions (no data file)

The store starts empty and only `raise_exception` creates records. `close_exception`
needs an ID that a gloved user will not remember or type. That is a gap in Ops' request.

### 2.4 Ops' own notes

- "Don't make us type SKU codes" -> description search must exist and must be safe.
- "`ERR_4001`, we had to ring IT" -> errors must let the agent self-correct.
- "Stock corrections feed the month-end count" -> corrections are the irreversible operation.
- "Someone at Leeds could see Reading's numbers" -> site scope enforced by the toolkit.
- "Everything fast" -> confirmation costs one extra step; Section 7 explains why we accept it.

---

## 3. Changes from Ops' request

Ops asked for 5 tools. The toolkit has **10**: 4 read-only, 6 state-changing.

| #   | Ops asked for                                        | Built                                                                                  | Why (evidence)                                                                                                                                                                                                                       |
| --- | ---------------------------------------------------- | -------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1   | `lookup` (SKU _or_ rough name, one tool)             | `get_stock` (exact SKU) + `search_stock` (description)                                 | Two different promises. An exact SKU can be answered with certainty; a name cannot (2.1: 12/16 SKUs have a same-site twin). One tool with a "best match" would return the wrong item silently.                                       |
| 2   | (inside `lookup`) returns "where it is and how many" | `search_stock` returns **all** candidates; quantities withheld unless exactly one match | If ambiguous candidates carried quantities, the agent could answer "420 pallet wrap" by adding 8801+8802: a confident wrong number for any task needing a variant. Identify first, then read with `get_stock`.                        |
| 3   | `check_dock` (view + book + cancel)                  | `list_dock_slots` (read) + `book_dock_slot` + `cancel_dock_booking` (write)            | Reading and writing behind one name lets the model change state while "checking". Book and cancel also differ in reversibility.                                                                                                      |
| 4   | `stock_change` ("same kind of thing really")         | `correct_stock` + `move_stock`                                                         | Not the same. A correction changes the _total_ and feeds the month-end count; a move preserves the total and is undone by a reverse move. Different parameters, failure modes and consequences.                                      |
| 5   | `raise_exception` (category, few words, SKU)         | `raise_exception` with `category` enum (`damaged` \| `missing`) and `sku` **required** | Ops named exactly two categories and three fields. A free-text category would be validated after the fact. Ops said the ticket relates to "which SKU", and a ticket without one is un-actionable. Staff find it with `search_stock`. |
| 6   | `close_exception`                                    | `close_exception`, **terminal** (no reopen tool)                                       | Ops asked for close but not its reverse. Position: closing is final and is confirmed as such; a wrongly closed ticket is answered by raising a new one (Section 8).                                                                  |
| 7   | (not requested)                                      | `list_exceptions` (read)                                                               | `close_exception` needs an ID. Without a listing tool the agent must invent one or ask a gloved user to type it, contradicting the "no typing codes" note.                                                                           |
| 8   | "book one, cancel one"                               | Bookings identified by `date` + `slot`; the preview shows the carrier                  | 2.2: carrier cannot identify a booking at Leeds or Reading.                                                                                                                                                                          |
| 9   | "shouldn't be possible" (cross-site)                 | **No `site` parameter on any tool.** Site comes from server config (Section 5)         | A site parameter would have to be trusted or verified. A parameter that does not exist cannot be misused.                                                                                                                            |
| 10  | "tell us in a way that makes sense"                  | One structured error object with a corrected example call                              | Section 6.                                                                                                                                                                                                                           |
| 11  | "everything fast"                                    | Confirmation on all 6 state-changing tools, as a two-step preview/commit               | Section 7. Each write is operational state (see Section 7 for per-tool reasons).                                                                                                                                                     |

---

## 4. Tool interface

### 4.0 Conventions that apply to every tool

- **Read-only vs state-changing is visible in the interface.** Every tool sets MCP
  annotations (`readOnlyHint: true` for the four reads, `false` for the six writes;
  `destructiveHint: true` for `cancel_dock_booking`, `correct_stock` and
  `close_exception`) **and** every description starts with `READ-ONLY.` or
  `CHANGES STATE.`
- **No tool has a `site` parameter.** The site comes from trusted server context
  (Section 5). Every success result echoes `site`.
- **Closed value sets are enums in the schema:** `slot`, `status`, `category`.
- **All schemas set `additionalProperties: false`.**
- **Write tools use a two-step flow** (Section 7). They accept an optional
  `confirmation_token`. A first call without a token never changes state.

### 4.1 `get_stock`

**Operation type:** read-only.

**Model-facing description:**

> READ-ONLY. Get stock for one exact SKU (format SKU-1234) at the caller's own site:
> description, each bin location with quantity, and total. Use when the user gives a
> SKU, or after search_stock identified one product. A quantity of 0 is a valid result,
> not an error. Do not guess SKUs; for descriptions use search_stock.

**Schema:**

```json
{
  "type": "object",
  "required": ["sku"],
  "properties": {
    "sku": { "type": "string", "pattern": "^SKU-[0-9]{4}$" }
  },
  "additionalProperties": false
}
```

**Success result:**

```json
{
  "ok": true,
  "site": "LEEDS-01",
  "sku": "SKU-8801",
  "description": "Pallet wrap, 500mm clear",
  "unit": "each",
  "locations": [{ "bin": "A-12-3", "quantity": 240 }],
  "total_quantity": 240
}
```

**Rules:**

- Unknown SKU -> `NOT_FOUND`.
- SKU exists at another site (e.g. SKU-8805 requested from Leeds) -> `SITE_ACCESS_DENIED`.
  The error names no site, bin or quantity. It only says the item is not stocked here.
- Quantity `0` returns `ok: true` with `total_quantity: 0`.

### 4.2 `search_stock`

**Operation type:** read-only.

**Model-facing description:**

> READ-ONLY. Search products at the caller's own site by description when the user
> does not know the SKU. Returns ALL plausible matches. If match_status is "single",
> the one product is returned with its quantity; answer directly. If it is "multiple",
> quantities are withheld: do NOT pick one; list the candidates and ask the user which
> they mean, then call get_stock with the chosen SKU. Never invent a SKU.

**Schema:**

```json
{
  "type": "object",
  "required": ["query"],
  "properties": {
    "query": { "type": "string", "minLength": 2, "maxLength": 80 }
  },
  "additionalProperties": false
}
```

**Matching rule:** case-insensitive; the query is split into words (a trailing "s" is
ignored, so "wraps" matches "wrap"); a product matches when **every** word appears in
its description. Only the caller's site is searched.

**Success result, one match:**

```json
{
  "ok": true,
  "site": "READING-02",
  "match_status": "single",
  "matches": [
    {
      "sku": "SKU-8807",
      "description": "Edge board, 1200mm",
      "unit": "each",
      "locations": [{ "bin": "B-05-2", "quantity": 340 }],
      "total_quantity": 340
    }
  ]
}
```

**Success result, several matches (quantities and bins withheld):**

```json
{
  "ok": true,
  "site": "LEEDS-01",
  "match_status": "multiple",
  "matches": [
    { "sku": "SKU-8801", "description": "Pallet wrap, 500mm clear" },
    { "sku": "SKU-8802", "description": "Pallet wrap, 500mm black" }
  ],
  "next_step": "Ask the user which product they mean, then call get_stock with that SKU."
}
```

**Rules:**

- Zero matches -> `NOT_FOUND` with a suggestion to try fewer or different words.
- Never returns another site's products. A search for "edge board" at Leeds is
  `NOT_FOUND` and does not hint that Reading stocks it (a description is not an
  identifier, unlike a SKU in `get_stock`).
- A zero-stock product still counts as a match (SKU-8809 appears and is not dropped).
- Worked cases at LEEDS-01: "pallet wrap" -> 2 (multiple); "pallet" -> 4 (multiple);
  "void fill" -> 1 (single, 8811); "strapping 12" -> 1 (single, 8803).

### 4.3 `list_dock_slots`

**Operation type:** read-only.

**Model-facing description:**

> READ-ONLY. List dock slots at the caller's own site for one date, optionally filtered
> by status. Use to answer "what's free" and before booking or cancelling. Booked
> slots show their carrier. Never ask the user for a site.

**Schema:**

```json
{
  "type": "object",
  "required": ["date"],
  "properties": {
    "date": { "type": "string", "format": "date" },
    "status": {
      "type": "string",
      "enum": ["available", "booked", "all"],
      "default": "all"
    }
  },
  "additionalProperties": false
}
```

**Success result:** `ok`, `site`, `date`, `slots` (each `{slot, status, carrier}`),
`slot_count`. A date with no schedule -> `NOT_FOUND` with
`details.scheduled_dates` listing the dates that do have one.

### 4.4 `list_exceptions`

**Operation type:** read-only.

**Model-facing description:**

> READ-ONLY. List exceptions raised at the caller's own site. Use to find an
> exception ID before closing one; never ask the user to type or remember an ID.
> Defaults to open exceptions.

**Schema:**

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string",
      "enum": ["open", "closed", "all"],
      "default": "open"
    }
  },
  "additionalProperties": false
}
```

**Success result:** `ok`, `site`, `exceptions` (each `{exception_id, category, sku,
description, status, raised_at, resolution_note}`), `exception_count`. An empty list is
a valid result, not an error.

### 4.5 `book_dock_slot`

**Operation type:** state-changing. Reversible (by `cancel_dock_booking`). Confirmation required.

**Model-facing description:**

> CHANGES STATE (requires confirmation). Book one available dock slot at the caller's
> own site. First call without confirmation_token returns a preview; show it to the
> user and only after they agree call again with the same arguments plus the returned
> confirmation_token. Never invent a slot; check list_dock_slots first.

**Schema:**

```json
{
  "type": "object",
  "required": ["date", "slot", "carrier"],
  "properties": {
    "date": { "type": "string", "format": "date" },
    "slot": {
      "type": "string",
      "enum": ["06:00", "08:00", "10:00", "12:00", "14:00", "16:00"]
    },
    "carrier": { "type": "string", "minLength": 1, "maxLength": 80 },
    "confirmation_token": { "type": "string" }
  },
  "additionalProperties": false
}
```

**Rules:** slot already booked -> `SLOT_ALREADY_BOOKED` (returned at preview time, so
the user is never asked to confirm a booking that would fail); date with no schedule ->
`NOT_FOUND`.

### 4.6 `cancel_dock_booking`

**Operation type:** state-changing. Confirmation required. Treated as destructive: the
carrier may already be on its way, and the freed slot can be taken by someone else.

**Model-facing description:**

> CHANGES STATE (requires confirmation). Cancel an existing dock booking at the
> caller's own site, identified by date and slot (never by carrier). First call returns
> a preview that names the carrier; confirm with the user, then repeat with the
> returned confirmation_token.

**Schema:** `date` (format date), `slot` (the same six-value enum),
`confirmation_token` (optional string). Required: `date`, `slot`.
`additionalProperties: false`.

**Rules:** slot exists but is not booked -> `SLOT_NOT_BOOKED`.

### 4.7 `correct_stock`

**Operation type:** state-changing, **ledger-affecting**. Confirmation required.
Treated as destructive: the old figure is overwritten and the correction feeds the
month-end count.

**Model-facing description:**

> CHANGES STATE (requires confirmation). Correct the recorded quantity of one SKU in
> one bin at the caller's own site after a physical count. Feeds the month-end count.
> The preview shows old quantity, new quantity and difference; confirm all three with
> the user. Do NOT use this to record moving stock between bins: use move_stock.

**Schema:**

```json
{
  "type": "object",
  "required": ["sku", "bin", "corrected_quantity", "reason"],
  "properties": {
    "sku": { "type": "string", "pattern": "^SKU-[0-9]{4}$" },
    "bin": { "type": "string", "minLength": 1, "maxLength": 20 },
    "corrected_quantity": { "type": "integer", "minimum": 0 },
    "reason": { "type": "string", "minLength": 3, "maxLength": 300 },
    "confirmation_token": { "type": "string" }
  },
  "additionalProperties": false
}
```

**Rules:** the SKU must be held at the caller's site (`SITE_ACCESS_DENIED` otherwise,
`NOT_FOUND` if unknown); the bin must hold that SKU (`NOT_FOUND` with the bins that do).
`bin` is required because after a partial move a SKU can sit in more than one bin and a
count is taken per bin; the agent gets the bins from `get_stock`.

### 4.8 `move_stock`

**Operation type:** state-changing. Confirmation required. Total quantity is unchanged;
a move is undone by a reverse move.

**Model-facing description:**

> CHANGES STATE (requires confirmation). Record moving a quantity of one SKU from one
> bin to another bin at the caller's own site. Total stock does not change. Confirm
> SKU, source bin, destination bin and quantity with the user. Do not use to fix a wrong
> count: use correct_stock.

**Schema:**

```json
{
  "type": "object",
  "required": ["sku", "from_bin", "to_bin", "quantity"],
  "properties": {
    "sku": { "type": "string", "pattern": "^SKU-[0-9]{4}$" },
    "from_bin": { "type": "string", "minLength": 1, "maxLength": 20 },
    "to_bin": { "type": "string", "minLength": 1, "maxLength": 20 },
    "quantity": { "type": "integer", "minimum": 1 },
    "confirmation_token": { "type": "string" }
  },
  "additionalProperties": false
}
```

**Rules:** `from_bin` must hold the SKU; `quantity` above what it holds ->
`INSUFFICIENT_STOCK` (with `available` and `requested`); `from_bin` equal to `to_bin` ->
`INVALID_ARGUMENT`; a `to_bin` whose prefix belongs to another site -> `SITE_ACCESS_DENIED`;
a malformed `to_bin` -> `INVALID_ARGUMENT`. A partial move leaves the remainder in
`from_bin` and creates or increases the quantity in `to_bin`.

### 4.9 `raise_exception`

**Operation type:** state-changing. Confirmation required.

**Model-facing description:**

> CHANGES STATE (requires confirmation). Raise a damaged or missing-stock exception
> for one SKU at the caller's own site. Category must be "damaged" or "missing".
> Returns a server-generated exception ID. Confirm category, SKU and description with
> the user first. If the user has no SKU, use search_stock to find it.

**Schema:**

```json
{
  "type": "object",
  "required": ["category", "sku", "description"],
  "properties": {
    "category": { "type": "string", "enum": ["damaged", "missing"] },
    "sku": { "type": "string", "pattern": "^SKU-[0-9]{4}$" },
    "description": { "type": "string", "minLength": 3, "maxLength": 500 },
    "confirmation_token": { "type": "string" }
  },
  "additionalProperties": false
}
```

**Rules:** SKU must be held at the caller's site (`SITE_ACCESS_DENIED` / `NOT_FOUND`).
IDs have the form `EX-001`, generated by the server.

### 4.10 `close_exception`

**Operation type:** state-changing, **terminal**. Confirmation required. Treated as
destructive because there is no reopen tool.

**Model-facing description:**

> CHANGES STATE (requires confirmation). Close an open exception at the caller's own
> site with a resolution note. Closing is final; there is no reopen. Use list_exceptions
> to get the ID; never invent one. Confirm the ID and note with the user first.

**Schema:**

```json
{
  "type": "object",
  "required": ["exception_id", "resolution_note"],
  "properties": {
    "exception_id": { "type": "string", "pattern": "^EX-[0-9]{3,}$" },
    "resolution_note": { "type": "string", "minLength": 3, "maxLength": 500 },
    "confirmation_token": { "type": "string" }
  },
  "additionalProperties": false
}
```

**Rules:** unknown ID -> `NOT_FOUND`; exception at another site -> `SITE_ACCESS_DENIED`;
already closed -> `ALREADY_CLOSED` (do not retry).

---

## 5. Trusted caller context and site scoping

The server is started with a **session context** that does not come from the model:

```text
KESTREL_CALLER_ID       e.g. "ops.leeds.01"
KESTREL_ASSIGNED_SITE   one of LEEDS-01 | READING-02 | GLASGOW-03
```

- Supplied by whatever launches the server (in the stub: the `env` block of the
  agent-host registration; in production: the terminal's authenticated session).
- The server **refuses to start** if either value is missing or `KESTREL_ASSIGNED_SITE`
  is not in the closed set.
- Every tool reads the site from this context. No tool accepts a site.
- Every record read or written is filtered by that site **inside the server**. Where the
  caller names an identifier that exists at another site (SKU, `to_bin`, exception ID),
  the answer is `SITE_ACCESS_DENIED`, which discloses no quantity, bin, carrier,
  schedule or site name. Where the caller only describes something (`search_stock`), the
  other site's records are simply not searched.

**Why `SITE_ACCESS_DENIED` rather than `NOT_FOUND` for a cross-site identifier:**
`NOT_FOUND` would be a false statement ("check the code for typos" when the code is
correct) and would send the agent down the wrong recovery path. The denial confirms only
that the identifier exists elsewhere. Accepted cost: that fact is revealed.

---

## 6. Response and error contract

Every tool returns a JSON object. Success: `"ok": true` plus a result. Failure:

```json
{
  "ok": false,
  "error": {
    "code": "MACHINE_READABLE_CODE",
    "message": "What failed and why, in plain language.",
    "field": "field_name or null",
    "details": {},
    "suggested_action": "The next corrective step for the agent.",
    "example_call": { "tool": "tool_name", "arguments": {} }
  }
}
```

`example_call` is a corrected call where one can be built (omitted otherwise).

| Code                    | Meaning and what the error must contain                                                                 |
| ----------------------- | ------------------------------------------------------------------------------------------------------- |
| `INVALID_ARGUMENT`      | A value is missing, malformed or out of range. Names the `field`, the constraint or allowed values, and gives an `example_call`. |
| `NOT_FOUND`             | No such SKU, slot, date, bin or exception within the caller's scope. Lists what does exist where safe (e.g. `scheduled_dates`). |
| `SITE_ACCESS_DENIED`    | An identified record belongs to another site. Reveals none of its data. Hard boundary: do not retry.    |
| `CONFIRMATION_REQUIRED` | No change made. `details.proposed_action` and `details.confirmation_token` are included.                |
| `CONFIRMATION_INVALID`  | Token expired, already used, or issued for different arguments. No change made. Call without a token to get a fresh preview. |
| `SLOT_ALREADY_BOOKED`   | Booking not changed. Lists nearby `available` slots in `details`.                                       |
| `SLOT_NOT_BOOKED`       | Cancellation target is not booked. Nothing to cancel.                                                   |
| `INSUFFICIENT_STOCK`    | Move not applied. `details` has `available` and `requested`.                                            |
| `ALREADY_CLOSED`        | Exception was not changed. Do not retry.                                                                |

**Schema rejections** use the same shape. The server catches validation failures and
returns `INVALID_ARGUMENT` with the offending `field`, the permitted values or pattern,
and an `example_call`, rather than the host's default validation text.

---

## 7. Confirmation and state rules

### 7.1 Two-step confirmation on all six write tools

1. **Preview call.** The agent calls the tool without `confirmation_token`. The server
   runs full schema **and** business validation, changes nothing, and returns
   `CONFIRMATION_REQUIRED` with `details.proposed_action` (human-readable, e.g. "Cancel
   the 12:00 dock booking on 2026-04-08 at LEEDS-01 held by Northbound Freight") and a
   `confirmation_token`.
2. **Commit call.** After the user agrees, the agent repeats the call with identical
   arguments plus the token. The server applies the change.

The token is single-use, expires after 5 minutes, and is bound to the caller, the tool
and the exact arguments. Reusing it for any other operation returns
`CONFIRMATION_INVALID`.

Validating at preview time means the user is never asked to confirm something that
would fail (e.g. booking a taken slot).

**What this does and does not guarantee.** The server cannot see the human. The token
guarantees that the action committed is exactly the one previewed, and that no write
can happen in a single blind call. The human decision itself rests on the agent showing
the preview, plus the host's own tool-approval prompt. The token is not a substitute
for either.

### 7.2 Why all six, and what it costs

| Tool                  | Reason for confirmation                                                          |
| --------------------- | -------------------------------------------------------------------------------- |
| `correct_stock`       | Overwrites a figure that feeds the month-end count.                              |
| `move_stock`          | Changes bin records; a wrong move misdirects the next picker.                    |
| `cancel_dock_booking` | The carrier may already be en route; the slot can be taken by someone else.      |
| `close_exception`     | Ops never asked for a reopen, so closing is final.                               |
| `book_dock_slot`      | Reversible, but a wrong booking blocks a real slot; kept uniform for simplicity. |
| `raise_exception`     | Reversible only by raising and closing noise; kept uniform for simplicity.       |

**Cost:** one extra round-trip per write on a forklift terminal. Accepted: a wrong
correction or cancellation costs far more than one extra tap, and a single uniform rule
is harder for an agent to get wrong than a per-tool exception list.

### 7.3 State rules

1. Trusted context, not a tool argument, supplies the caller and site.
2. Read-only tools never mutate state.
3. A state change happens only after schema validation, business validation and a valid
   confirmation token.
4. Changes are applied atomically. The in-memory test backend makes them visible to a
   subsequent read in the same server session.
5. The server never reports success before the state layer has applied the change.
6. Ambiguous searches return all plausible candidates; the agent asks, never picks.

---

## 8. Deliberately not built

- **No `reopen_exception`.** Ops asked for close only. A reopen would need rules about
  who may do it and what happens to the resolution note. Position: closing is terminal;
  a wrongly closed ticket is answered by raising a new exception. This is stated in the
  `close_exception` description so the agent warns the user.
- **No site selector** on any tool (Section 5).
- **No cross-site stock transfer.** Not requested, and it would be a cross-site vector.
  `move_stock` is bin-to-bin within the caller's site only.
- **No bulk operations and no edit or delete of exceptions.** Not requested; each would
  widen the blast radius of a single call.
- **No "best match" lookup.** Rejected in Section 3, row 1.

## 9. Evidence and runtime requirements

The implementation must register all ten tools in a real MCP server and exercise them
through an MCP-compatible host (Claude Code). Evidence must include:

- tool discovery and selection by the host
- one unambiguous lookup answered without unnecessary clarification (e.g. "void fill" at Leeds)
- one ambiguous lookup followed by a clarification question (e.g. "pallet wrap")
- a zero-stock answer for SKU-8809 at Glasgow, reported as zero rather than not found
- a preview followed by a confirmed state change, and a commit attempt with a wrong token
- same-site success and cross-site refusal (e.g. SKU-8805 from Leeds)
- schema rejection and an actionable business error (e.g. booking a booked slot)
- passing `pytest-asyncio` output covering invocation, schema rejection, site scoping,
  confirmation and error shape
- the host registration config used for the demonstration

The first four Git commits must be distinct and ordered `01-spec`, `02-plan`,
`03-tasks`, `04-implement`; no source file may appear before `04-implement`.