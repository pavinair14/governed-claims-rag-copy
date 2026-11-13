import pytest

from warehouse_mcp.context import SITES
from warehouse_mcp.errors import ErrorCode, ToolError
from warehouse_mcp.models import ListDockSlotsInput
from warehouse_mcp.tools.dock import list_dock_slots


def call(scope, date="2026-04-08", status="all"):
    return list_dock_slots(scope, ListDockSlotsInput(date=date, status=status))


def test_all_slots_for_own_site(make_scope):
    result = call(make_scope("LEEDS-01"))

    assert result["ok"] is True
    assert result["site"] == "LEEDS-01"
    assert result["date"] == "2026-04-08"
    assert result["slot_count"] == 6
    assert [s["slot"] for s in result["slots"]] == [
        "06:00", "08:00", "10:00", "12:00", "14:00", "16:00",
    ]


def test_available_filter(make_scope):
    result = call(make_scope("LEEDS-01"), status="available")
    assert [s["slot"] for s in result["slots"]] == ["06:00", "10:00", "14:00", "16:00"]
    assert all(s["carrier"] is None for s in result["slots"])


def test_booked_filter_shows_the_carrier(make_scope):
    result = call(make_scope("LEEDS-01"), status="booked")
    assert result["slots"] == [
        {"slot": "08:00", "status": "booked", "carrier": "Northbound Freight"},
        {"slot": "12:00", "status": "booked", "carrier": "Northbound Freight"},
    ]


@pytest.mark.parametrize(
    "site,expected_booked",
    [
        ("LEEDS-01", ["08:00", "12:00"]),
        ("READING-02", ["06:00", "14:00"]),
        ("GLASGOW-03", ["10:00"]),
    ],
)
def test_each_site_sees_only_its_own_bookings(site, expected_booked, make_scope):
    result = call(make_scope(site), status="booked")
    assert [s["slot"] for s in result["slots"]] == expected_booked
    assert result["site"] == site


def test_same_slot_time_differs_between_sites(make_scope):
    leeds_0800 = next(s for s in call(make_scope("LEEDS-01"))["slots"] if s["slot"] == "08:00")
    reading_0800 = next(s for s in call(make_scope("READING-02"))["slots"] if s["slot"] == "08:00")
    assert leeds_0800["status"] == "booked"
    assert reading_0800["status"] == "available"


def test_empty_filter_result_is_a_success(make_scope, store):
    for slot in store.docks:
        slot.status = "available"
        slot.carrier = None
    result = call(make_scope("LEEDS-01"), status="booked")
    assert result["ok"] is True
    assert result["slots"] == []
    assert result["slot_count"] == 0


@pytest.mark.parametrize("site", SITES)
def test_unscheduled_date_is_not_found_with_the_valid_dates(site, make_scope):
    with pytest.raises(ToolError) as caught:
        call(make_scope(site), date="2026-04-09")

    err = caught.value
    assert err.code == ErrorCode.NOT_FOUND
    assert err.field == "date"
    assert err.details["scheduled_dates"] == ["2026-04-08"]
    assert err.example_call["arguments"]["date"] == "2026-04-08"