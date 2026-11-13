from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    NOT_FOUND = "NOT_FOUND"
    SITE_ACCESS_DENIED = "SITE_ACCESS_DENIED"
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"
    CONFIRMATION_INVALID = "CONFIRMATION_INVALID"
    SLOT_ALREADY_BOOKED = "SLOT_ALREADY_BOOKED"
    SLOT_NOT_BOOKED = "SLOT_NOT_BOOKED"
    INSUFFICIENT_STOCK = "INSUFFICIENT_STOCK"
    ALREADY_CLOSED = "ALREADY_CLOSED"


class ToolError(Exception):
    """A failure the agent can act on. Tools raise it; the server turns it into JSON."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        suggested_action: str,
        field: str | None = None,
        details: dict[str, Any] | None = None,
        example_call: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.suggested_action = suggested_action
        self.field = field
        self.details = details or {}
        self.example_call = example_call

    def to_envelope(self) -> dict[str, Any]:
        error: dict[str, Any] = {
            "code": self.code.value,
            "message": self.message,
            "field": self.field,
            "details": self.details,
            "suggested_action": self.suggested_action,
        }
        if self.example_call is not None:
            error["example_call"] = self.example_call
        return {"ok": False, "error": error}