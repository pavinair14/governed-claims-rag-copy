from typing import Any

from warehouse_mcp.confirm import Confirmations, execute_write
from warehouse_mcp.errors import ErrorCode, ToolError
from warehouse_mcp.models import BookDockSlotInput, ListDockSlotsInput
from warehouse_mcp.scope import Scope
from warehouse_mcp.store import DockSlot

from warehouse_mcp.models import (
    BookDockSlotInput,
    CancelDockBookingInput,
    ListDockSlotsInput,
)


def _day_or_not_found(scope: Scope, date_str: str) -> list[DockSlot]:
    slots = scope.dock_slots(date_str)
    if slots:
        return slots
    scheduled = scope.scheduled_dates()
    example_date = scheduled[0] if scheduled else "<YYYY-MM-DD>"
    raise ToolError(
        ErrorCode.NOT_FOUND,
        f"There is no dock schedule for {date_str} at your site.",
        field="date",
        details={"scheduled_dates": scheduled},
        suggested_action=(
            "Ask the user for a date that has a schedule, "
            "or use one of the scheduled dates."
        ),
        example_call={"tool": "list_dock_slots", "arguments": {"date": example_date}},
    )


def list_dock_slots(scope: Scope, args: ListDockSlotsInput) -> dict[str, Any]:
    date_str = args.date.isoformat()
    slots = _day_or_not_found(scope, date_str)

    if args.status != "all":
        slots = [s for s in slots if s.status == args.status]

    slots = sorted(slots, key=lambda s: s.slot)
    return {
        "ok": True,
        "site": scope.site,
        "date": date_str,
        "slots": [
            {"slot": s.slot, "status": s.status, "carrier": s.carrier} for s in slots
        ],
        "slot_count": len(slots),
    }


def _plan_book(scope: Scope, args: BookDockSlotInput) -> str:
    date_str = args.date.isoformat()
    day = _day_or_not_found(scope, date_str)
    slot = next((s for s in day if s.slot == args.slot), None)

    if slot is None:
        raise ToolError(
            ErrorCode.NOT_FOUND,
            f"There is no {args.slot} slot on {date_str} at your site.",
            field="slot",
            suggested_action="List the dock slots for that date and pick one of them.",
            example_call={"tool": "list_dock_slots", "arguments": {"date": date_str}},
        )

    if slot.status != "available":
        free = sorted(s.slot for s in day if s.status == "available")
        raise ToolError(
            ErrorCode.SLOT_ALREADY_BOOKED,
            f"The {args.slot} slot on {date_str} is already booked "
            f"(carrier: {slot.carrier}). Nothing was changed.",
            field="slot",
            details={"booked_carrier": slot.carrier, "available_slots": free},
            suggested_action=(
                "Offer the user one of the available slots, or ask for another date. "
                "Do not retry the same slot."
                if free
                else "There are no free slots that day. Ask the user for another date."
            ),
            example_call=(
                {
                    "tool": "book_dock_slot",
                    "arguments": {
                        "date": date_str,
                        "slot": free[0],
                        "carrier": args.carrier,
                    },
                }
                if free
                else None
            ),
        )

    return (
        f"Book the {args.slot} dock slot on {date_str} at {scope.site} "
        f"for {args.carrier}."
    )


def _apply_book(scope: Scope, args: BookDockSlotInput) -> dict[str, Any]:
    date_str = args.date.isoformat()
    slot = scope.dock_slot(date_str, args.slot)
    before = {"status": slot.status, "carrier": slot.carrier}
    slot.status = "booked"
    slot.carrier = args.carrier
    scope.record(
        {
            "action": "book_dock_slot",
            "date": date_str,
            "slot": args.slot,
            "before": before,
            "after": {"status": slot.status, "carrier": slot.carrier},
        }
    )
    return {
        "ok": True,
        "site": scope.site,
        "applied": True,
        "date": date_str,
        "slot": args.slot,
        "status": "booked",
        "carrier": args.carrier,
    }


def book_dock_slot(
    confirmations: Confirmations, scope: Scope, args: BookDockSlotInput
) -> dict[str, Any]:
    return execute_write(
        confirmations, scope, "book_dock_slot", args, _plan_book, _apply_book
    )


def _plan_cancel(scope: Scope, args: CancelDockBookingInput) -> str:
    date_str = args.date.isoformat()
    day = _day_or_not_found(scope, date_str)
    slot = next((s for s in day if s.slot == args.slot), None)

    if slot is None:
        raise ToolError(
            ErrorCode.NOT_FOUND,
            f"There is no {args.slot} slot on {date_str} at your site.",
            field="slot",
            suggested_action="List the dock slots for that date and pick one of them.",
            example_call={"tool": "list_dock_slots", "arguments": {"date": date_str}},
        )

    if slot.status != "booked":
        booked = sorted(s.slot for s in day if s.status == "booked")
        raise ToolError(
            ErrorCode.SLOT_NOT_BOOKED,
            f"The {args.slot} slot on {date_str} is not booked, so there is nothing "
            "to cancel. Nothing was changed.",
            field="slot",
            details={"booked_slots": booked},
            suggested_action=(
                "Ask the user which booked slot they mean. Do not retry this slot."
            ),
            example_call={
                "tool": "list_dock_slots",
                "arguments": {"date": date_str, "status": "booked"},
            },
        )

    return (
        f"Cancel the {args.slot} dock booking on {date_str} at {scope.site}, "
        f"currently held by {slot.carrier}. The carrier will lose this slot."
    )


def _apply_cancel(scope: Scope, args: CancelDockBookingInput) -> dict[str, Any]:
    date_str = args.date.isoformat()
    slot = scope.dock_slot(date_str, args.slot)
    before = {"status": slot.status, "carrier": slot.carrier}
    slot.status = "available"
    slot.carrier = None
    scope.record(
        {
            "action": "cancel_dock_booking",
            "date": date_str,
            "slot": args.slot,
            "before": before,
            "after": {"status": slot.status, "carrier": slot.carrier},
        }
    )
    return {
        "ok": True,
        "site": scope.site,
        "applied": True,
        "date": date_str,
        "slot": args.slot,
        "status": "available",
        "cancelled_carrier": before["carrier"],
    }


def cancel_dock_booking(
    confirmations: Confirmations, scope: Scope, args: CancelDockBookingInput
) -> dict[str, Any]:
    return execute_write(
        confirmations, scope, "cancel_dock_booking", args, _plan_cancel, _apply_cancel
    )