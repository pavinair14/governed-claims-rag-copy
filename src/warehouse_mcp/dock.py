from __future__ import annotations

from datetime import date
from typing import Any

from .context import CallerContext
from .data_store import WarehouseDataStore


VALID_DOCK_STATUSES = {
    "available",
    "booked",
    "all",
}


def _error(
    code: str,
    message: str,
    field: str | None = None,
    details: dict[str, Any] | None = None,
    suggested_action: str = "",
) -> dict[str, Any]:
    return {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            "field": field,
            "details": details or {},
            "suggested_action": suggested_action,
        },
    }


def list_dock_slots(
    store: WarehouseDataStore,
    context: CallerContext,
    requested_date: date,
    status: str = "all",
) -> dict[str, Any]:
    """List dock slots for the caller's assigned site."""

    if status not in VALID_DOCK_STATUSES:
        return _error(
            code="INVALID_ARGUMENT",
            message=f"Invalid dock status '{status}'.",
            field="status",
            details={
                "allowed_values": sorted(VALID_DOCK_STATUSES),
            },
            suggested_action=(
                "Use 'available', 'booked', or 'all'."
            ),
        )

    records = store.load_dock_schedule()

    matches = [
        record
        for record in records
        if record["site"] == context.assigned_site
        and record["date"] == requested_date.isoformat()
        and (status == "all" or record["status"] == status)
    ]

    return {
        "ok": True,
        "site": context.assigned_site,
        "date": requested_date.isoformat(),
        "slots": matches,
        "slot_count": len(matches),
    }


def book_dock_slot(
    store: WarehouseDataStore,
    context: CallerContext,
    requested_date: date,
    slot: str,
    carrier: str,
    confirmation: bool,
) -> dict[str, Any]:
    """Book an available dock slot after explicit confirmation."""

    if not confirmation:
        return _error(
            code="CONFIRMATION_REQUIRED",
            message=(
                f"Booking dock slot {slot} on "
                f"{requested_date.isoformat()} requires confirmation."
            ),
            field="confirmation",
            details={
                "site": context.assigned_site,
                "date": requested_date.isoformat(),
                "slot": slot,
                "carrier": carrier,
            },
            suggested_action=(
                "Ask the user to explicitly confirm the booking."
            ),
        )

    if not carrier.strip():
        return _error(
            code="INVALID_ARGUMENT",
            message="Carrier cannot be empty.",
            field="carrier",
            suggested_action="Provide the carrier name.",
        )

    records = store.load_dock_schedule()

    matches = [
        record
        for record in records
        if record["site"] == context.assigned_site
        and record["date"] == requested_date.isoformat()
        and record["slot"] == slot
    ]

    if not matches:
        return _error(
            code="NOT_FOUND",
            message=(
                f"No dock slot '{slot}' exists for "
                f"{requested_date.isoformat()} at "
                f"{context.assigned_site}."
            ),
            field="slot",
            suggested_action=(
                "Use list_dock_slots to inspect valid dock slots."
            ),
        )

    record = matches[0]

    if record["status"] == "booked":
        return _error(
            code="SLOT_ALREADY_BOOKED",
            message=(
                f"Dock slot '{slot}' on "
                f"{requested_date.isoformat()} is already booked."
            ),
            field="slot",
            details={
                "existing_carrier": record["carrier"],
            },
            suggested_action=(
                "Choose an available slot instead."
            ),
        )

    record["status"] = "booked"
    record["carrier"] = carrier.strip()

    return {
        "ok": True,
        "booking": {
            "site": record["site"],
            "date": record["date"],
            "slot": record["slot"],
            "status": record["status"],
            "carrier": record["carrier"],
        },
    }


def cancel_dock_booking(
    store: WarehouseDataStore,
    context: CallerContext,
    requested_date: date,
    slot: str,
    confirmation: bool,
) -> dict[str, Any]:
    """Cancel an existing dock booking after explicit confirmation."""

    if not confirmation:
        return _error(
            code="CONFIRMATION_REQUIRED",
            message=(
                f"Cancelling dock slot {slot} on "
                f"{requested_date.isoformat()} requires confirmation."
            ),
            field="confirmation",
            details={
                "site": context.assigned_site,
                "date": requested_date.isoformat(),
                "slot": slot,
            },
            suggested_action=(
                "Ask the user to explicitly confirm the cancellation."
            ),
        )

    records = store.load_dock_schedule()

    matches = [
        record
        for record in records
        if record["site"] == context.assigned_site
        and record["date"] == requested_date.isoformat()
        and record["slot"] == slot
    ]

    if not matches:
        return _error(
            code="NOT_FOUND",
            message=(
                f"No dock slot '{slot}' exists for "
                f"{requested_date.isoformat()} at "
                f"{context.assigned_site}."
            ),
            field="slot",
            suggested_action=(
                "Use list_dock_slots to inspect valid dock slots."
            ),
        )

    record = matches[0]

    if record["status"] == "available":
        return _error(
            code="NOT_FOUND",
            message=(
                f"Dock slot '{slot}' is not currently booked."
            ),
            field="slot",
            suggested_action=(
                "Choose a currently booked slot to cancel."
            ),
        )

    previous_carrier = record["carrier"]

    record["status"] = "available"
    record["carrier"] = None

    return {
        "ok": True,
        "cancellation": {
            "site": record["site"],
            "date": record["date"],
            "slot": record["slot"],
            "status": record["status"],
            "previous_carrier": previous_carrier,
        },
    }