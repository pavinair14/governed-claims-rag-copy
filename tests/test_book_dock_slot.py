import pytest

from warehouse_mcp.errors import ErrorCode, ToolError
from warehouse_mcp.models import BookDockSlotInput, ListDockSlotsInput
from warehouse_mcp.tools.dock import book_dock_slot, list_dock_slots

DATE = "2026-04-08"


def make_args(slot="10:00", carrier="Northbound Freight", token=None, date=DATE):
    return BookDockSlotInput(
        date=date, slot=slot, carrier=carrier, confirmation_token=token
    )


def preview(confirmations, scope, **kw):
    with pytest.raises(ToolError) as caught:
        book_dock_slot(confirmations, scope, make_args(**kw))
    assert caught.value.code == ErrorCode.CONFIRMATION_REQUIRED
    return caught.value


def fails_with(confirmations, scope, code, **kw):
    with pytest.raises(ToolError) as caught:
        book_dock_slot(confirmations, scope, make_args(**kw))
    assert caught.value.code == code
    return caught.value


def statuses(scope):
    result = list_dock_slots(scope, ListDockSlotsInput(date=DATE))
    return {s["slot"]: (s["status"], s["carrier"]) for s in result["slots"]}


def test_preview_describes_the_booking_and_changes_nothing(confirmations, make_scope, store):
    scope = make_scope("LEEDS-01")
    err = preview(confirmations, scope)

    assert err.details["proposed_action"] == (
        "Book the 10:00 dock slot on 2026-04-08 at LEEDS-01 for Northbound Freight."
    )
    assert statuses(scope)["10:00"] == ("available", None)
    assert store.audit == []


def test_confirmed_booking_is_applied_and_visible_to_a_later_read(
    confirmations, make_scope, store
):
    scope = make_scope("LEEDS-01")
    token = preview(confirmations, scope).details["confirmation_token"]

    result = book_dock_slot(confirmations, scope, make_args(token=token))

    assert result == {
        "ok": True,
        "site": "LEEDS-01",
        "applied": True,
        "date": DATE,
        "slot": "10:00",
        "status": "booked",
        "carrier": "Northbound Freight",
    }
    assert statuses(scope)["10:00"] == ("booked", "Northbound Freight")
    assert len(store.audit) == 1
    entry = store.audit[0]
    assert entry["action"] == "book_dock_slot"
    assert entry["before"] == {"status": "available", "carrier": None}
    assert entry["site"] == "LEEDS-01"


def test_the_example_call_in_the_preview_commits_successfully(confirmations, make_scope):
    scope = make_scope("LEEDS-01")
    example = preview(confirmations, scope).example_call

    book_dock_slot(confirmations, scope, BookDockSlotInput(**example["arguments"]))
    assert statuses(scope)["10:00"][0] == "booked"


def test_booked_slot_fails_at_preview_with_alternatives_and_no_token(
    confirmations, make_scope
):
    scope = make_scope("LEEDS-01")
    err = fails_with(confirmations, scope, ErrorCode.SLOT_ALREADY_BOOKED, slot="08:00")

    assert err.field == "slot"
    assert err.details["booked_carrier"] == "Northbound Freight"
    assert err.details["available_slots"] == ["06:00", "10:00", "14:00", "16:00"]
    assert err.example_call["arguments"]["slot"] == "06:00"
    assert confirmations.outstanding() == 0


def test_slot_booked_between_preview_and_commit_is_not_overwritten(
    confirmations, make_scope
):
    scope = make_scope("LEEDS-01")
    token = preview(confirmations, scope).details["confirmation_token"]

    taken = scope.dock_slot(DATE, "10:00")  # someone else books it in the meantime
    taken.status, taken.carrier = "booked", "Other Haulage"

    fails_with(
        confirmations, scope, ErrorCode.SLOT_ALREADY_BOOKED, token=token
    )
    assert statuses(scope)["10:00"] == ("booked", "Other Haulage")


def test_token_cannot_book_twice(confirmations, make_scope):
    scope = make_scope("LEEDS-01")
    token = preview(confirmations, scope).details["confirmation_token"]
    book_dock_slot(confirmations, scope, make_args(token=token))

    fails_with(confirmations, scope, ErrorCode.SLOT_ALREADY_BOOKED, token=token)


def test_token_for_one_slot_cannot_book_another(confirmations, make_scope):
    scope = make_scope("LEEDS-01")
    token = preview(confirmations, scope, slot="10:00").details["confirmation_token"]

    fails_with(
        confirmations, scope, ErrorCode.CONFIRMATION_INVALID, slot="14:00", token=token
    )
    assert statuses(scope)["14:00"] == ("available", None)
    assert statuses(scope)["10:00"] == ("available", None)


def test_unscheduled_date_is_not_found(confirmations, make_scope):
    err = fails_with(
        confirmations, make_scope("LEEDS-01"), ErrorCode.NOT_FOUND, date="2026-04-09"
    )
    assert err.details["scheduled_dates"] == [DATE]


def test_same_slot_time_is_a_different_slot_at_each_site(confirmations, make_scope):
    # Glasgow's 10:00 is booked; Leeds's 10:00 is free.
    fails_with(
        confirmations, make_scope("GLASGOW-03"), ErrorCode.SLOT_ALREADY_BOOKED, slot="10:00"
    )

    leeds = make_scope("LEEDS-01")
    token = preview(confirmations, leeds).details["confirmation_token"]
    book_dock_slot(confirmations, leeds, make_args(token=token))
    assert statuses(leeds)["10:00"][0] == "booked"


def test_booking_changes_only_the_callers_own_site(confirmations, make_scope):
    leeds = make_scope("LEEDS-01")
    token = preview(confirmations, leeds).details["confirmation_token"]
    book_dock_slot(confirmations, leeds, make_args(token=token))

    assert statuses(make_scope("READING-02"))["10:00"] == ("available", None)
    assert statuses(make_scope("GLASGOW-03"))["10:00"] == ("booked", "Northbound Freight")


def test_failed_calls_leave_no_audit_entry(confirmations, make_scope, store):
    scope = make_scope("LEEDS-01")
    fails_with(confirmations, scope, ErrorCode.SLOT_ALREADY_BOOKED, slot="08:00")
    fails_with(confirmations, scope, ErrorCode.CONFIRMATION_INVALID, token="bogus")
    assert store.audit == []