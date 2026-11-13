from datetime import datetime, timezone
from typing import Any

from warehouse_mcp.confirm import Confirmations, execute_write
from warehouse_mcp.errors import ErrorCode, ToolError
from warehouse_mcp.models import (
    CloseExceptionInput,
    ListExceptionsInput,
    RaiseExceptionInput,
)
from warehouse_mcp.scope import Scope

def _view(exc: dict[str, Any]) -> dict[str, Any]:
    return {
        "exception_id": exc["exception_id"],
        "category": exc["category"],
        "sku": exc["sku"],
        "description": exc["description"],
        "status": exc["status"],
        "raised_at": exc["raised_at"],
        "resolution_note": exc.get("resolution_note"),
    }


def list_exceptions(scope: Scope, args: ListExceptionsInput) -> dict[str, Any]:
    items = scope.exceptions()
    if args.status != "all":
        items = [e for e in items if e["status"] == args.status]

    return {
        "ok": True,
        "site": scope.site,
        "exceptions": [_view(e) for e in items],
        "exception_count": len(items),
    }


def _plan_raise(scope: Scope, args: RaiseExceptionInput) -> str:
    product = scope.rows_for_sku(args.sku)[0]  # NOT_FOUND or SITE_ACCESS_DENIED
    return (
        f"Raise a {args.category} exception for {args.sku} ({product.description}) "
        f"at {scope.site}: {args.description}"
    )


def _apply_raise(scope: Scope, args: RaiseExceptionInput) -> dict[str, Any]:
    record = {
        "exception_id": scope.next_exception_id(),
        "category": args.category,
        "sku": args.sku,
        "description": args.description,
        "status": "open",
        "raised_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "resolution_note": None,
    }
    scope.add_exception(record)
    scope.record(
        {
            "action": "raise_exception",
            "exception_id": record["exception_id"],
            "sku": args.sku,
            "before": None,
            "after": {"status": "open", "category": args.category},
        }
    )
    return {"ok": True, "site": scope.site, "applied": True, **_view(record)}


def raise_exception(
    confirmations: Confirmations, scope: Scope, args: RaiseExceptionInput
) -> dict[str, Any]:
    return execute_write(
        confirmations, scope, "raise_exception", args, _plan_raise, _apply_raise
    )

def _plan_close(scope: Scope, args: CloseExceptionInput) -> str:
    exc = scope.get_exception(args.exception_id)  # NOT_FOUND or SITE_ACCESS_DENIED

    if exc["status"] == "closed":
        raise ToolError(
            ErrorCode.ALREADY_CLOSED,
            f"Exception {args.exception_id} is already closed. Nothing was changed.",
            field="exception_id",
            details={"resolution_note": exc.get("resolution_note")},
            suggested_action=(
                "Do not retry. Tell the user it was already closed, and quote the "
                "existing resolution note. If the problem has come back, raise a "
                "new exception instead."
            ),
            example_call={"tool": "list_exceptions", "arguments": {"status": "open"}},
        )

    return (
        f"Close exception {args.exception_id} ({exc['category']}, {exc['sku']}: "
        f"{exc['description']}) at {scope.site} with the resolution note: "
        f"{args.resolution_note}. Closing is final: there is no way to reopen it. "
        "If it was closed in error, a new exception has to be raised."
    )


def _apply_close(scope: Scope, args: CloseExceptionInput) -> dict[str, Any]:
    exc = scope.get_exception(args.exception_id)
    exc["status"] = "closed"
    exc["resolution_note"] = args.resolution_note
    scope.record(
        {
            "action": "close_exception",
            "exception_id": args.exception_id,
            "before": {"status": "open", "resolution_note": None},
            "after": {"status": "closed", "resolution_note": args.resolution_note},
        }
    )
    return {"ok": True, "site": scope.site, "applied": True, **_view(exc)}


def close_exception(
    confirmations: Confirmations, scope: Scope, args: CloseExceptionInput
) -> dict[str, Any]:
    return execute_write(
        confirmations, scope, "close_exception", args, _plan_close, _apply_close
    )