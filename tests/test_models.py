import pytest
from pydantic import ValidationError

from warehouse_mcp.models import (
    BookDockSlotInput,
    CancelDockBookingInput,
    CloseExceptionInput,
    CorrectStockInput,
    GetStockInput,
    ListDockSlotsInput,
    ListExceptionsInput,
    MoveStockInput,
    RaiseExceptionInput,
    SearchStockInput,
)

VALID = [
    (GetStockInput, {"sku": "SKU-8801"}),
    (SearchStockInput, {"query": "pallet wrap"}),
    (ListDockSlotsInput, {"date": "2026-04-08"}),
    (ListExceptionsInput, {}),
    (BookDockSlotInput, {"date": "2026-04-08", "slot": "10:00", "carrier": "Northbound Freight"}),
    (CancelDockBookingInput, {"date": "2026-04-08", "slot": "12:00"}),
    (CorrectStockInput, {"sku": "SKU-8802", "bin": "A-12-4", "corrected_quantity": 175, "reason": "recount"}),
    (MoveStockInput, {"sku": "SKU-8801", "from_bin": "A-12-3", "to_bin": "A-13-1", "quantity": 20}),
    (RaiseExceptionInput, {"category": "damaged", "sku": "SKU-8801", "description": "torn pallet"}),
    (CloseExceptionInput, {"exception_id": "EX-001", "resolution_note": "replaced"}),
]


@pytest.mark.parametrize("model,payload", VALID)
def test_valid_payloads_accepted(model, payload):
    model(**payload)


@pytest.mark.parametrize("model,payload", VALID)
def test_site_property_is_rejected_everywhere(model, payload):
    with pytest.raises(ValidationError):
        model(**payload, site="READING-02")


BAD = [
    (GetStockInput, {"sku": "8801"}),
    (GetStockInput, {"sku": "sku-8801"}),
    (GetStockInput, {}),
    (SearchStockInput, {"query": "a"}),
    (ListDockSlotsInput, {"date": "next tuesday"}),
    (ListDockSlotsInput, {"date": "2026-04-08", "status": "free"}),
    (ListExceptionsInput, {"status": "pending"}),
    (BookDockSlotInput, {"date": "2026-04-08", "slot": "11:00", "carrier": "X"}),
    (BookDockSlotInput, {"date": "2026-04-08", "slot": "10am", "carrier": "X"}),
    (BookDockSlotInput, {"date": "2026-04-08", "slot": "10:00", "carrier": ""}),
    (CorrectStockInput, {"sku": "SKU-8802", "bin": "A-12-4", "corrected_quantity": -1, "reason": "recount"}),
    (CorrectStockInput, {"sku": "SKU-8802", "bin": "A-12-4", "corrected_quantity": "5", "reason": "recount"}),
    (MoveStockInput, {"sku": "SKU-8801", "from_bin": "A-12-3", "to_bin": "A-13-1", "quantity": 0}),
    (RaiseExceptionInput, {"category": "stolen", "sku": "SKU-8801", "description": "gone"}),
    (RaiseExceptionInput, {"category": "damaged", "description": "torn pallet"}),
    (CloseExceptionInput, {"exception_id": "001", "resolution_note": "replaced"}),
]


@pytest.mark.parametrize("model,payload", BAD)
def test_invalid_payloads_rejected(model, payload):
    with pytest.raises(ValidationError):
        model(**payload)


def test_closed_sets_are_enums_in_the_published_schema():
    slot = BookDockSlotInput.model_json_schema()["properties"]["slot"]
    assert slot["enum"] == ["06:00", "08:00", "10:00", "12:00", "14:00", "16:00"]

    status = ListDockSlotsInput.model_json_schema()["properties"]["status"]
    assert status["enum"] == ["available", "booked", "all"]

    category = RaiseExceptionInput.model_json_schema()["properties"]["category"]
    assert category["enum"] == ["damaged", "missing"]