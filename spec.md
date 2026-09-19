# Warehouse Ops MCP Toolkit Specification

## 1. Purpose

Build a safe, agent-friendly MCP toolkit for Kestrel warehouse operations across three sites:

- `LEEDS-01`
- `READING-02`
- `GLASGOW-03`

The toolkit will allow an AI agent to answer warehouse questions and perform approved operational actions using the supplied warehouse data as a stub backend.

The design must not simply reproduce the Warehouse Ops wish-list. The supplied requirements are treated as business requirements, while this document defines the actual tool interface.

The toolkit must support:

- clear tool boundaries
- schema-constrained inputs
- safe handling of ambiguous requests
- explicit confirmation for state-changing operations
- server-enforced site scoping
- actionable errors
- agent-friendly tool descriptions
- runtime use through a real MCP-compatible agent host, using Claude Code for the demonstration

The case specifically requires the interface to be designed before implementation and the resulting Git history to show that sequence.

---

## 2. Design Principles

### 2.1 Design from the supplied data

The stock and dock data must be inspected before finalizing tool behaviour.

The lookup interface must not promise more than the stock data can support.

Where multiple products have similar descriptions, a name-based search must return candidates rather than silently selecting a best match.

### 2.2 Separate read-only and state-changing operations

Read operations and state-changing operations are exposed as separate tools.

This prevents an agent from treating a tool that can modify warehouse state as if it were only a lookup.

### 2.3 Use schema constraints

Tool parameters must use explicit types and closed sets where applicable.

Examples include:

- site values
- dock status
- exception category
- stock quantities
- confirmation values

Invalid values should be rejected by the schema before the operation is performed.

### 2.4 Confirmation for state changes

Any operation that changes warehouse state or affects operational records requires explicit confirmation.

The tool must not perform the change when confirmation is absent.

### 2.5 Enforce site scope in the toolkit

The caller has an assigned site.

The MCP server must enforce that site restriction.

The agent or user must not be able to provide a different site value and use it to access another site's data.

Valid sites are:

- `LEEDS-01`
- `READING-02`
- `GLASGOW-03`

### 2.6 Do not guess under uncertainty

The agent should only receive a single stock result when the search produces one clear match.

If multiple plausible products match the request, the search tool returns the candidates and the agent asks the user to clarify.

The agent must not confidently choose one candidate merely because it is the closest textual match.

### 2.7 Errors must be actionable

Errors must explain:

1. what failed
2. why it failed
3. which field or value caused the problem, where applicable
4. what the agent should do next

The error should allow the agent to correct its request without requiring the user to understand an internal error code.

---

## 3. Trusted Caller Context

The toolkit uses trusted caller context containing:

```text
caller_id
assigned_site
```

`assigned_site` is supplied by the trusted application/agent-host context rather than being treated as a user-controlled authorization parameter.

The valid site set is:

```text
LEEDS-01
READING-02
GLASGOW-03
```

Every tool that accesses site-specific warehouse data must apply the caller's assigned-site restriction.

A user asking about another site must not be able to bypass this restriction by supplying a different site value.

---

## 4. Tool Interface

The toolkit exposes nine tools.

### 4.1 `get_stock`

**Purpose:** Retrieve stock information for an exact SKU.

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
		"sku": {"type": "string", "minLength": 1}
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

### 4.2 `search_stock`

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
		"query": {"type": "string", "minLength": 1}
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

### 4.3 `list_dock_slots`

**Purpose:** View dock slots for the caller's assigned site.

**Operation type:** Read-only.

**Parameters:**

```text
date: date
status: "available" | "booked" | "all"
```

`status` defaults to `all`.

**Model-facing description:**

> List dock slots for the caller's assigned site on a date. Use this read-only tool to inspect availability before booking or cancelling. The site is taken from trusted caller context; never ask the caller to supply it.

**Schema:**

```json
{
	"type": "object",
	"required": ["date"],
	"properties": {
		"date": {"type": "string", "format": "date"},
		"status": {"type": "string", "enum": ["available", "booked", "all"], "default": "all"}
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
		"date": {"type": "string", "format": "date"},
		"slot": {"type": "string", "pattern": "^(?:[01][0-9]|2[0-3]):[0-5][0-9]$"},
		"carrier": {"type": "string", "minLength": 1},
		"confirmation": {"const": true}
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

The implementation must register all nine tools in a real MCP server and exercise them through an MCP-compatible host. Evidence must include:

- tool discovery and selection by the host
- one unambiguous lookup answered without unnecessary clarification
- one ambiguous lookup followed by a clarification question
- confirmation refusal followed by a confirmed state change
- same-site success and cross-site refusal
- schema rejection and an actionable business error
- passing `pytest-asyncio` output
- the host registration/configuration used for the demonstration

The first four Git commits must be distinct and ordered as `01-spec`, `02-plan`, `03-tasks`, and `04-implement`; no source file may appear before `04-implement`.
