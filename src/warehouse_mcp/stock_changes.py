from __future__ import annotations

from typing import Any

from .context import CallerContext
from .data_store import WarehouseDataStore


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


def correct_stock(
    store: WarehouseDataStore,
    context: CallerContext,
    sku: str,
    corrected_quantity: int,
    reason: str,
    confirmation: bool,
) -> dict[str, Any]:
    """Correct the recorded quantity for a SKU."""

    if not confirmation:
        return _error(
            code="CONFIRMATION_REQUIRED",
            message=(
                f"Correcting stock for '{sku}' requires confirmation."
            ),
            field="confirmation",
            details={
                "sku": sku,
                "corrected_quantity": corrected_quantity,
                "reason": reason,
            },
            suggested_action=(
                "Ask the user to explicitly confirm the correction."
            ),
        )

    if corrected_quantity < 0:
        return _error(
            code="INVALID_ARGUMENT",
            message="Corrected quantity cannot be negative.",
            field="corrected_quantity",
            suggested_action=(
                "Provide a quantity of zero or greater."
            ),
        )

    if not reason.strip():
        return _error(
            code="INVALID_ARGUMENT",
            message="A reason is required for a stock correction.",
            field="reason",
            suggested_action=(
                "Provide the reason for the stock correction."
            ),
        )

    records = store.load_stock()

    matches = [
        record
        for record in records
        if record["sku"].strip().upper() == sku.strip().upper()
        and record["site"] == context.assigned_site
    ]

    if not matches:
        return _error(
            code="NOT_FOUND",
            message=(
                f"SKU '{sku}' was not found at "
                f"{context.assigned_site}."
            ),
            field="sku",
            suggested_action=(
                "Check the SKU and ensure it belongs to your assigned site."
            ),
        )

    record = matches[0]
    previous_quantity = int(record["quantity"])

    return {
        "ok": True,
        "correction": {
            "sku": record["sku"],
            "site": record["site"],
            "previous_quantity": previous_quantity,
            "corrected_quantity": corrected_quantity,
            "unit": record["unit"],
            "reason": reason.strip(),
            "confirmed": True,
        },
    }


def move_stock(
    store: WarehouseDataStore,
    context: CallerContext,
    sku: str,
    from_bin: str,
    to_bin: str,
    quantity: int,
    confirmation: bool,
) -> dict[str, Any]:
    """Move stock between bins after explicit confirmation."""

    if not confirmation:
        return _error(
            code="CONFIRMATION_REQUIRED",
            message=(
                f"Moving stock for '{sku}' requires confirmation."
            ),
            field="confirmation",
            details={
                "sku": sku,
                "from_bin": from_bin,
                "to_bin": to_bin,
                "quantity": quantity,
            },
            suggested_action=(
                "Ask the user to explicitly confirm the stock movement."
            ),
        )

    if quantity <= 0:
        return _error(
            code="INVALID_ARGUMENT",
            message="Move quantity must be greater than zero.",
            field="quantity",
            suggested_action=(
                "Provide a positive quantity to move."
            ),
        )

    if not from_bin.strip():
        return _error(
            code="INVALID_ARGUMENT",
            message="Source bin cannot be empty.",
            field="from_bin",
            suggested_action=(
                "Provide the source bin."
            ),
        )

    if not to_bin.strip():
        return _error(
            code="INVALID_ARGUMENT",
            message="Destination bin cannot be empty.",
            field="to_bin",
            suggested_action=(
                "Provide the destination bin."
            ),
        )

    if from_bin.strip() == to_bin.strip():
        return _error(
            code="INVALID_ARGUMENT",
            message="Source and destination bins must be different.",
            field="to_bin",
            suggested_action=(
                "Provide a different destination bin."
            ),
        )

    records = store.load_stock()

    matches = [
        record
        for record in records
        if record["sku"].strip().upper() == sku.strip().upper()
        and record["site"] == context.assigned_site
        and record["bin"] == from_bin.strip()
    ]

    if not matches:
        return _error(
            code="NOT_FOUND",
            message=(
                f"SKU '{sku}' was not found in bin "
                f"'{from_bin}' at {context.assigned_site}."
            ),
            field="from_bin",
            suggested_action=(
                "Check the SKU and source bin."
            ),
        )

    record = matches[0]
    available_quantity = int(record["quantity"])

    if quantity > available_quantity:
        return _error(
            code="INSUFFICIENT_STOCK",
            message=(
                f"Cannot move {quantity} {record['unit']} of "
                f"'{sku}'. Only {available_quantity} "
                f"{record['unit']} are available in '{from_bin}'."
            ),
            field="quantity",
            details={
                "available_quantity": available_quantity,
                "requested_quantity": quantity,
            },
            suggested_action=(
                "Reduce the requested quantity or check another bin."
            ),
        )

    return {
        "ok": True,
        "movement": {
            "sku": record["sku"],
            "site": record["site"],
            "from_bin": record["bin"],
            "to_bin": to_bin.strip(),
            "quantity": quantity,
            "unit": record["unit"],
            "confirmed": True,
        },
    }