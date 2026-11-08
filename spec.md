# Warehouse Ops MCP Toolkit — Specification (Tool Interface Design)


## 1. Purpose and scope

Build an MCP toolkit that lets an agent answer stock and dock questions and raise
exceptions for Kestrel warehouse staff at three sites: `LEEDS-01`, `READING-02`,
`GLASGOW-03`. Staff are assigned to one site. The warehouse systems are stubbed over
the supplied `stock_snapshot.csv` and `dock_schedule.jsonl`; the deliverable is the
**interface**, not the backend.

`data/tool_specification.md` is treated as a wish-list from people who know the job,
not as a design. Section 3 lists every change from it and why.

The toolkit must be usable by an agent **from the tool descriptions, schemas and results
alone**. Nothing in this design depends on a separate instructions file being loaded by
the host; any such file is a convenience layered on top (see plan).

---

## 2. What the data says (design evidence)

### 2.1 Stock (`stock_snapshot.csv`, 16 SKUs)

| Site           | SKUs                                     | Same-site pairs that differ by one attribute                                                  |
| -------------- | ---------------------------------------- | --------------------------------------------------------------------------------------------- |
| LEEDS-01 (7)   | 8801, 8802, 8803, 8804, 8811, 8815, 8816 | 8801/8802 (clear/black wrap), 8803/8804 (12mm/16mm band), 8815/8816 (standard UK/euro pallet) |
| READING-02 (5) | 8805, 8806, 8807, 8812, 8813             | 8805/8806 (50mm/75mm corner protector), 8812/8813 (clear/printed tape)                        |
| GLASGOW-03 (4) | 8808, 8809, 8810, 8814                   | 8808/8809 (400mm/600mm shrink film)                                                           |

- **12 of 16 SKUs have a same-site sibling** that differs by one word or number. Only
  8807 (Edge board), 8814 (Label roll), 8810 (Void fill, paper) and 8811 (Void fill,
  air pillow) are unique at their site. A single fuzzy `lookup` returning a "best match"
  would confidently return the wrong product for 75% of the catalogue.
- **Ambiguity depends on site.** "Void fill" matches two products globally but exactly
  one at LEEDS-01 (8811) and one at GLASGOW-03 (8810). A design that always demands
  disambiguation fails here; a design that never does fails on "pallet wrap".
- **"Pallet" is a trap at LEEDS-01:** it matches both pallet wrap (8801, 8802) and
  pallets (8815, 8816) — four candidates, two different kinds of product.
- **Zero stock is real data.** SKU-8809 (Shrink film, 600mm) has quantity `0`; its
  sibling SKU-8808 has 150. Returning `NOT_FOUND` for 8809, or dropping zero-stock rows
  to "disambiguate", would make an agent answer "150" to a question about the 600mm film.
- **SKUs are globally unique and each is held at exactly one site**, one bin each
  (e.g. `A-12-3`, `YARD-1`). Bin prefixes are site-specific (`A-`/`YARD-` Leeds, `B-`
  Reading, `C-` Glasgow). A SKU therefore identifies its site, which is what makes a
  cross-site refusal decidable — and means `to_bin` on a move is also a cross-site vector.

### 2.2 Docks (`dock_schedule.jsonl`, 18 slots, one date: 2026-04-08)

- Slots are a **closed set** of six two-hourly starts: `06:00 08:00 10:00 12:00 14:00 16:00`.
- **The same slot time exists at all three sites.** "Book the 10:00" is a different
  physical slot per site, so a slot is only meaningful inside a site scope.
- 5 of 18 slots are booked. **Every booking is "Northbound Freight"**, and Leeds and
  Reading each have _two_ (Leeds 08:00 & 12:00; Reading 06:00 & 14:00). "Cancel Northbound's
  booking" is therefore ambiguous at two of three sites, so bookings are identified by
  `date` + `slot`, never by carrier.
- The file covers a single date. A `date` parameter must produce a useful error when
  the date has no schedule.

### 2.3 Exceptions (no data file)

There is no exceptions file: the store starts empty and only `raise_exception` creates
records. `close_exception` needs an ID that the user, wearing gloves, will not remember
or type. That is a gap in Ops' request (see `list_exceptions`, §3).

### 2.4 Ops' own notes

- "Don't make us type SKU codes" → description search must exist and must be safe.
- "`ERR_4001`, we had to ring IT" → errors must let the agent self-correct.
- "Stock corrections feed the month-end count" → corrections are the irreversible operation.
- "Someone at Leeds could see Reading's numbers" → site scope enforced by the toolkit.
- "Everything fast" → confirmation is spent only where it buys safety (§6).

---

## 3. Changes from Ops' request

Ops asked for 5 tools. The toolkit has **10**: 4 read-only, 6 state-changing.

| #   | Ops asked for                                        | Built                                                                                                                                                 | Why (evidence)                                                                                                                                                                                                               |
| --- | ---------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `lookup` (SKU _or_ rough name, one tool)             | `get_stock` (exact SKU) + `search_stock` (description)                                                                                                | Two different promises. An exact SKU can be answered with certainty; a name cannot (§2.1: 12/16 SKUs have a same-site twin). One tool with a "best match" would return the wrong item silently.                              |
| 2   | (inside `lookup`) returns "where it is and how many" | `search_stock` returns **all** candidates; quantities are **withheld** unless exactly one product matches                                             | If candidates carried quantities the agent could answer "420 pallet wrap" by adding 8801+8802 — a confident, wrong number for any purpose needing a variant. Identify first, then read.                                      |
| 3   | `check_dock` (view + book + cancel)                  | `list_dock_slots` (read) + `book_dock_slot` + `cancel_dock_booking` (write)                                                                           | Reading and writing behind one name means the model can change state while "checking". Book and cancel also differ in reversibility (§6).                                                                                    |
| 4   | `stock_change` ("same kind of thing really")         | `correct_stock` + `move_stock`                                                                                                                        | They are not the same. A correction changes the _total_ and feeds the month-end count (irreversible); a move preserves the total and is undone by a reverse move. Different parameters, failure modes and confirmation tier. |
| 5   | `raise_exception` (category, few words, SKU)         | `raise_exception` with `category` as a closed enum (`damaged` \| `missing`) and `sku` optional                                                        | Ops named exactly two categories and three fields. Free-text category would be validated after the fact; SKU-less tickets are un-actionable.                                                                                 |
| 6   | `close_exception`                                    | `close_exception`, **terminal** (no reopen tool)                                                                                                      | Ops asked for close but not its reverse. Position: closing is final and confirmed as irreversible; a wrongly closed ticket is answered by raising a new one. See "Deliberately not built".                                   |
| 7   | (not requested)                                      | `list_exceptions` (read)                                                                                                                              | `close_exception` needs an ID. Without a listing tool the agent must invent one or ask a gloved user to type it, contradicting the "no typing codes" note.                                                                   |
| 8   | "book one, cancel one"                               | `cancel_dock_booking` identifies the booking by `date` + `slot` and shows the carrier in the preview                                                  | §2.2: carrier cannot identify a booking at Leeds or Reading.                                                                                                                                                                 |
| 9   | "shouldn't be possible" (cross-site)                 | No site _selector_ anywhere. Site comes from trusted session context; an optional `site` argument is an **assertion** that is verified, never trusted | §5.                                                                                                                                                                                                                          |
| 10  | "tell us in a way that makes sense"                  | One structured error object with `code`, `message`, `field`, `details`, `suggested_action`, `example_call`                                            | §7.                                                                                                                                                                                                                          |

### Deliberately not built

**Operation type:** Read-only.

**Parameters:**

```text
sku: string
```

**Schema:**

```json
{
  "type": "object",
  "required": ["sku"],
  "properties": {
    "sku": { "type": "string", "minLength": 1 }
  },
  "additionalProperties": false
}
```

**Model-facing description:**

> Retrieve stock information for an exact SKU at the caller's assigned warehouse site. Use this tool when the user provides a specific SKU. Do not use it for approximate product-name searches.

**Rules:**

- The SKU must be a string.
- The result must be restricted to the caller's assigned site.
- A valid record with quantity `0` is still a valid stock result.
- An unknown SKU returns `NOT_FOUND`.
- The tool must not modify stock.

---

## 4. Design principles

**Purpose:** Search stock using a product description when the user does not know the SKU.

**Operation type:** Read-only.

**Parameters:**

```text
query: string
```

**Schema:**

```json
{
  "type": "object",
  "required": ["query"],
  "properties": {
    "query": { "type": "string", "minLength": 1 }
  },
  "additionalProperties": false
}
```

**Model-facing description:**

> Search products at the caller's assigned warehouse site using the product description provided by the user. Return all plausible matching candidates. If more than one candidate is plausible, do not choose one; present the candidates so the user can clarify.

**Rules:**

- Search only the caller's assigned site.
- Do not silently select a best match when multiple plausible products exist.
- Return a single result when there is one clear match.
- Return multiple candidates when the request is ambiguous.
- Return `NOT_FOUND` when no candidate exists.
- The tool must not modify stock.

**Expected agent behaviour:**

If the user asks:

> How many pallet wraps do we have?

and the data contains multiple plausible pallet-wrap products, Claude should present the candidates and ask which product the user means.

If the search produces one clear candidate, Claude should answer directly without unnecessary clarification.

---

## 5. Trusted caller context and site scoping

The server is started with a **session context** it does not take from the model:

```text
KESTREL_CALLER_ID       e.g. "ops.leeds.01"
KESTREL_ASSIGNED_SITE   one of LEEDS-01 | READING-02 | GLASGOW-03
```

- Supplied by whatever launches the server (in the stub: the `env` block of the agent-host
  registration; in production: the terminal's authenticated session). The model cannot set it.
- The server **refuses to start** if either value is missing or `ASSIGNED_SITE` is not in the closed set.
- Every tool reads the site from this context. **No tool has a site selector.**
- Every success result echoes `site`, so the agent and user always see which site the data is from.

### The optional `site` assertion

> List dock slots for the caller's assigned site on a date. Use this read-only tool to inspect availability before booking or cancelling. The site is taken from trusted caller context; never ask the caller to supply it.

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

**Result:** `ok: true`, the trusted site, ISO date, matching slots, and `slot_count`.

---

### 4.4 `book_dock_slot`

**Purpose:** Book one currently available dock slot.

**Operation type:** State-changing; explicit confirmation required.

**Parameters:**

```text
date: date
slot: string (HH:MM)
carrier: non-empty string
confirmation: literal true
```

**Model-facing description:**

> Book one available dock slot for the caller's assigned site. Use only after the user has confirmed the exact date, time, and carrier. This changes the dock schedule. The site is taken from trusted caller context.

**Schema:**

```json
{
  "type": "object",
  "required": ["date", "slot", "carrier", "confirmation"],
  "properties": {
    "date": { "type": "string", "format": "date" },
    "slot": {
      "type": "string",
      "pattern": "^(?:[01][0-9]|2[0-3]):[0-5][0-9]$"
    },
    "carrier": { "type": "string", "minLength": 1 },
    "confirmation": { "const": true }
  },
  "additionalProperties": false
}
```

The server checks that the slot exists at the assigned site and is available before updating it. An already-booked slot returns `SLOT_ALREADY_BOOKED`.

---

### 4.5 `cancel_dock_booking`

**Purpose:** Cancel one existing dock booking.

**Operation type:** State-changing; explicit confirmation required.

**Parameters:** `date: date`, `slot: string (HH:MM)`, `confirmation: literal true`.

**Model-facing description:**

> Cancel an existing dock booking for the caller's assigned site. Use only after the user has confirmed the exact date and time. This changes the dock schedule. The site is taken from trusted caller context.

The schema is an object with required `date`, `slot`, and `confirmation`, the same date and slot constraints as `book_dock_slot`, and `confirmation` constrained to `true`. The server makes the slot available only after all validation succeeds.

---

### 4.6 `correct_stock`

**Purpose:** Replace the recorded quantity after a physical count correction.

**Operation type:** State-changing and ledger-affecting; explicit confirmation required.

**Parameters:**

```text
sku: non-empty string
corrected_quantity: integer >= 0
reason: non-empty string
confirmation: literal true
```

**Model-facing description:**

> Correct the recorded quantity for an exact SKU at the caller's assigned site after a physical count. This affects month-end stock records, so require confirmation of the SKU, new quantity, and reason. Do not use it to represent a bin movement.

The schema requires these four fields, rejects additional fields, constrains `corrected_quantity` to a non-negative integer, and constrains `confirmation` to `true`. The server verifies that the SKU belongs to the assigned site before applying the correction.

---

### 4.7 `move_stock`

**Purpose:** Record a physical movement between two bins at the assigned site.

**Operation type:** State-changing; explicit confirmation required.

**Parameters:**

```text
sku: non-empty string
from_bin: non-empty string
to_bin: non-empty string
quantity: integer > 0
confirmation: literal true
```

**Model-facing description:**

> Record a physical movement of an exact SKU between two different bins at the caller's assigned site. Confirm the SKU, source bin, destination bin, and quantity first. Do not move more than the source bin contains.

The schema uses non-empty strings, `quantity` minimum `1`, and `confirmation: true`. The server verifies site ownership, distinct bins, source existence, and available quantity before applying the movement.

---

### 4.8 `raise_exception`

**Purpose:** Create a damaged or missing stock exception.

**Operation type:** State-changing operational record; explicit confirmation required.

**Parameters:**

```text
category: "damaged" | "missing"
description: non-empty string
sku: non-empty string | null (optional)
confirmation: literal true
```

**Model-facing description:**

> Raise a damaged or missing stock exception at the caller's assigned site. Use only after the user confirms the category and description, and validate an optional SKU against that site. Do not invent an exception or SKU.

The category is a closed enum and `confirmation` is constrained to `true`. If `sku` is supplied, it must belong to the assigned site. The result includes a server-generated exception ID.

---

### 4.9 `close_exception`

**Purpose:** Close an existing exception with a resolution note.

**Operation type:** State-changing operational record; explicit confirmation required.

**Parameters:**

```text
exception_id: non-empty string
resolution_note: non-empty string
confirmation: literal true
```

**Model-facing description:**

> Close an open exception belonging to the caller's assigned site. Require confirmation of the exception ID and resolution note. Do not close an unknown or already-closed exception.

The schema requires the three fields, rejects empty strings and additional fields, and constrains `confirmation` to `true`. The server checks existence, site ownership, and open status before closing it; a second close returns `ALREADY_CLOSED`.

---

## 5. Common Response and Error Contract

Every tool returns a JSON object. Successful calls contain `"ok": true` and an operation-specific result. Failed calls contain exactly this actionable shape:

```json
{
  "ok": false,
  "error": {
    "code": "MACHINE_READABLE_CODE",
    "message": "What failed and why, in plain language.",
    "field": "field_name or null",
    "details": {},
    "suggested_action": "The next corrective action for the agent."
  }
}
```

The minimum codes are:

- `INVALID_ARGUMENT`: value or required business input is invalid; include the field and allowed values or constraints.
- `NOT_FOUND`: the requested SKU, slot, or exception is not available within the caller's scope.
- `SITE_ACCESS_DENIED`: an identified record belongs to another site; do not reveal that site's quantity, bin, carrier, or schedule details.
- `CONFIRMATION_REQUIRED`: no state change occurred; return the exact proposed action so the agent can ask for confirmation.
- `SLOT_ALREADY_BOOKED`: booking was not changed; choose another available slot.
- `INSUFFICIENT_STOCK`: movement was not applied; include available and requested quantities.
- `ALREADY_CLOSED`: the exception was not changed; do not retry closure.

Schema validation may reject a call before the tool runs. It must still identify the invalid field and permitted shape where the MCP host exposes validation errors.

## 6. Safety and State Rules

1. Trusted caller context, not a tool argument, supplies `caller_id` and `assigned_site`.
2. Every stock, dock, and exception read or write is filtered by `assigned_site` inside the server.
3. Read-only tools never mutate state.
4. No state-changing operation occurs unless the request passes schema validation, business validation, and explicit confirmation.
5. Confirmation is for the specific proposed operation; a previous confirmation cannot be reused for a different operation.
6. State changes are applied atomically after validation. The in-memory test backend must make the result visible to a subsequent read in the same server session.
7. The server must not claim a change succeeded until the state layer has applied it.
8. Ambiguous description searches return all plausible candidates. The agent asks a focused clarification question rather than selecting a best match.

## 7. Decisions Against the Ops Wish-list

- The requested `lookup` is split into `get_stock` and `search_stock` because exact SKU lookup and uncertain description search need different safety behavior. The stock file contains near-identical variants such as clear and black pallet wrap.
- The requested `check_dock` is split into `list_dock_slots`, `book_dock_slot`, and `cancel_dock_booking` so inspection cannot accidentally be treated as a write.
- The requested `stock_change` is split into `correct_stock` and `move_stock` because a count correction affects the month-end record while a movement changes bin location and available stock.
- All writes require confirmation because dock bookings, stock corrections, movements, and exception records are operational state, and the requirements explicitly note that stock corrections feed month-end count.
- Site is deliberately absent from every public tool parameter. The data contains three sites and the requirements describe staff as site-assigned; accepting a user-controlled site would make the access boundary advisory.
- Search returns candidates instead of one fuzzy winner because the supplied descriptions contain meaningful variants and the requirements explicitly make uncertainty the toolkit's responsibility.

## 8. Runtime and Evidence Requirements

The implementation must register all ten tools in a real MCP server and exercise them through an MCP-compatible host. Evidence must include:

- tool discovery and selection by the host
- one unambiguous lookup answered without unnecessary clarification
- one ambiguous lookup followed by a clarification question
- confirmation refusal followed by a confirmed state change
- same-site success and cross-site refusal
- schema rejection and an actionable business error
- passing `pytest-asyncio` output
- the host registration/configuration used for the demonstration

The first four Git commits must be distinct and ordered as `01-spec`, `02-plan`, `03-tasks`, and `04-implement`; no source file may appear before `04-implement`.
