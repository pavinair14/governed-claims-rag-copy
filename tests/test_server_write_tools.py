import json

import pytest

from helpers import mcp_client

READ_TOOLS = {"get_stock", "search_stock", "list_dock_slots", "list_exceptions"}
WRITE_TOOLS = {
    "book_dock_slot",
    "cancel_dock_booking",
    "correct_stock",
    "move_stock",
    "raise_exception",
    "close_exception",
}
DESTRUCTIVE = {"cancel_dock_booking", "correct_stock", "close_exception"}
DATE = "2026-04-08"

BOOK = {"date": DATE, "slot": "10:00", "carrier": "Northbound Freight"}
CANCEL = {"date": DATE, "slot": "12:00"}
CORRECT = {"sku": "SKU-8802", "bin": "A-12-4", "corrected_quantity": 175, "reason": "recount"}
MOVE = {"sku": "SKU-8801", "from_bin": "A-12-3", "to_bin": "A-13-1", "quantity": 20}
RAISE = {"category": "damaged", "sku": "SKU-8801", "description": "torn pallet"}


async def preview(client, tool, args):
    is_error, body = await client.call(tool, args)
    assert is_error is True
    assert body["error"]["code"] == "CONFIRMATION_REQUIRED", body
    return body["error"]


async def confirmed(client, tool, args):
    err = await preview(client, tool, args)
    token = err["details"]["confirmation_token"]
    is_error, body = await client.call(tool, {**args, "confirmation_token": token})
    assert is_error is False, body
    return body


async def slot_status(client, slot, date=DATE):
    _, body = await client.call("list_dock_slots", {"date": date})
    return next(s for s in body["slots"] if s["slot"] == slot)


async def bins(client, sku):
    _, body = await client.call("get_stock", {"sku": sku})
    return {loc["bin"]: loc["quantity"] for loc in body["locations"]}


async def test_ten_tools_with_the_right_annotations_and_schemas():
    async with mcp_client() as client:
        tools = {t.name: t for t in await client.tools()}

    assert set(tools) == READ_TOOLS | WRITE_TOOLS

    for name in WRITE_TOOLS:
        tool = tools[name]
        assert tool.annotations.read_only_hint is False, name
        assert tool.annotations.destructive_hint is (name in DESTRUCTIVE), name
        assert tool.description.startswith("CHANGES STATE (requires confirmation)."), name
        props = tool.input_schema["properties"]
        assert "site" not in props
        assert "confirmation_token" in props
        assert "confirmation_token" not in tool.input_schema.get("required", [])
        assert tool.input_schema["additionalProperties"] is False

    for name in READ_TOOLS:
        assert tools[name].annotations.read_only_hint is True
        assert tools[name].annotations.destructive_hint is False

    assert tools["book_dock_slot"].input_schema["properties"]["slot"]["enum"] == [
        "06:00", "08:00", "10:00", "12:00", "14:00", "16:00",
    ]
    assert tools["raise_exception"].input_schema["properties"]["category"]["enum"] == [
        "damaged", "missing",
    ]


async def test_book_preview_changes_nothing_then_commit_does():
    async with mcp_client("LEEDS-01") as client:
        err = await preview(client, "book_dock_slot", BOOK)
        assert err["details"]["proposed_action"] == (
            "Book the 10:00 dock slot on 2026-04-08 at LEEDS-01 for Northbound Freight."
        )
        assert (await slot_status(client, "10:00"))["status"] == "available"

        body = await confirmed(client, "book_dock_slot", BOOK)
        assert body["applied"] is True
        assert await slot_status(client, "10:00") == {
            "slot": "10:00", "status": "booked", "carrier": "Northbound Freight",
        }


async def test_the_example_call_in_a_preview_commits_through_the_protocol():
    async with mcp_client("LEEDS-01") as client:
        err = await preview(client, "book_dock_slot", BOOK)
        example = err["example_call"]

        is_error, body = await client.call(example["tool"], example["arguments"])
        assert is_error is False, body
        assert (await slot_status(client, "10:00"))["status"] == "booked"


async def test_booking_a_booked_slot_fails_at_preview_with_alternatives():
    async with mcp_client("LEEDS-01") as client:
        is_error, body = await client.call("book_dock_slot", {**BOOK, "slot": "08:00"})

    assert is_error is True
    err = body["error"]
    assert err["code"] == "SLOT_ALREADY_BOOKED"
    assert err["details"]["available_slots"] == ["06:00", "10:00", "14:00", "16:00"]
    assert "confirmation_token" not in json.dumps(err)


async def test_a_wrong_token_changes_nothing():
    async with mcp_client("LEEDS-01") as client:
        is_error, body = await client.call(
            "book_dock_slot", {**BOOK, "confirmation_token": "not-a-real-token"}
        )
        assert is_error is True
        assert body["error"]["code"] == "CONFIRMATION_INVALID"
        assert (await slot_status(client, "10:00"))["status"] == "available"


async def test_a_token_cannot_be_used_for_different_arguments():
    async with mcp_client("LEEDS-01") as client:
        err = await preview(client, "book_dock_slot", BOOK)
        token = err["details"]["confirmation_token"]

        is_error, body = await client.call(
            "book_dock_slot", {**BOOK, "slot": "14:00", "confirmation_token": token}
        )
        assert is_error is True
        assert body["error"]["code"] == "CONFIRMATION_INVALID"
        assert (await slot_status(client, "14:00"))["status"] == "available"
        assert (await slot_status(client, "10:00"))["status"] == "available"


async def test_cancel_names_the_carrier_and_frees_the_slot():
    async with mcp_client("LEEDS-01") as client:
        err = await preview(client, "cancel_dock_booking", CANCEL)
        assert "held by Northbound Freight" in err["details"]["proposed_action"]

        body = await confirmed(client, "cancel_dock_booking", CANCEL)
        assert body["cancelled_carrier"] == "Northbound Freight"
        assert (await slot_status(client, "12:00"))["status"] == "available"


async def test_cancelling_an_available_slot_is_slot_not_booked():
    async with mcp_client("LEEDS-01") as client:
        is_error, body = await client.call(
            "cancel_dock_booking", {"date": DATE, "slot": "10:00"}
        )
    assert is_error is True
    assert body["error"]["code"] == "SLOT_NOT_BOOKED"


async def test_correct_stock_end_to_end():
    async with mcp_client("LEEDS-01") as client:
        assert await bins(client, "SKU-8802") == {"A-12-4": 180}

        err = await preview(client, "correct_stock", CORRECT)
        assert "from 180 to 175" in err["details"]["proposed_action"]
        assert await bins(client, "SKU-8802") == {"A-12-4": 180}

        body = await confirmed(client, "correct_stock", CORRECT)
        assert (body["previous_quantity"], body["corrected_quantity"]) == (180, 175)
        assert await bins(client, "SKU-8802") == {"A-12-4": 175}


async def test_move_stock_splits_a_sku_across_two_bins():
    async with mcp_client("LEEDS-01") as client:
        body = await confirmed(client, "move_stock", MOVE)

        assert body["total_quantity"] == 240
        assert await bins(client, "SKU-8801") == {"A-12-3": 220, "A-13-1": 20}


async def test_moving_too_much_is_insufficient_stock_with_the_numbers():
    async with mcp_client("LEEDS-01") as client:
        is_error, body = await client.call("move_stock", {**MOVE, "quantity": 241})

    assert is_error is True
    assert body["error"]["code"] == "INSUFFICIENT_STOCK"
    assert body["error"]["details"] == {"available": 240, "requested": 241}


async def test_exception_lifecycle_raise_list_close():
    async with mcp_client("LEEDS-01") as client:
        raised = await confirmed(client, "raise_exception", RAISE)
        exception_id = raised["exception_id"]
        assert exception_id == "EX-001"

        _, listing = await client.call("list_exceptions")
        assert [e["exception_id"] for e in listing["exceptions"]] == [exception_id]

        close_args = {"exception_id": exception_id, "resolution_note": "replaced the pallet"}
        err = await preview(client, "close_exception", close_args)
        assert "no way to reopen" in err["details"]["proposed_action"]

        closed = await confirmed(client, "close_exception", close_args)
        assert closed["status"] == "closed"

        _, listing = await client.call("list_exceptions")
        assert listing["exceptions"] == []

        is_error, body = await client.call("close_exception", close_args)
        assert is_error is True
        assert body["error"]["code"] == "ALREADY_CLOSED"


async def test_a_new_session_starts_from_clean_state():
    async with mcp_client("LEEDS-01") as client:
        await confirmed(client, "book_dock_slot", BOOK)
        assert (await slot_status(client, "10:00"))["status"] == "booked"

    async with mcp_client("LEEDS-01") as client:
        assert (await slot_status(client, "10:00"))["status"] == "available"


@pytest.mark.parametrize(
    "tool,args",
    [
        ("book_dock_slot", BOOK),
        ("cancel_dock_booking", CANCEL),
        ("correct_stock", CORRECT),
        ("move_stock", MOVE),
        ("raise_exception", RAISE),
        ("close_exception", {"exception_id": "EX-001", "resolution_note": "done"}),
    ],
)
async def test_a_site_argument_is_rejected_by_every_write_tool(tool, args):
    async with mcp_client("LEEDS-01") as client:
        is_error, body = await client.call(tool, {**args, "site": "READING-02"})

    assert is_error is True
    assert body["error"]["code"] == "INVALID_ARGUMENT"
    assert body["error"]["field"] == "site"


@pytest.mark.parametrize(
    "tool,args",
    [
        (
            "correct_stock",
            {"sku": "SKU-8805", "bin": "B-03-7", "corrected_quantity": 1, "reason": "recount"},
        ),
        (
            "move_stock",
            {"sku": "SKU-8805", "from_bin": "B-03-7", "to_bin": "B-03-9", "quantity": 1},
        ),
        (
            "raise_exception",
            {"category": "damaged", "sku": "SKU-8805", "description": "crushed"},
        ),
    ],
)
async def test_other_sites_stock_is_refused_by_the_write_tools(tool, args):
    async with mcp_client("LEEDS-01") as client:
        is_error, body = await client.call(tool, args)

    assert is_error is True
    assert body["error"]["code"] == "SITE_ACCESS_DENIED"
    text = json.dumps(body)
    for fragment in ["Corner protector", "READING", "1200"]:
        assert fragment not in text


async def test_same_site_writes_work_in_the_same_session_as_cross_site_refusals():
    async with mcp_client("READING-02") as client:
        is_error, body = await client.call(
            "raise_exception",
            {"category": "damaged", "sku": "SKU-8801", "description": "not ours"},
        )
        assert (is_error, body["error"]["code"]) == (True, "SITE_ACCESS_DENIED")

        raised = await confirmed(
            client,
            "raise_exception",
            {"category": "damaged", "sku": "SKU-8805", "description": "crushed corner"},
        )
        assert raised["sku"] == "SKU-8805"
        assert raised["site"] == "READING-02"


async def test_bad_enum_values_return_our_error_shape():
    async with mcp_client("LEEDS-01") as client:
        is_error, body = await client.call("book_dock_slot", {**BOOK, "slot": "11:00"})
        assert is_error is True
        assert body["error"]["details"]["allowed_values"] == [
            "06:00", "08:00", "10:00", "12:00", "14:00", "16:00",
        ]
        assert body["error"]["example_call"]["tool"] == "book_dock_slot"

        is_error, body = await client.call("raise_exception", {**RAISE, "category": "stolen"})
        assert is_error is True
        assert body["error"]["details"]["allowed_values"] == ["damaged", "missing"]