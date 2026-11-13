import json

import pytest

from warehouse_mcp.errors import ErrorCode, ToolError
from warehouse_mcp.models import (
    BookDockSlotInput,
    CorrectStockInput,
    GetStockInput,
    ListExceptionsInput,
    MoveStockInput,
    RaiseExceptionInput,
)
from warehouse_mcp.validate import parse_args

BOOK_EXAMPLE = {"date": "2026-04-08", "slot": "10:00", "carrier": "Northbound Freight"}


def fail(model, raw, tool="t", example=None):
    with pytest.raises(ToolError) as caught:
        parse_args(model, raw, tool=tool, example=example or {})
    assert caught.value.code == ErrorCode.INVALID_ARGUMENT
    return caught.value


def test_bad_slot_lists_the_allowed_values_and_an_example():
    err = fail(
        BookDockSlotInput,
        {**BOOK_EXAMPLE, "slot": "11:00"},
        tool="book_dock_slot",
        example=BOOK_EXAMPLE,
    )
    assert err.field == "slot"
    assert err.details["allowed_values"] == ["06:00", "08:00", "10:00", "12:00", "14:00", "16:00"]
    assert err.details["received"] == "11:00"
    assert err.example_call == {"tool": "book_dock_slot", "arguments": BOOK_EXAMPLE}


def test_site_argument_gets_its_own_explanation():
    err = fail(GetStockInput, {"sku": "SKU-8801", "site": "READING-02"})
    assert err.field == "site"
    assert "session" in err.message


def test_missing_required_parameter():
    err = fail(GetStockInput, {})
    assert err.field == "sku"
    assert "missing" in err.message


def test_bad_sku_format_shows_the_pattern():
    err = fail(GetStockInput, {"sku": "8801"})
    assert err.field == "sku"
    assert err.details["pattern"] == "^SKU-[0-9]{4}$"


def test_bad_category_lists_the_two_allowed_values():
    err = fail(
        RaiseExceptionInput,
        {"category": "stolen", "sku": "SKU-8801", "description": "gone"},
    )
    assert err.details["allowed_values"] == ["damaged", "missing"]


def test_quantity_as_text_and_below_minimum_are_rejected():
    base = {"sku": "SKU-8801", "from_bin": "A-12-3", "to_bin": "A-13-1"}
    assert fail(MoveStockInput, {**base, "quantity": "5"}).field == "quantity"
    assert fail(MoveStockInput, {**base, "quantity": 0}).field == "quantity"
    assert (
        fail(
            CorrectStockInput,
            {"sku": "SKU-8802", "bin": "A-12-4", "corrected_quantity": -1, "reason": "recount"},
        ).field
        == "corrected_quantity"
    )


def test_bad_date_asks_for_iso_format():
    err = fail(
        BookDockSlotInput,
        {**BOOK_EXAMPLE, "date": "next tuesday"},
        tool="book_dock_slot",
        example=BOOK_EXAMPLE,
    )
    assert err.field == "date"
    assert "YYYY-MM-DD" in err.message


def test_every_problem_is_listed_not_just_the_first():
    err = fail(BookDockSlotInput, {"date": "2026-04-08", "slot": "11:00"})
    fields = {p["field"] for p in err.details["problems"]}
    assert fields == {"slot", "carrier"}


def test_valid_input_returns_the_model():
    parsed = parse_args(BookDockSlotInput, BOOK_EXAMPLE, tool="t", example={})
    assert parsed.slot == "10:00"


def test_missing_arguments_use_defaults():
    assert parse_args(ListExceptionsInput, None, tool="t", example={}).status == "open"


def test_envelope_is_valid_json_with_the_full_shape():
    err = fail(GetStockInput, {"sku": "bad"}, tool="get_stock", example={"sku": "SKU-8801"})
    envelope = json.loads(json.dumps(err.to_envelope()))
    assert envelope["ok"] is False
    assert set(envelope["error"]) >= {
        "code", "message", "field", "details", "suggested_action", "example_call",
    }