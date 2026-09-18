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

> List dock s
