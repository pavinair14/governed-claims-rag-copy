import asyncio
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from pydantic import BaseModel

from warehouse_mcp.confirm import Confirmations
from warehouse_mcp.context import SessionContext, StartupError, load_context
from warehouse_mcp.errors import ErrorCode, ToolError
from warehouse_mcp.models import (
    BookDockSlotInput,
    CancelDockBookingInput,
    CloseExceptionInput,
    CorrectStockInput,
    GetStockInput,
    ListDockSlotsInput,
    ListExceptionsInput,
    MoveStockInput,
    RaiseExceptionInput,
    SearchStockInput,
)
from warehouse_mcp.scope import Scope
from warehouse_mcp.store import Store
from warehouse_mcp.tools.dock import book_dock_slot, cancel_dock_booking, list_dock_slots
from warehouse_mcp.tools.exceptions import (
    close_exception,
    list_exceptions,
    raise_exception,
)
from warehouse_mcp.tools.stock import correct_stock, get_stock, move_stock, search_stock
from warehouse_mcp.validate import parse_args

INSTRUCTIONS = (
    "Kestrel warehouse tools. Your site is fixed by your session; no tool takes a site "
    "and you must never quote figures for another site. Tools starting READ-ONLY never "
    "change anything. Tools starting CHANGES STATE are two-step: the first call (no "
    "confirmation_token) changes nothing and returns CONFIRMATION_REQUIRED with a "
    "preview and a token; show the preview to the user, and only after they agree call "
    "again with the same arguments plus the token. Never confirm on the user's behalf. "
    "If a search returns several candidates, ask the user which one; never pick. "
    "A quantity of 0 is a valid answer. Never invent SKUs, bins, slots or IDs. "
    "Errors say what to do next: follow suggested_action and do not repeat an invalid call."
)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    model: type[BaseModel]
    example: dict[str, Any]
    handler: Callable[..., dict[str, Any]]
    read_only: bool = True
    destructive: bool = False


TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="get_stock",
        description=(
            "READ-ONLY. Get stock for one exact SKU (format SKU-1234) at the caller's own "
            "site: description, each bin location with quantity, and total. Use when the "
            "user gives a SKU, or after search_stock identified one product. A quantity "
            "of 0 is a valid result, not an error. Do not guess SKUs; for descriptions "
            "use search_stock."
        ),
        model=GetStockInput,
        example={"sku": "SKU-8801"},
        handler=get_stock,
    ),
    ToolSpec(
        name="search_stock",
        description=(
            "READ-ONLY. Search products at the caller's own site by description when the "
            "user does not know the SKU. Returns ALL plausible matches. If match_status "
            'is "single", the one product is returned with its quantity; answer directly. '
            'If it is "multiple", quantities are withheld: do NOT pick one; list the '
            "candidates and ask the user which they mean, then call get_stock with the "
            "chosen SKU. Never invent a SKU."
        ),
        model=SearchStockInput,
        example={"query": "pallet wrap"},
        handler=search_stock,
    ),
    ToolSpec(
        name="list_dock_slots",
        description=(
            "READ-ONLY. List dock slots at the caller's own site for one date, optionally "
            "filtered by status. Use to answer \"what's free\" and before booking or "
            "cancelling. Booked slots show their carrier. Never ask the user for a site."
        ),
        model=ListDockSlotsInput,
        example={"date": "2026-04-08"},
        handler=list_dock_slots,
    ),
    ToolSpec(
        name="list_exceptions",
        description=(
            "READ-ONLY. List exceptions raised at the caller's own site. Use to find an "
            "exception ID before closing one; never ask the user to type or remember an "
            "ID. Defaults to open exceptions."
        ),
        model=ListExceptionsInput,
        example={},
        handler=list_exceptions,
    ),
    ToolSpec(
        name="book_dock_slot",
        description=(
            "CHANGES STATE (requires confirmation). Book one available dock slot at the "
            "caller's own site. First call without confirmation_token returns a preview; "
            "show it to the user and only after they agree call again with the same "
            "arguments plus the returned confirmation_token. Never invent a slot; check "
            "list_dock_slots first."
        ),
        model=BookDockSlotInput,
        example={"date": "2026-04-08", "slot": "10:00", "carrier": "Northbound Freight"},
        handler=book_dock_slot,
        read_only=False,
    ),
    ToolSpec(
        name="cancel_dock_booking",
        description=(
            "CHANGES STATE (requires confirmation). Cancel an existing dock booking at "
            "the caller's own site, identified by date and slot (never by carrier). First "
            "call returns a preview that names the carrier; confirm with the user, then "
            "repeat with the returned confirmation_token."
        ),
        model=CancelDockBookingInput,
        example={"date": "2026-04-08", "slot": "12:00"},
        handler=cancel_dock_booking,
        read_only=False,
        destructive=True,
    ),
    ToolSpec(
        name="correct_stock",
        description=(
            "CHANGES STATE (requires confirmation). Correct the recorded quantity of one "
            "SKU in one bin at the caller's own site after a physical count. Feeds the "
            "month-end count. The preview shows old quantity, new quantity and "
            "difference; confirm all three with the user. Do NOT use this to record "
            "moving stock between bins: use move_stock."
        ),
        model=CorrectStockInput,
        example={
            "sku": "SKU-8802",
            "bin": "A-12-4",
            "corrected_quantity": 175,
            "reason": "recount",
        },
        handler=correct_stock,
        read_only=False,
        destructive=True,
    ),
    ToolSpec(
        name="move_stock",
        description=(
            "CHANGES STATE (requires confirmation). Record moving a quantity of one SKU "
            "from one bin to another bin at the caller's own site. Total stock does not "
            "change. Confirm SKU, source bin, destination bin and quantity with the user. "
            "Do not use to fix a wrong count: use correct_stock."
        ),
        model=MoveStockInput,
        example={
            "sku": "SKU-8801",
            "from_bin": "A-12-3",
            "to_bin": "A-13-1",
            "quantity": 20,
        },
        handler=move_stock,
        read_only=False,
    ),
    ToolSpec(
        name="raise_exception",
        description=(
            "CHANGES STATE (requires confirmation). Raise a damaged or missing-stock "
            'exception for one SKU at the caller\'s own site. Category must be "damaged" '
            'or "missing". Returns a server-generated exception ID. Confirm category, SKU '
            "and description with the user first. If the user has no SKU, use "
            "search_stock to find it."
        ),
        model=RaiseExceptionInput,
        example={"category": "damaged", "sku": "SKU-8801", "description": "torn pallet"},
        handler=raise_exception,
        read_only=False,
    ),
    ToolSpec(
        name="close_exception",
        description=(
            "CHANGES STATE (requires confirmation). Close an open exception at the "
            "caller's own site with a resolution note. Closing is final; there is no "
            "reopen. Use list_exceptions to get the ID; never invent one. Confirm the ID "
            "and note with the user first."
        ),
        model=CloseExceptionInput,
        example={"exception_id": "EX-001", "resolution_note": "replaced the pallet"},
        handler=close_exception,
        read_only=False,
        destructive=True,
    ),
]


def _to_mcp_tool(spec: ToolSpec) -> types.Tool:
    return types.Tool(
        name=spec.name,
        description=spec.description,
        input_schema=spec.model.model_json_schema(),
        annotations=types.ToolAnnotations(
            read_only_hint=spec.read_only,
            destructive_hint=spec.destructive,
        ),
    )


def _result(payload: dict[str, Any], *, is_error: bool) -> types.CallToolResult:
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=json.dumps(payload))],
        is_error=is_error,
    )


def create_server(ctx: SessionContext, store: Store | None = None) -> Server:
    scope = Scope(Store.load() if store is None else store, ctx)
    confirmations = Confirmations()
    by_name = {t.name: t for t in TOOLS}

    async def on_list_tools(_ctx, _params) -> types.ListToolsResult:
        return types.ListToolsResult(tools=[_to_mcp_tool(t) for t in TOOLS])

    async def on_call_tool(_ctx, params) -> types.CallToolResult:
        try:
            spec = by_name.get(params.name)
            if spec is None:
                raise ToolError(
                    ErrorCode.INVALID_ARGUMENT,
                    f"There is no tool called {params.name!r}.",
                    field="name",
                    details={"available_tools": sorted(by_name)},
                    suggested_action="Call one of the available tools.",
                )
            args = parse_args(
                spec.model, params.arguments, tool=spec.name, example=spec.example
            )
            if spec.read_only:
                payload = spec.handler(scope, args)
            else:
                payload = spec.handler(confirmations, scope, args)
            return _result(payload, is_error=False)
        except ToolError as err:
            return _result(err.to_envelope(), is_error=True)

    return Server(
        "kestrel-warehouse",
        version="0.1.0",
        instructions=INSTRUCTIONS,
        on_list_tools=on_list_tools,
        on_call_tool=on_call_tool,
    )


async def run() -> None:
    ctx = load_context()
    server = create_server(ctx)
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main() -> None:
    try:
        asyncio.run(run())
    except StartupError as exc:
        print(f"Startup refused: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()