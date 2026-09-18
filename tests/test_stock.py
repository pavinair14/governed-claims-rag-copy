from pathlib import Path

from warehouse_mcp.context import CallerContext
from warehouse_mcp.data_store import WarehouseDataStore
from warehouse_mcp.stock import get_stock, search_stock


ROOT = Path(__file__).resolve().parents[1]

store = WarehouseDataStore(
    stock_file=ROOT / "data" / "stock_snapshot.csv",
    dock_file=ROOT / "data" / "dock_schedule.jsonl",
)


def test_get_stock_exact_sku():
    context = CallerContext(
        caller_id="operator-001",
        assigned_site="LEEDS-01",
    )

    result = get_stock(store, context, "SKU-8801")

    assert result["ok"] is True
    assert result["stock"]["sku"] == "SKU-8801"
    assert result["stock"]["quantity"] == 240


def test_get_stock_zero_quantity_is_valid():
    context = CallerContext(
        caller_id="operator-001",
        assigned_site="GLASGOW-03",
    )

    result = get_stock(store, context, "SKU-8809")

    assert result["ok"] is True
    assert result["stock"]["quantity"] == 0


def test_get_stock_not_found():
    context = CallerContext(
        caller_id="operator-001",
        assigned_site="LEEDS-01",
    )

    result = get_stock(store, context, "SKU-9999")

    assert result["ok"] is False
    assert result["error"]["code"] == "NOT_FOUND"


def test_get_stock_cross_site_is_denied():
    context = CallerContext(
        caller_id="operator-001",
        assigned_site="LEEDS-01",
    )

    result = get_stock(store, context, "SKU-8805")

    assert result["ok"] is False
    assert result["error"]["code"] == "SITE_ACCESS_DENIED"


def test_search_stock_returns_multiple_candidates():
    context = CallerContext(
        caller_id="operator-001",
        assigned_site="LEEDS-01",
    )

    result = search_stock(store, context, "pallet wrap")

    assert result["ok"] is True
    assert result["match_count"] == 2

    skus = {item["sku"] for item in result["matches"]}

    assert skus == {"SKU-8801", "SKU-8802"}


def test_search_stock_returns_single_candidate():
    context = CallerContext(
        caller_id="operator-001",
        assigned_site="LEEDS-01",
    )

    result = search_stock(store, context, "edge board")

    assert result["ok"] is True
    assert result["match_count"] == 1
    assert result["matches"][0]["sku"] == "SKU-8807"


def test_search_stock_empty_query():
    context = CallerContext(
        caller_id="operator-001",
        assigned_site="LEEDS-01",
    )

    result = search_stock(store, context, "")

    assert result["ok"] is False
    assert result["error"]["code"] == "INVALID_ARGUMENT"