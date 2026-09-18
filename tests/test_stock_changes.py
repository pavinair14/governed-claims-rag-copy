from pathlib import Path

from warehouse_mcp.context import CallerContext
from warehouse_mcp.data_store import WarehouseDataStore
from warehouse_mcp.stock_changes import (
    correct_stock,
    move_stock,
)


ROOT = Path(__file__).resolve().parents[1]

store = WarehouseDataStore(
    stock_file=ROOT / "data" / "stock_snapshot.csv",
    dock_file=ROOT / "data" / "dock_schedule.jsonl",
)


def test_correction_requires_confirmation():
    context = CallerContext(
        caller_id="operator-001",
        assigned_site="LEEDS-01",
    )

    result = correct_stock(
        store,
        context,
        "SKU-8801",
        250,
        "Physical recount",
        confirmation=False,
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "CONFIRMATION_REQUIRED"


def test_correction_accepts_zero():
    context = CallerContext(
        caller_id="operator-001",
        assigned_site="LEEDS-01",
    )

    result = correct_stock(
        store,
        context,
        "SKU-8801",
        0,
        "Physical recount found no stock",
        confirmation=True,
    )

    assert result["ok"] is True
    assert result["correction"]["corrected_quantity"] == 0


def test_correction_requires_reason():
    context = CallerContext(
        caller_id="operator-001",
        assigned_site="LEEDS-01",
    )

    result = correct_stock(
        store,
        context,
        "SKU-8801",
        250,
        "",
        confirmation=True,
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "INVALID_ARGUMENT"


def test_correction_negative_quantity_rejected():
    context = CallerContext(
        caller_id="operator-001",
        assigned_site="LEEDS-01",
    )

    result = correct_stock(
        store,
        context,
        "SKU-8801",
        -1,
        "Invalid count correction",
        confirmation=True,
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "INVALID_ARGUMENT"


def test_correction_cross_site_is_not_found():
    context = CallerContext(
        caller_id="operator-001",
        assigned_site="LEEDS-01",
    )

    result = correct_stock(
        store,
        context,
        "SKU-8805",
        100,
        "Physical recount",
        confirmation=True,
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "NOT_FOUND"


def test_move_requires_confirmation():
    context = CallerContext(
        caller_id="operator-001",
        assigned_site="LEEDS-01",
    )

    result = move_stock(
        store,
        context,
        "SKU-8801",
        "A-01-1",
        "B-01-1",
        20,
        confirmation=False,
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "CONFIRMATION_REQUIRED"


def test_move_requires_positive_quantity():
    context = CallerContext(
        caller_id="operator-001",
        assigned_site="LEEDS-01",
    )

    result = move_stock(
        store,
        context,
        "SKU-8801",
        "A-01-1",
        "B-01-1",
        0,
        confirmation=True,
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "INVALID_ARGUMENT"


def test_move_rejects_same_bin():
    context = CallerContext(
        caller_id="operator-001",
        assigned_site="LEEDS-01",
    )

    result = move_stock(
        store,
        context,
        "SKU-8801",
        "A-01-1",
        "A-01-1",
        20,
        confirmation=True,
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "INVALID_ARGUMENT"


def test_move_rejects_insufficient_stock():
    context = CallerContext(
        caller_id="operator-001",
        assigned_site="LEEDS-01",
    )

    result = move_stock(
        store,
        context,
        "SKU-8801",
        "A-01-1",
        "B-01-1",
        9999,
        confirmation=True,
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "INSUFFICIENT_STOCK"


def test_move_valid_stock():
    context = CallerContext(
        caller_id="operator-001",
        assigned_site="LEEDS-01",
    )

    result = move_stock(
        store,
        context,
        "SKU-8801",
        "A-01-1",
        "B-01-1",
        20,
        confirmation=True,
    )

    assert result["ok"] is True
    assert result["movement"]["quantity"] == 20
    assert result["movement"]["from_bin"] == "A-01-1"
    assert result["movement"]["to_bin"] == "B-01-1"