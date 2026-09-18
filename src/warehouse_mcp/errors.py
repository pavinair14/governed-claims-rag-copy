from __future__ import annotations

from typing import Any


def make_error(
    code: str,
    message: str,
    *,
    field: str | None = None,
    details: dict[str, Any] | None = None,
    suggested_action: str | None = None,
) -> dict[str, Any]:
    """Create the common error response used by all toolkit operations."""

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