from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

# Shared building blocks
Sku = Annotated[str, Field(pattern=r"^SKU-[0-9]{4}$")]
ExceptionId = Annotated[str, Field(pattern=r"^EX-[0-9]{3,}$")]
Slot = Literal["06:00", "08:00", "10:00", "12:00", "14:00", "16:00"]
BinName = Annotated[str, Field(min_length=1, max_length=20)]
Token = Annotated[str | None, Field(default=None)]


class ToolInput(BaseModel):
    """Base for every tool input: unknown fields (including 'site') are rejected."""

    model_config = ConfigDict(extra="forbid")


# Read-only tools
class GetStockInput(ToolInput):
    sku: Sku


class SearchStockInput(ToolInput):
    query: str = Field(min_length=2, max_length=80)


class ListDockSlotsInput(ToolInput):
    date: date
    status: Literal["available", "booked", "all"] = "all"


class ListExceptionsInput(ToolInput):
    status: Literal["open", "closed", "all"] = "open"


# State-changing tools (all take an optional confirmation token)
class BookDockSlotInput(ToolInput):
    date: date
    slot: Slot
    carrier: str = Field(min_length=1, max_length=80)
    confirmation_token: Token


class CancelDockBookingInput(ToolInput):
    date: date
    slot: Slot
    confirmation_token: Token


class CorrectStockInput(ToolInput):
    sku: Sku
    bin: BinName
    corrected_quantity: int = Field(strict=True, ge=0)
    reason: str = Field(min_length=3, max_length=300)
    confirmation_token: Token


class MoveStockInput(ToolInput):
    sku: Sku
    from_bin: BinName
    to_bin: BinName
    quantity: int = Field(strict=True, ge=1)
    confirmation_token: Token


class RaiseExceptionInput(ToolInput):
    category: Literal["damaged", "missing"]
    sku: Sku
    description: str = Field(min_length=3, max_length=500)
    confirmation_token: Token


class CloseExceptionInput(ToolInput):
    exception_id: ExceptionId
    resolution_note: str = Field(min_length=3, max_length=500)
    confirmation_token: Token