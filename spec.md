# Warehouse Ops MCP Toolkit Specification

## 1. Purpose

The Warehouse Ops MCP Toolkit provides a safe, agent-friendly interface for warehouse operations at Kestrel's three warehouse sites:

- `LEEDS-01`
- `READING-02`
- `GLASGOW-03`

The toolkit allows an AI agent to:

- Find stock using an exact SKU or product description.
- View dock availability.
- Book and cancel dock slots.
- Correct stock quantities.
- Move stock between bins.
- Raise warehouse exceptions.
- Close warehouse exceptions.

The toolkit is designed for use by warehouse operations staff through an AI agent. The interface must therefore make read-only operations, state-changing operations, validation failures, ambiguity, confirmation requirements, and site authorization clear to the agent.

The supplied CSV and JSONL files are used as the stub warehouse backend. The primary objective is the quality and safety of the MCP interface rather than integration with real warehouse systems.

## 2. Design Principles

### 2.1 Design from the supplied data

The tool interface must reflect what the supplied warehouse data can safely support.

The stock snapshot contains 16 SKUs across three sites. Several product descriptions are very similar, so a product-name search cannot safely assume that the closest textual match is always the intended SKU.

Therefore, descriptive searches must return all plausible candidates when the query is ambiguous instead of silently selecting a single SKU.

### 2.2 Separate read and state-changing operations

Read-only operations and state-changing operations must use separate tools.

This allows an AI agent to distinguish between:

- retrieving information, and
- performing an action that changes warehouse state.

The original Ops request combines multiple behaviours under `check_dock` and `stock_change`. These operations are separated in this specification.

### 2.3 Constrain inputs with schemas

Parameters with a closed set of valid values must be represented using constrained schemas/enums.

Examples include:

- warehouse site
- dock status
- exception category

Invalid values must be rejected before the operation is performed.

### 2.4 Require confirmation for state-changing operations

State-changing operations must not modify warehouse state without explicit confirmation.

This is particularly important for stock corrections because stock corrections feed the month-end count.

The confirmation requirement is part of the tool contract rather than being left entirely to the agent.

### 2.5 Enforce site scope in the toolkit

Every operation must be restricted to the caller's assigned warehouse site.

The toolkit must enforce this boundary using trusted caller context.

A caller must not gain access to another site simply by supplying another site value as a tool argument.

### 2.6 Return actionable errors

Errors must explain:

1. What failed.
2. Why it failed.
3. Which input caused the problem, when applicable.
4. What the agent should do next.

Opaque errors such as `ERR_4001` are not sufficient.

### 2.7 Do not guess when the data is ambiguous

When multiple products are plausible matches, the toolkit must return the candidates so that the agent can ask the user to clarify.

When there is exactly one clear match, the toolkit should return that match without unnecessarily asking the user for additional information.

## 3. Caller and Site Context

The toolkit operates with trusted caller context containing:

- `caller_id`
- `assigned_site`

`assigned_site` must be one of:

- `LEEDS-01`
- `READING-02`
- `GLASGOW-03`

The assigned site is established outside normal tool arguments and is enforced by the toolkit.

The toolkit must not trust a user-supplied site value as authorization.

If a request attempts to access data belonging to another site, the operation must fail with a `SITE_ACCESS_DENIED` error.

Valid access to the caller's own site must continue to work.

## 4. Tool Overview

The toolkit exposes the following tools:

| Tool                  | Purpose                                | Type           | Confirmation |
| --------------------- | -------------------------------------- | -------------- | ------------ |
| `get_stock`           | Retrieve stock using an exact SKU      | Read-only      | No           |
| `search_stock`        | Search stock using product description | Read-only      | No           |
| `list_dock_slots`     | View dock slots                        | Read-only      | No           |
| `book_dock_slot`      | Book an available dock slot            | State-changing | Yes          |
| `cancel_dock_booking` | Cancel an existing dock booking        | State-changing | Yes          |
| `correct_stock`       | Correct a recorded stock quantity      | State-changing | Yes          |
| `move_stock`          | Record stock movement between bins     | State-changing | Yes          |
| `raise_exception`     | Create a warehouse exception           | State-changing | Yes          |
| `close_exception`     | Close a warehouse exception            | State-changing | Yes          |

## 5. Stock Tools

### 5.1 `get_stock`

#### Purpose

Retrieve the stock record for an exact SKU at the caller's assigned site.

#### Model-facing description

> Get the current stock record for a specific SKU at the caller's assigned warehouse site. Use this tool when the exact SKU is known. Do not use this tool for approximate product-name searches. The result includes the product description, bin, quantity and unit. Access is restricted to the caller's assigned site.

#### Parameters

| Parameter | Type   | Required | Description          |
| --------- | ------ | -------- | -------------------- |
| `sku`     | string | Yes      | Exact SKU to look up |

#### Behaviour

- The SKU must be supplied.
- The lookup is restricted to the caller's assigned site.
- A valid SKU returns its stock record.
- A SKU with quantity `0` is still a valid stock record.
- A SKU that does not exist at the caller's site returns `NOT_FOUND`.
- The tool does not modify warehouse state.

### 5.2 `search_stock`

#### Purpose

Search for stock using product-description text when the exact SKU is not known.

#### Model-facing description

> Search stock at the caller's assigned warehouse site using product-description text. Return all plausible matching products. Do not select a single product when multiple candidates are plausible. If multiple candidates are returned, ask the user to clarify before performing an SKU-specific operation.

#### Parameters

| Parameter | Type   | Required | Description                        |
| --------- | ------ | -------- | ---------------------------------- |
| `query`   | string | Yes      | Product description or search text |

#### Behaviour

- Search only within the caller's assigned site.
- Return matching stock records.
- Each candidate should include:
  - SKU
  - description
  - bin
  - quantity
  - unit

- If exactly one clear match exists, return that match.
- If multiple plausible matches exist, return all relevant candidates.
- If no match exists, return `NOT_FOUND`.
- The tool is read-only.

#### Ambiguity example

For a request such as:

> How much pallet wrap do we have?

the tool must not arbitrarily select one product if multiple pallet-wrap variants exist.

The agent should instead receive the candidates and ask the user to clarify which product they mean.

## 6. Dock Tools

### 6.1 `list_dock_slots`

#### Purpose

View dock slots for the caller's assigned warehouse site.

#### Model-facing description

> List dock slots for the caller's assigned warehouse site and date. Use this tool to see available or booked slots. This tool only reads the dock schedule and does not create or modify bookings.

#### Parameters

| Parameter | Type | Required | Description                                |
| --------- | ---- | -------- | ------------------------------------------ |
| `date`    | date | Yes      | Date for which dock slots should be listed |
| `status`  | enum | No       | Filter by slot status                      |

Allowed values for `status`:

- `available`
- `booked`
- `all`

Default value: `all`

#### Behaviour

- Return only slots belonging to the caller's assigned site.
- Support filtering by availability status.
- Do not create, modify or cancel bookings.

### 6.2 `book_dock_slot`

#### Purpose

Book an available dock slot.

#### Model-facing description

> Book an available dock slot at the caller's assigned warehouse site. Use this tool only when the required date, slot and carrier are known. Booking changes warehouse schedule state and requires explicit confirmation. Do not book an already-booked slot.

#### Parameters

| Parameter      | Type    | Required | Description                           |
| -------------- | ------- | -------- | ------------------------------------- |
| `date`         | date    | Yes      | Date of the dock slot                 |
| `slot`         | string  | Yes      | Dock slot identifier                  |
| `carrier`      | string  | Yes      | Carrier associated with the booking   |
| `confirmation` | boolean | Yes      | Must be `true` to perform the booking |

#### Behaviour

- The site is obtained from trusted caller context.
- The requested slot must exist at the caller's site.
- The slot must currently be available.
- `carrier` is required.
- `confirmation` must be `true` before the booking is created.
- If confirmation is not provided, no state change occurs.
- If the slot is already booked, return `SLOT_ALREADY_BOOKED`.
- The error should guide the agent to select another available slot.

### 6.3 `cancel_dock_booking`

#### Purpose

Cancel an existing dock booking.

#### Model-facing description

> Cancel an existing dock booking at the caller's assigned warehouse site. Cancellation changes schedule state and requires explicit confirmation. Use this tool only when the user has identified the booking to cancel.

#### Parameters

| Parameter      | Type    | Required | Description                                |
| -------------- | ------- | -------- | ------------------------------------------ |
| `date`         | date    | Yes      | Date of the booking                        |
| `slot`         | string  | Yes      | Dock slot identifier                       |
| `confirmation` | boolean | Yes      | Must be `true` to perform the cancellation |

#### Behaviour

- The site is obtained from trusted caller context.
- The booking must exist at the caller's site.
- The slot must currently be booked.
- `confirmation` must be `true`.
- No state change occurs without confirmation.
- After successful cancellation, the slot becomes available.

## 7. Stock Change Tools

### 7.1 `correct_stock`

#### Purpose

Correct an incorrect recorded stock quantity.

#### Model-facing description

> Correct the recorded quantity for a specific SKU at the caller's assigned warehouse site. Stock corrections affect inventory records used for month-end counting, so explicit confirmation is required. Use this tool only when the SKU and corrected quantity are known.

#### Parameters

| Parameter            | Type                 | Required | Description                              |
| -------------------- | -------------------- | -------- | ---------------------------------------- |
| `sku`                | string               | Yes      | SKU whose quantity should be corrected   |
| `corrected_quantity` | non-negative integer | Yes      | New recorded quantity                    |
| `reason`             | string               | Yes      | Reason for the correction                |
| `confirmation`       | boolean              | Yes      | Must be `true` to perform the correction |

#### Behaviour

- The SKU must exist at the caller's assigned site.
- `corrected_quantity` must be zero or greater.
- `reason` is required.
- Explicit confirmation is required.
- No stock change occurs without confirmation.
- Cross-site access must be rejected.

### 7.2 `move_stock`

#### Purpose

Record the movement of stock from one bin to another.

#### Model-facing description

> Record a stock movement between bins at the caller's assigned warehouse site. Use this tool when stock has physically moved from one bin to another. This changes stock state and requires explicit confirmation.

#### Parameters

| Parameter      | Type             | Required | Description                            |
| -------------- | ---------------- | -------- | -------------------------------------- |
| `sku`          | string           | Yes      | SKU being moved                        |
| `from_bin`     | string           | Yes      | Current bin                            |
| `to_bin`       | string           | Yes      | Destination bin                        |
| `quantity`     | positive integer | Yes      | Quantity to move                       |
| `confirmation` | boolean          | Yes      | Must be `true` to perform the movement |

#### Behaviour

- The SKU must exist at the caller's assigned site.
- `quantity` must be greater than zero.
- `from_bin` must identify the stock's current bin.
- `to_bin` must be different from `from_bin`.
- The requested quantity must not exceed the available quantity.
- Explicit confirmation is required.
- No state change occurs without confirmation.
- Cross-site access must be rejected.

## 8. Exception Tools

### 8.1 `raise_exception`

#### Purpose

Create an exception for damaged or missing stock.

#### Model-facing description

> Create a warehouse exception for damaged or missing stock at the caller's assigned warehouse site. Use a valid exception category and provide a concise description of what happened. Include the related SKU when known. Creating an exception changes operational state and requires explicit confirmation.

#### Parameters

| Parameter      | Type    | Required | Description                            |
| -------------- | ------- | -------- | -------------------------------------- |
| `category`     | enum    | Yes      | Exception category                     |
| `description`  | string  | Yes      | Description of the issue               |
| `sku`          | string  | No       | Related SKU, when known                |
| `confirmation` | boolean | Yes      | Must be `true` to create the exception |

Allowed values for `category`:

- `damaged`
- `missing`

#### Behaviour

- `category` must use one of the allowed enum values.
- `description` is required.
- When supplied, the SKU must belong to the caller's assigned site.
- Explicit confirmation is required.
- The created exception must be associated with the caller's assigned site.

### 8.2 `close_exception`

#### Purpose

Close an existing exception after the issue has been resolved.

#### Model-facing description

> Close an existing warehouse exception at the caller's assigned warehouse site after the issue has been resolved. Provide a resolution note describing what was done. Closing an exception changes operational state and requires explicit confirmation.

#### Parameters

| Parameter         | Type    | Required | Description                           |
| ----------------- | ------- | -------- | ------------------------------------- |
| `exception_id`    | string  | Yes      | Exception to close                    |
| `resolution_note` | string  | Yes      | Description of the resolution         |
| `confirmation`    | boolean | Yes      | Must be `true` to close the exception |

#### Behaviour

- The exception must exist.
- The exception must belong to the caller's assigned site.
- The exception must not already be closed.
- `resolution_note` is required.
- Explicit confirmation is required.
- No state change occurs without confirmation.

## 9. Common Error Contract

All tool failures use a consistent structured error shape.

The response must contain:

- `ok`
- `error.code`
- `error.message`
- `error.field`
- `error.details`
- `error.suggested_action`

Example structure:

```text
{
  "ok": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human and model-readable explanation.",
    "field": "field_name",
    "details": {},
    "suggested_action": "What the agent should do next."
  }
}
```

### Error fields

| Field                    | Type           | Required | Description                           |
| ------------------------ | -------------- | -------- | ------------------------------------- |
| `ok`                     | boolean        | Yes      | Indicates that the operation failed   |
| `error.code`             | string         | Yes      | Machine-readable error category       |
| `error.message`          | string         | Yes      | Human/model-readable explanation      |
| `error.field`            | string or null | No       | Input field associated with the error |
| `error.details`          | object         | No       | Additional information                |
| `error.suggested_action` | string         | Yes      | Guidance for the agent                |

### Required error categories

The implementation must support clear error categories including:

- `INVALID_ARGUMENT`
- `NOT_FOUND`
- `SITE_ACCESS_DENIED`
- `CONFIRMATION_REQUIRED`
- `SLOT_ALREADY_BOOKED`
- `INSUFFICIENT_STOCK`
- `ALREADY_CLOSED`

Additional implementation-specific error codes may be added where required.

## 10. Confirmation Behaviour

Read-only tools execute without confirmation.

The following state-changing operations require explicit confirmation:

- `book_dock_slot`
- `cancel_dock_booking`
- `correct_stock`
- `move_stock`
- `raise_exception`
- `close_exception`

If `confirmation` is not `true`, the operation must not change state.

Instead, the tool must return a `CONFIRMATION_REQUIRED` response containing enough information for the agent to explain the proposed change to the user.

For example, a stock correction confirmation response should identify:

- the SKU
- the current quantity
- the proposed new quantity
- the reason for the change

The agent must not assume that a previous request automatically constitutes confirmation for the final state-changing call.

## 11. Ambiguous Lookup Behaviour

The toolkit must distinguish between an unambiguous lookup and an ambiguous lookup.

### Unambiguous lookup

If the search query produces one clear product match, return the product.

The agent should not unnecessarily ask the user for an SKU.

### Ambiguous lookup

If the search query produces multiple plausible products, return the candidates.

The agent must ask the user to clarify which candidate is intended before performing an operation that requires a specific SKU.

### Example

User:

> How many pallet wraps do we have?

Possible candidates may include:

- `SKU-8801` — Pallet wrap, 500mm clear
- `SKU-8802` — Pallet wrap, 500mm black

Agent response:

> We have two pallet-wrap products at this site: 500mm clear and 500mm black. Which one do you mean?

The agent must not guess.

## 12. Site-Scoping Behaviour

Site authorization is enforced by the toolkit.

For example, if the caller is assigned to:

`LEEDS-01`

the caller may access Leeds data but must not access:

- `READING-02`
- `GLASGOW-03`

A cross-site request must return:

`SITE_ACCESS_DENIED`

The toolkit must not rely on the AI agent to enforce this rule.

The toolkit must also permit valid same-site requests.

## 13. Changes from the Original Ops Request

The original Ops request is treated as a requirements document rather than a final API design.

### 13.1 `lookup` split into two tools

Original request:

`lookup`

Final design:

- `get_stock`
- `search_stock`

Reason:

Exact SKU lookup and approximate product-name search have different safety characteristics.

The supplied stock data contains similar product descriptions, so a single fuzzy lookup that returns one best match could confidently return the wrong item.

### 13.2 `check_dock` split into three tools

Original request:

`check_dock`

Final design:

- `list_dock_slots`
- `book_dock_slot`
- `cancel_dock_booking`

Reason:

Viewing dock availability is read-only, while booking and cancellation change warehouse state.

Separate tools make the distinction clear to the AI agent and allow different confirmation requirements.

### 13.3 `stock_change` split into two tools

Original request:

`stock_change`

Final design:

- `correct_stock`
- `move_stock`

Reason:

Correcting a quantity and moving stock between bins are separate warehouse operations with different parameters and validation rules.

Combining them would require the agent to choose between multiple unrelated behaviours through a single tool.

### 13.4 Confirmation added to state-changing operations

The Ops request did not define confirmation behaviour.

Confirmation is added because state-changing operations can affect operational records, and stock corrections specifically feed the month-end count.

### 13.5 Server-enforced site scoping added

The Ops requirements identify a previous incident where staff at one site could access another site's numbers.

The final design therefore enforces the caller's assigned site inside the toolkit rather than trusting a site parameter supplied by the agent.

### 13.6 Structured actionable errors added

The original `ERR_4001` style does not provide enough information for an agent or operator to correct the request.

The final design uses structured errors containing the failure reason and a suggested corrective action.

### 13.7 Ambiguity handling added

The Ops request did not define what should happen when a product-name search is uncertain.

The final design explicitly requires the agent to ask a clarification question when multiple plausible products are returned.

## 14. Acceptance Criteria

### Stock

- Exact SKU lookup returns the correct stock record.
- A zero-quantity stock record is treated as a valid record.
- Unambiguous product searches return the single matching product.
- Ambiguous product searches return multiple candidates instead of guessing.
- Stock searches are restricted to the caller's assigned site.

### Dock

- Available dock slots can be listed without confirmation.
- Bookings require explicit confirmation.
- An already-booked slot cannot be booked again.
- Booking conflicts return actionable errors.
- Cancellation requires explicit confirmation.
- Dock operations are restricted to the caller's assigned site.

### Stock Changes

- Stock corrections require explicit confirmation.
- Stock quantities cannot become negative.
- Stock movement requires a positive quantity.
- Stock movement cannot exceed available stock.
- Stock movement requires explicit confirmation.
- Stock-changing operations are restricted to the caller's assigned site.

### Exceptions

- Only supported exception categories are accepted.
- Raising an exception requires confirmation.
- Closing an exception requires confirmation.
- Closed exceptions cannot be closed again.
- Exceptions are restricted to the caller's assigned site.

### Validation and Safety

- Closed-set parameters are schema constrained.
- Invalid arguments are rejected.
- Cross-site access is rejected by the toolkit.
- Valid same-site access continues to work.
- State-changing operations cannot execute without confirmation.
- Errors follow the common actionable error shape.
- The agent can use error responses to correct failed calls.
- The agent asks a clarification question when the data is ambiguous.

### Agent Integration

- The MCP server can be registered with a real agent host.
- An agent can select the appropriate tool at runtime.
- The runtime demonstration includes normal read operations.
- The runtime demonstration includes state-changing operations.
- The runtime demonstration includes an ambiguous lookup where the agent asks for clarification.

## 15. Non-Goals

The project does not require integration with production warehouse-management systems.

The supplied:

- `stock_snapshot.csv`
- `dock_schedule.jsonl`

files may be used as the stub data source.

The primary objective is to demonstrate:

- agent-friendly MCP tool design
- schema validation
- safe state-changing operations
- confirmation handling
- site-level authorization
- ambiguity handling
- actionable errors
- automated testing
- runtime agent/tool selection

Production infrastructure, authentication systems, real warehouse integrations and production deployment are outside the scope of this case.
