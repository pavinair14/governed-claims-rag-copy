from datetime import date
from pathlib import Path

from warehouse_mcp.context import CallerContext
from warehouse_mcp.data_store import WarehouseDataStore
from warehouse_mcp.dock import (
    book_dock_slot,
    cancel_dock_booking,
    list_dock_slots,
)


ROOT = Path(__file__).resolve().parents[1]

store = WarehouseDataStore(
    "data/stock_snapshot.csv",
    "data/dock_schedule.jsonl",
)

state = WarehouseState(
    store.load_stock(),
    store.load_dock_schedule(),
)


def test_list_available_leeds_slots():
    context = CallerContext(
        caller_id="operator-001",
        assigned_site="LEEDS-01",
    )

    result = list_dock_slots(
        state,
        context,
        date(2026, 4, 8),
        "available",
    )

    assert result["ok"] is True
    assert result["slot_count"] == 4


def test_list_booked_leeds_slots():
    context = CallerContext(
        caller_id="operator-001",
        assigned_site="LEEDS-01",
    )

    result = list_dock_slots(
        state,
        context,
        date(2026, 4, 8),
        "booked",
    )

    assert result["ok"] is True
    assert result["slot_count"] == 2


def test_invalid_status_is_rejected():
    context = CallerContext(
        caller_id="operator-001",
        assigned_site="LEEDS-01",
    )

    result = list_dock_slots(
        state,
        context,
        date(2026, 4, 8),
        "free",
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "INVALID_ARGUMENT"


def test_booking_requires_confirmation():
    context = CallerContext(
        caller_id="operator-001",
        assigned_site="LEEDS-01",
    )

    result = book_dock_slot(
        state,
        context,
        date(2026, 4, 8),
        "10:00",
        "Test Carrier",
        confirmation=False,
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "CONFIRMATION_REQUIRED"


def test_booking_already_booked_slot():
    context = CallerContext(
        caller_id="operator-001",
        assigned_site="LEEDS-01",
    )

    result = book_dock_slot(
        state,
        context,
        date(2026, 4, 8),
        "08:00",
        "Test Carrier",
        confirmation=True,
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "SLOT_ALREADY_BOOKED"


def test_booking_available_slot():
    context = CallerContext(
        caller_id="operator-001",
        assigned_site="LEEDS-01",
    )

    result = book_dock_slot(
        state,
        context,
        date(2026, 4, 8),
        "10:00",
        "Test Carrier",
        confirmation=True,
    )

    assert result["ok"] is True
    assert result["booking"]["status"] == "booked"
    assert result["booking"]["carrier"] == "Test Carrier"


def test_cancellation_requires_confirmation():
    context = CallerContext(
        caller_id="operator-001",
        assigned_site="LEEDS-01",
    )

    result = cancel_dock_booking(
        state,
        context,
        date(2026, 4, 8),
        "08:00",
        confirmation=False,
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "CONFIRMATION_REQUIRED"


def test_cancel_booked_slot():
    context = CallerContext(
        caller_id="operator-001",
        assigned_site="LEEDS-01",
    )

    result = cancel_dock_booking(
        state,
        context,
        date(2026, 4, 8),
        "08:00",
        confirmation=True,
    )

    assert result["ok"] is True
    assert result["cancellation"]["status"] == "available"
    assert result["cancellation"]["previous_carrier"] == "Northbound Freight"