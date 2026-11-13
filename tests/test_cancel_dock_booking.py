import pytest

from warehouse_mcp.errors import ErrorCode, ToolError
from warehouse_mcp.models import (
    BookDockSlotInput,
    CancelDockBookingInput,
    ListDockSlotsInput,
)
from warehouse_mcp.tools.dock import book_dock_slot, cancel_dock_booking, list_dock_slots

DATE = "2026-04-08"


def make_args(slot="12:00", token=None, date=DATE):
    return CancelDockBookingInput(date=date, slot=slot, confirmation_token=token)


def preview(confirmations, scope, **kw):
    with pytest.raises(ToolError) as caught:
        cancel_dock_booking(confirmations, scope, make_args(**kw))
    assert caught.value.code == ErrorCode.CONFIRMATION_REQUIRED
    return caught.value


def fails_with(confirmations, scope, code, **kw):
    with pytest.raises(ToolError) as caught:
        cancel_dock_booking(confirmations, scope, make_args(**kw))
    assert caught.value.code == code
    return caught.value


def statuses(scope):
    result = list_dock_slots(scope, ListDockSlotsInput(date=DATE))
    return {s["slot"]: (s["status"], s["carrier"]) for s in result["slots"]}


def test_preview_names_the_carrier_and_changes_nothing(confirmations, make_scope, store):
    scope = make_scope("LEEDS-01")
    err = preview(confirmations, scope)

    assert err.details["proposed_action"] == (
        "Cancel the 12:00 dock booking on 2026-04-08 at LEEDS-01, currently held by "
        "Northbound Freight. The carrier will lose this slot."
    )
    assert statuses(scope)["12:00"] == ("booked", "Northbound Freight")
    assert store.audit == []


def test_confirmed_cancellation_frees_the_slot(confirmations, make_scope, store):
    scope = make_scope("LEEDS-01")
    token = preview(confirmations, scope).details["confirmation_token"]

    result = cancel_dock_booking(confirmations, scope, make_args(token=token))

    assert result == {
        "ok": True,
        "site": "LEEDS-01",
        "applied": True,
        "date": DATE,
        "slot": "12:00",
        "status": "available",
        "cancelled_carrier": "Northbound Freight",
    }
    assert statuses(scope)["12:00"] == ("available", None)
    assert len(store.audit) == 1
    assert store.audit[0]["before"] == {"status": "booked", "carrier": "Northbound Freight"}


def test_a_cancelled_slot_can_be_booked_again(confirmations, make_scope):
    scope = make_scope("LEEDS-01")
    token = preview(confirmations, scope).details["confirmation_token"]
    cancel_dock_booking(confirmations, scope, make_args(token=token))

    with pytest.raises(ToolError) as caught:
        book_dock_slot(
            confirmations,
            scope,
            BookDockSlotInput(date=DATE, slot="12:00", carrier="Other Haulage"),
        )
    book_token = caught.value.details["confirmation_token"]
    book_dock_slot(
        confirmations,
        scope,
        BookDockSlotInput(
            date=DATE, slot="12:00", carrier="Other Haulage", confirmation_token=book_token
        ),
    )
    assert statuses(scope)["12:00"] == ("booked", "Other Haulage")


def test_cancelling_an_available_slot_fails_at_preview_with_no_token(
    confirmations, make_scope, store
):
    scope = make_scope("LEEDS-01")
    err = fails_with(confirmations, scope, ErrorCode.SLOT_NOT_BOOKED, slot="10:00")

    assert err.field == "slot"
    assert err.details["booked_slots"] == ["08:00", "12:00"]
    assert err.example_call["arguments"] == {"date": DATE, "status": "booked"}
    assert confirmations.outstanding() == 0
    assert store.audit == []


def test_booking_cancelled_between_preview_and_commit_is_not_double_cancelled(
    confirmations, make_scope
):
    scope = make_scope("LEEDS-01")
    token = preview(confirmations, scope).details["confirmation_token"]

    slot = scope.dock_slot(DATE, "12:00")  # someone else cancels it first
    slot.status, slot.carrier = "available", None

    fails_with(confirmations, scope, ErrorCode.SLOT_NOT_BOOKED, token=token)


def test_a_different_booking_in_the_same_slot_is_not_cancelled_by_an_old_token(
    confirmations, make_scope
):
    scope = make_scope("LEEDS-01")
    token = preview(confirmations, scope).details["confirmation_token"]

    slot = scope.dock_slot(DATE, "12:00")  # now held by someone the user never saw
    slot.carrier = "Other Haulage"

    fails_with(confirmations, scope, ErrorCode.CONFIRMATION_INVALID, token=token)
    assert statuses(scope)["12:00"] == ("booked", "Other Haulage")


def test_token_for_one_slot_cannot_cancel_another(confirmations, make_scope):
    scope = make_scope("LEEDS-01")
    token = preview(confirmations, scope, slot="12:00").details["confirmation_token"]

    fails_with(
        confirmations, scope, ErrorCode.CONFIRMATION_INVALID, slot="08:00", token=token
    )
    assert statuses(scope)["08:00"] == ("booked", "Northbound Freight")


def test_unscheduled_date_is_not_found(confirmations, make_scope):
    err = fails_with(
        confirmations, make_scope("LEEDS-01"), ErrorCode.NOT_FOUND, date="2026-04-09"
    )
    assert err.details["scheduled_dates"] == [DATE]


def test_cancelling_only_ever_touches_the_callers_own_site(confirmations, make_scope):
    # Glasgow's 10:00 is booked; Leeds's 10:00 is not, so Leeds cannot cancel it.
    fails_with(
        confirmations, make_scope("LEEDS-01"), ErrorCode.SLOT_NOT_BOOKED, slot="10:00"
    )
    assert statuses(make_scope("GLASGOW-03"))["10:00"] == ("booked", "Northbound Freight")

    leeds = make_scope("LEEDS-01")
    token = preview(confirmations, leeds).details["confirmation_token"]
    cancel_dock_booking(confirmations, leeds, make_args(token=token))
    assert statuses(make_scope("READING-02"))["14:00"] == ("booked", "Northbound Freight")
    assert statuses(make_scope("GLASGOW-03"))["10:00"] == ("booked", "Northbound Freight")


def test_failed_calls_leave_no_audit_entry(confirmations, make_scope, store):
    scope = make_scope("LEEDS-01")
    fails_with(confirmations, scope, ErrorCode.SLOT_NOT_BOOKED, slot="10:00")
    fails_with(confirmations, scope, ErrorCode.CONFIRMATION_INVALID, token="bogus")
    assert store.audit == []