from pathlib import Path

from warehouse_mcp.context import CallerContext
from warehouse_mcp.data_store import WarehouseDataStore
from warehouse_mcp.exceptions import (
    close_exception,
    raise_exception,
)


ROOT = Path(__file__).resolve().parents[1]

store = WarehouseDataStore(
    stock_file=ROOT / "data" / "stock_snapshot.csv",
    dock_file=ROOT / "data" / "dock_schedule.jsonl",
)


def test_raise_exception_requires_confirmation():
    context = CallerContext(
        caller_id="operator-001",
        assigned_site="LEEDS-01",
    )

    result = raise_exception(
        store,
        context,
        "damaged",
        "Pallet wrap roll damaged.",
        "SKU-8801",
        confirmation=False,
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "CONFIRMATION_REQUIRED"


def test_raise_exception_rejects_invalid_category():
    context = CallerContext(
        caller_id="operator-001",
        assigned_site="LEEDS-01",
    )

    result = raise_exception(
        store,
        context,
        "broken",
        "Pallet wrap roll damaged.",
        "SKU-8801",
        confirmation=True,
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "INVALID_ARGUMENT"


def test_raise_exception_requires_description():
    context = CallerContext(
        caller_id="operator-001",
        assigned_site="LEEDS-01",
    )

    result = raise_exception(
        store,
        context,
        "damaged",
        "",
        "SKU-8801",
        confirmation=True,
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "INVALID_ARGUMENT"


def test_raise_exception_valid_sku():
    context = CallerContext(
        caller_id="operator-001",
        assigned_site="LEEDS-01",
    )

    result = raise_exception(
        store,
        context,
        "damaged",
        "Pallet wrap roll damaged.",
        "SKU-8801",
        confirmation=True,
    )

    assert result["ok"] is True
    assert result["exception"]["category"] == "damaged"
    assert result["exception"]["sku"] == "SKU-8801"
    assert result["exception"]["site"] == "LEEDS-01"


def test_raise_exception_can_omit_sku():
    context = CallerContext(
        caller_id="operator-001",
        assigned_site="LEEDS-01",
    )

    result = raise_exception(
        store,
        context,
        "missing",
        "A package is missing from the receiving area.",
        None,
        confirmation=True,
    )

    assert result["ok"] is True
    assert result["exception"]["category"] == "missing"
    assert result["exception"]["sku"] is None


def test_raise_exception_cross_site_sku_is_rejected():
    context = CallerContext(
        caller_id="operator-001",
        assigned_site="LEEDS-01",
    )

    result = raise_exception(
        store,
        context,
        "damaged",
        "Item is damaged.",
        "SKU-8805",
        confirmation=True,
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "NOT_FOUND"


def test_close_exception_requires_confirmation():
    context = CallerContext(
        caller_id="operator-001",
        assigned_site="LEEDS-01",
    )

    result = close_exception(
        store,
        context,
        "EX-001",
        "Replacement stock received.",
        confirmation=False,
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "CONFIRMATION_REQUIRED"


def test_close_exception_requires_id():
    context = CallerContext(
        caller_id="operator-001",
        assigned_site="LEEDS-01",
    )

    result = close_exception(
        store,
        context,
        "",
        "Replacement stock received.",
        confirmation=True,
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "INVALID_ARGUMENT"


def test_close_exception_requires_resolution_note():
    context = CallerContext(
        caller_id="operator-001",
        assigned_site="LEEDS-01",
    )

    result = close_exception(
        store,
        context,
        "EX-001",
        "",
        confirmation=True,
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "INVALID_ARGUMENT"


def test_close_exception_valid_request():
    context = CallerContext(
        caller_id="operator-001",
        assigned_site="LEEDS-01",
    )

    result = close_exception(
        store,
        context,
        "EX-001",
        "Replacement stock received.",
        confirmation=True,
    )

    assert result["ok"] is True
    assert result["closure"]["exception_id"] == "EX-001"
    assert result["closure"]["site"] == "LEEDS-01"