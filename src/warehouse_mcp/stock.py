from __future__ import annotations

from typing import Any

from .context import CallerContext, require_site_access
from .data_store import WarehouseDataStore


def get_stock(
    store: WarehouseDataStore,
    context: CallerContext,
    sku: str,
) -> dict[str, Any]:
    """Return stock for an exact SKU within the caller's assigned site."""

    records = store.load_stock()

    matches = [
        record
        for record in records
        if record["sku"].strip().upper() == sku.strip().upper()
    ]

    if not matches:
        return {
            "ok": False,
            "error": {
                "code": "NOT_FOUND",
                "message": f"SKU '{sku}' was not found.",
                "field": "sku",
                "details": {},
                "suggested_action": (
                    "Check the SKU or use product description search."
                ),
            },
        }

    record = matches[0]

    try:
        require_site_access(context, record["site"])
    except PermissionError:
        return {
            "ok": False,
            "error": {
                "code": "SITE_ACCESS_DENIED",
                "message": (
                    f"SKU '{sku}' belongs to a site outside "
                    "the caller's assigned site."
                ),
                "field": "sku",
                "details": {
                    "assigned_site": context.assigned_site,
                },
                "suggested_action": (
                    "Request a SKU belonging to the assigned site."
                ),
            },
        }

    return {
        "ok": True,
        "stock": {
            "sku": record["sku"],
            "description": record["description"],
            "site": record["site"],
            "bin": record["bin"],
            "quantity": int(record["quantity"]),
            "unit": record["unit"],
        },
    }


def search_stock(
    store: WarehouseDataStore,
    context: CallerContext,
    query: str,
) -> dict[str, Any]:
    """Search stock descriptions within the caller's assigned site."""

    query = query.strip().lower()

    if not query:
        return {
            "ok": False,
            "error": {
                "code": "INVALID_ARGUMENT",
                "message": "Search query cannot be empty.",
                "field": "query",
                "details": {},
                "suggested_action": (
                    "Provide a product description or search term."
                ),
            },
        }

    records = store.load_stock()

    matches = [
        record
        for record in records
        if query in record["description"].strip().lower()
        and record["site"] == context.assigned_site
    ]

    if not matches:
        return {
            "ok": False,
            "error": {
                "code": "NOT_FOUND",
                "message": (
                    f"No stock items matched the search '{query}'."
                ),
                "field": "query",
                "details": {},
                "suggested_action": (
                    "Try a different product description."
                ),
            },
        }

    candidates = [
        {
            "sku": record["sku"],
            "description": record["description"],
            "site": record["site"],
            "bin": record["bin"],
            "quantity": int(record["quantity"]),
            "unit": record["unit"],
        }
        for record in matches
    ]

    return {
        "ok": True,
        "matches": candidates,
        "match_count": len(candidates),
    }