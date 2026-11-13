from typing import Any

from warehouse_mcp.errors import ErrorCode, ToolError
from warehouse_mcp.models import GetStockInput, SearchStockInput
from warehouse_mcp.scope import Scope
from warehouse_mcp.search import match_skus
from warehouse_mcp.store import StockRow


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