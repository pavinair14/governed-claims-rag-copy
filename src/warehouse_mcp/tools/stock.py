from typing import Any

from warehouse_mcp.confirm import Confirmations, execute_write
from warehouse_mcp.errors import ErrorCode, ToolError
from warehouse_mcp.models import CorrectStockInput, GetStockInput, SearchStockInput
from warehouse_mcp.scope import Scope, site_of_bin
from warehouse_mcp.search import match_skus
from warehouse_mcp.store import StockRow

from warehouse_mcp.models import (
    CorrectStockInput,
    GetStockInput,
    MoveStockInput,
    SearchStockInput,
)


def _stock_view(rows: list[StockRow]) -> dict[str, Any]:
    first = rows[0]
    return {
        "sku": first.sku,
        "description": first.description,
        "unit": first.unit,
        "locations": [{"bin": r.bin, "quantity": r.quantity} for r in rows],
        "total_quantity": sum(r.quantity for r in rows),
    }


def get_stock(scope: Scope, args: GetStockInput) -> dict[str, Any]:
    rows = scope.rows_for_sku(args.sku)
    return {"ok": True, "site": scope.site, **_stock_view(rows)}


def search_stock(scope: Scope, args: SearchStockInput) -> dict[str, Any]:
    own_rows = scope.stock_rows()
    skus = match_skus(own_rows, args.query)

    if not skus:
        raise ToolError(
            ErrorCode.NOT_FOUND,
            f"No product at your site matched {args.query!r}.",
            field="query",
            details={"query": args.query},
            suggested_action=(
                "Try fewer or different words (every word must appear in the "
                "description), or ask the user for the SKU."
            ),
            example_call={
                "tool": "search_stock",
                "arguments": {"query": "<one or two key words>"},
            },
        )

    if len(skus) == 1:
        rows = [r for r in own_rows if r.sku == skus[0]]
        return {
            "ok": True,
            "site": scope.site,
            "match_status": "single",
            "matches": [_stock_view(rows)],
        }

    descriptions = {r.sku: r.description for r in own_rows}
    return {
        "ok": True,
        "site": scope.site,
        "match_status": "multiple",
        "matches": [{"sku": s, "description": descriptions[s]} for s in skus],
        "next_step": (
            "Ask the user which product they mean, then call get_stock with that SKU."
        ),
    }

def _plan_correct(scope: Scope, args: CorrectStockInput) -> str:
    rows = scope.rows_for_sku(args.sku)  # NOT_FOUND or SITE_ACCESS_DENIED

    owner = site_of_bin(args.bin)
    if owner is not None and owner != scope.site:
        scope.require_own_bin(args.bin)  # raises SITE_ACCESS_DENIED

    row = next((r for r in rows if r.bin == args.bin), None)
    if row is None:
        bins = [r.bin for r in rows]
        raise ToolError(
            ErrorCode.NOT_FOUND,
            f"{args.sku} is not held in bin {args.bin} at your site.",
            field="bin",
            details={"bins_holding_sku": bins},
            suggested_action=(
                "Use one of the bins that hold this SKU, or ask the user which bin "
                "they counted."
            ),
            example_call={
                "tool": "correct_stock",
                "arguments": {
                    "sku": args.sku,
                    "bin": bins[0],
                    "corrected_quantity": args.corrected_quantity,
                    "reason": args.reason,
                },
            },
        )

    if args.corrected_quantity == row.quantity:
        raise ToolError(
            ErrorCode.INVALID_ARGUMENT,
            f"The recorded quantity of {args.sku} in bin {args.bin} is already "
            f"{row.quantity}, so there is nothing to correct. Nothing was changed.",
            field="corrected_quantity",
            details={"recorded_quantity": row.quantity},
            suggested_action=(
                "Tell the user the record already matches their count, and ask "
                "whether they meant a different figure."
            ),
        )

    difference = args.corrected_quantity - row.quantity
    return (
        f"Correct the recorded quantity of {args.sku} ({row.description}) in bin "
        f"{args.bin} at {scope.site} from {row.quantity} to {args.corrected_quantity} "
        f"{row.unit} (difference {difference:+d}). Reason: {args.reason}. "
        "This feeds the month-end stock count."
    )


def _apply_correct(scope: Scope, args: CorrectStockInput) -> dict[str, Any]:
    row = next(r for r in scope.rows_for_sku(args.sku) if r.bin == args.bin)
    before = row.quantity
    row.quantity = args.corrected_quantity
    scope.record(
        {
            "action": "correct_stock",
            "sku": args.sku,
            "bin": args.bin,
            "before": {"quantity": before},
            "after": {"quantity": row.quantity},
            "reason": args.reason,
        }
    )
    return {
        "ok": True,
        "site": scope.site,
        "applied": True,
        "sku": args.sku,
        "bin": args.bin,
        "unit": row.unit,
        "previous_quantity": before,
        "corrected_quantity": row.quantity,
        "difference": row.quantity - before,
        "reason": args.reason,
    }


def correct_stock(
    confirmations: Confirmations, scope: Scope, args: CorrectStockInput
) -> dict[str, Any]:
    return execute_write(
        confirmations, scope, "correct_stock", args, _plan_correct, _apply_correct
    )

def _plan_move(scope: Scope, args: MoveStockInput) -> str:
    rows = scope.rows_for_sku(args.sku)  # NOT_FOUND or SITE_ACCESS_DENIED

    if args.from_bin == args.to_bin:
        raise ToolError(
            ErrorCode.INVALID_ARGUMENT,
            f"The source and destination bin are both {args.from_bin}. "
            "Nothing was changed.",
            field="to_bin",
            suggested_action="Ask the user which bin the stock is moving to.",
        )

    scope.require_own_bin(args.from_bin, "from_bin")
    scope.require_own_bin(args.to_bin, "to_bin")

    src = next((r for r in rows if r.bin == args.from_bin), None)
    if src is None:
        bins = [r.bin for r in rows]
        raise ToolError(
            ErrorCode.NOT_FOUND,
            f"{args.sku} is not held in bin {args.from_bin} at your site.",
            field="from_bin",
            details={"bins_holding_sku": bins},
            suggested_action=(
                "Use one of the bins that hold this SKU, or ask the user which bin "
                "the stock is in now."
            ),
            example_call={
                "tool": "move_stock",
                "arguments": {
                    "sku": args.sku,
                    "from_bin": bins[0],
                    "to_bin": args.to_bin,
                    "quantity": args.quantity,
                },
            },
        )

    if args.quantity > src.quantity:
        raise ToolError(
            ErrorCode.INSUFFICIENT_STOCK,
            f"Bin {args.from_bin} holds {src.quantity} of {args.sku}, so "
            f"{args.quantity} cannot be moved. Nothing was changed.",
            field="quantity",
            details={"available": src.quantity, "requested": args.quantity},
            suggested_action=(
                "Ask the user whether to move the available quantity instead, or "
                "whether the recorded count is wrong (a count correction is a "
                "different action). Do not retry the same quantity."
            ),
            example_call=(
                {
                    "tool": "move_stock",
                    "arguments": {
                        "sku": args.sku,
                        "from_bin": args.from_bin,
                        "to_bin": args.to_bin,
                        "quantity": src.quantity,
                    },
                }
                if src.quantity > 0
                else None
            ),
        )

    dest = next((r for r in rows if r.bin == args.to_bin), None)
    dest_before = dest.quantity if dest else 0
    total = sum(r.quantity for r in rows)
    text = (
        f"Move {args.quantity} {src.unit} of {args.sku} ({src.description}) from bin "
        f"{args.from_bin} to bin {args.to_bin} at {scope.site}. Bin {args.from_bin} "
        f"will go from {src.quantity} to {src.quantity - args.quantity}; bin "
        f"{args.to_bin} will go from {dest_before} to {dest_before + args.quantity}. "
        f"Total stock stays at {total}."
    )
    if dest is None:
        text += f" Bin {args.to_bin} does not currently hold this SKU."
    return text


def _apply_move(scope: Scope, args: MoveStockInput) -> dict[str, Any]:
    rows = scope.rows_for_sku(args.sku)
    src = next(r for r in rows if r.bin == args.from_bin)
    dest = next((r for r in rows if r.bin == args.to_bin), None)

    held = src.quantity
    dest_before = dest.quantity if dest else 0
    if dest is None:
        dest = StockRow(
            sku=src.sku,
            description=src.description,
            site=src.site,
            bin=args.to_bin,
            quantity=0,
            unit=src.unit,
        )
        scope.add_stock_row(dest)

    src.quantity -= args.quantity
    dest.quantity += args.quantity
    if src.quantity == 0:
        scope.remove_stock_row(src)

    scope.record(
        {
            "action": "move_stock",
            "sku": args.sku,
            "from_bin": args.from_bin,
            "to_bin": args.to_bin,
            "quantity": args.quantity,
            "before": {args.from_bin: held, args.to_bin: dest_before},
            "after": {args.from_bin: src.quantity, args.to_bin: dest.quantity},
        }
    )
    return {
        "ok": True,
        "site": scope.site,
        "applied": True,
        "sku": args.sku,
        "unit": src.unit,
        "from_bin": args.from_bin,
        "to_bin": args.to_bin,
        "quantity_moved": args.quantity,
        "from_bin_quantity": src.quantity,
        "to_bin_quantity": dest.quantity,
        "total_quantity": sum(r.quantity for r in scope.rows_for_sku(args.sku)),
    }


def move_stock(
    confirmations: Confirmations, scope: Scope, args: MoveStockInput
) -> dict[str, Any]:
    return execute_write(
        confirmations, scope, "move_stock", args, _plan_move, _apply_move
    )