from __future__ import annotations

from typing import Any

from .context import CallerContext
from .data_store import WarehouseDataStore


VALID_EXCEPTION_CATEGORIES = {
    "damaged",
    "missing",
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


def raise_exception(
    store: WarehouseDataStore,
    context: CallerContext,
    category: str,
    description: str,
    sku: str | None,
    confirmation: bool,
) -> dict[str, Any]:
    """Create a warehouse exception after explicit confirmation."""

    if category not in VALID_EXCEPTION_CATEGORIES:
        return _error(
            code="INVALID_ARGUMENT",
            message=f"Invalid exception category '{category}'.",
            field="category",
            details={
                "allowed_values": sorted(VALID_EXCEPTION_CATEGORIES),
            },
            suggested_action=(
                "Use 'damaged' or 'missing'."
            ),
        )

    if not description.strip():
        return _error(
            code="INVALID_ARGUMENT",
            message="Exception description cannot be empty.",
            field="description",
            suggested_action=(
                "Provide a description of the damaged or missing item."
            ),
        )

    if not confirmation:
        return _error(
            code="CONFIRMATION_REQUIRED",
            message="Raising an exception requires confirmation.",
            field="confirmation",
            details={
                "category": category,
                "description": description,
                "sku": sku,
            },
            suggested_action=(
                "Ask the user to explicitly confirm the exception."
            ),
        )

    if sku is not None:
        matches = [
            record
            for record in store.load_stock()
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
                    "Check the SKU and ensure it belongs "
                    "to your assigned site."
                ),
            )

        normalized_sku = matches[0]["sku"]
    else:
        normalized_sku = None

    # Exception persistence will be added in the state layer.
    # For now this returns the validated operation.
    return {
        "ok": True,
        "exception": {
            "category": category,
            "description": description.strip(),
            "sku": normalized_sku,
            "site": context.assigned_site,
            "confirmed": True,
        },
    }


def close_exception(
    store: WarehouseDataStore,
    context: CallerContext,
    exception_id: str,
    resolution_note: str,
    confirmation: bool,
) -> dict[str, Any]:
    """Close an existing exception after explicit confirmation."""

    if not exception_id.strip():
        return _error(
            code="INVALID_ARGUMENT",
            message="Exception ID cannot be empty.",
            field="exception_id",
            suggested_action=(
                "Provide the exception ID to close."
            ),
        )

    if not resolution_note.strip():
        return _error(
            code="INVALID_ARGUMENT",
            message="Resolution note cannot be empty.",
            field="resolution_note",
            suggested_action=(
                "Provide a resolution note."
            ),
        )

    if not confirmation:
        return _error(
            code="CONFIRMATION_REQUIRED",
            message=(
                f"Closing exception '{exception_id}' "
                "requires confirmation."
            ),
            field="confirmation",
            details={
                "exception_id": exception_id,
                "resolution_note": resolution_note,
            },
            suggested_action=(
                "Ask the user to explicitly confirm the closure."
            ),
        )

    # Exception persistence and existence checks will be added
    # in the state layer.
    return {
        "ok": True,
        "closure": {
            "exception_id": exception_id.strip(),
            "site": context.assigned_site,
            "resolution_note": resolution_note.strip(),
            "confirmed": True,
        },
    }