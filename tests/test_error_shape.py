from helpers import mcp_client
from warehouse_mcp.errors import ErrorCode
from warehouse_mcp.server import TOOLS

REQUIRED_KEYS = {"code", "message", "field", "details", "suggested_action"}
BY_NAME = {t.name: t for t in TOOLS}
DATE = "2026-04-08"

RAISE = {"category": "damaged", "sku": "SKU-8801", "description": "torn pallet"}


async def collect_every_error() -> dict[str, tuple[str, dict, dict]]:
    """One Leeds session that provokes each error code once."""
    seen: dict[str, tuple[str, dict, dict]] = {}

    async with mcp_client("LEEDS-01") as client:

        async def hit(tool, args):
            is_error, body = await client.call(tool, args)
            assert is_error is True, (tool, args, body)
            error = body["error"]
            seen.setdefault(error["code"], (tool, args, error))
            return error

        async def confirmed(tool, args):
            error = await hit(tool, args)
            assert error["code"] == "CONFIRMATION_REQUIRED"
            token = error["details"]["confirmation_token"]
            is_error, body = await client.call(tool, {**args, "confirmation_token": token})
            assert is_error is False, body
            return body

        await hit("get_stock", {"sku": "bad"})                                   # INVALID_ARGUMENT
        await hit("get_stock", {"sku": "SKU-0000"})                              # NOT_FOUND
        await hit("get_stock", {"sku": "SKU-8805"})                              # SITE_ACCESS_DENIED
        await hit(                                                               # CONFIRMATION_REQUIRED
            "book_dock_slot", {"date": DATE, "slot": "10:00", "carrier": "Northbound Freight"}
        )
        await hit(                                                               # CONFIRMATION_INVALID
            "book_dock_slot",
            {"date": DATE, "slot": "10:00", "carrier": "X", "confirmation_token": "bogus"},
        )
        await hit(                                                               # SLOT_ALREADY_BOOKED
            "book_dock_slot", {"date": DATE, "slot": "08:00", "carrier": "X"}
        )
        await hit("cancel_dock_booking", {"date": DATE, "slot": "10:00"})        # SLOT_NOT_BOOKED
        await hit(                                                               # INSUFFICIENT_STOCK
            "move_stock",
            {"sku": "SKU-8801", "from_bin": "A-12-3", "to_bin": "A-13-1", "quantity": 241},
        )

        raised = await confirmed("raise_exception", RAISE)                       # ALREADY_CLOSED
        close = {"exception_id": raised["exception_id"], "resolution_note": "replaced"}
        await confirmed("close_exception", close)
        await hit("close_exception", close)

    return seen


async def test_every_error_code_is_reachable_through_the_protocol():
    seen = await collect_every_error()
    assert set(seen) == {code.value for code in ErrorCode}


async def test_every_error_has_the_full_shape():
    for code, (tool, args, error) in (await collect_every_error()).items():
        assert REQUIRED_KEYS <= set(error), (code, error)
        assert error["message"].strip(), code
        assert error["suggested_action"].strip(), code
        assert isinstance(error["details"], dict), code


async def test_every_example_call_is_a_valid_call():
    checked = 0
    for code, (tool, args, error) in (await collect_every_error()).items():
        example = error.get("example_call")
        if example is None:
            continue
        spec = BY_NAME[example["tool"]]  # the tool it suggests must exist
        spec.model.model_validate(example["arguments"])  # and the call must be valid
        checked += 1
    assert checked >= 7