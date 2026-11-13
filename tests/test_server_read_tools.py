import json
import subprocess
import sys

import pytest

from helpers import ROOT, mcp_client, server_env
from warehouse_mcp.context import SITES
from warehouse_mcp.store import Store

READ_TOOLS = {"get_stock", "search_stock", "list_dock_slots", "list_exceptions"}
FOREIGN_FRAGMENTS = {
    "LEEDS-01": ["READING", "GLASGOW"],
    "READING-02": ["LEEDS", "GLASGOW"],
    "GLASGOW-03": ["LEEDS", "READING"],
}


async def test_read_tools_are_listed_read_only_with_enums_and_no_site():
    async with mcp_client() as client:
        tools = {t.name: t for t in await client.tools()}

    assert READ_TOOLS <= set(tools)
    for name in READ_TOOLS:
        tool = tools[name]
        assert tool.annotations.read_only_hint is True
        assert tool.description.startswith("READ-ONLY.")
        assert "site" not in tool.input_schema["properties"]
        assert tool.input_schema["additionalProperties"] is False

    status = tools["list_dock_slots"].input_schema["properties"]["status"]
    assert status["enum"] == ["available", "booked", "all"]


async def test_each_read_tool_answers_through_the_protocol():
    async with mcp_client("LEEDS-01") as client:
        is_error, stock = await client.call("get_stock", {"sku": "SKU-8801"})
        assert (is_error, stock["total_quantity"]) == (False, 240)

        is_error, found = await client.call("search_stock", {"query": "void fill"})
        assert (is_error, found["match_status"]) == (False, "single")

        is_error, docks = await client.call("list_dock_slots", {"date": "2026-04-08"})
        assert (is_error, docks["slot_count"]) == (False, 6)

        is_error, excs = await client.call("list_exceptions")
        assert (is_error, excs["exceptions"]) == (False, [])


async def test_ambiguous_search_withholds_quantities_end_to_end():
    async with mcp_client("LEEDS-01") as client:
        is_error, body = await client.call("search_stock", {"query": "pallet wrap"})

    assert is_error is False
    assert body["match_status"] == "multiple"
    assert "quantity" not in json.dumps(body)
    assert "total_quantity" not in json.dumps(body)


async def test_zero_stock_is_a_success_end_to_end():
    async with mcp_client("GLASGOW-03") as client:
        is_error, body = await client.call("get_stock", {"sku": "SKU-8809"})
    assert is_error is False
    assert body["total_quantity"] == 0


async def test_bad_enum_returns_our_error_shape():
    async with mcp_client() as client:
        is_error, body = await client.call(
            "list_dock_slots", {"date": "2026-04-08", "status": "free"}
        )

    assert is_error is True
    err = body["error"]
    assert err["code"] == "INVALID_ARGUMENT"
    assert err["field"] == "status"
    assert err["details"]["allowed_values"] == ["available", "booked", "all"]
    assert err["example_call"]["tool"] == "list_dock_slots"


@pytest.mark.parametrize("tool,args", [
    ("get_stock", {"sku": "SKU-8801", "site": "READING-02"}),
    ("search_stock", {"query": "pallet", "site": "READING-02"}),
    ("list_dock_slots", {"date": "2026-04-08", "site": "READING-02"}),
    ("list_exceptions", {"site": "READING-02"}),
])
async def test_a_site_argument_is_rejected_by_every_read_tool(tool, args):
    async with mcp_client("LEEDS-01") as client:
        is_error, body = await client.call(tool, args)

    assert is_error is True
    assert body["error"]["code"] == "INVALID_ARGUMENT"
    assert body["error"]["field"] == "site"
    assert "READING" not in json.dumps(body["error"]["message"])


async def test_unknown_tool_is_an_actionable_error():
    async with mcp_client() as client:
        is_error, body = await client.call("lookup", {"sku": "SKU-8801"})

    assert is_error is True
    assert len(body["error"]["details"]["available_tools"]) == 10


@pytest.mark.parametrize("site", SITES)
async def test_same_site_works_and_cross_site_is_refused_in_one_session(site):
    async with mcp_client(site) as client:
        for row in Store.load().stock:
            is_error, body = await client.call("get_stock", {"sku": row.sku})
            if row.site == site:
                assert is_error is False, row.sku
                assert body["total_quantity"] == row.quantity
                assert body["site"] == site
            else:
                assert is_error is True, row.sku
                assert body["error"]["code"] == "SITE_ACCESS_DENIED"
                text = json.dumps(body)
                assert row.description not in text
                assert row.bin not in text
                for fragment in FOREIGN_FRAGMENTS[site]:
                    assert fragment not in text


@pytest.mark.parametrize("site", SITES)
async def test_each_site_sees_only_its_own_docks(site):
    async with mcp_client(site) as client:
        _, body = await client.call("list_dock_slots", {"date": "2026-04-08"})
    assert body["site"] == site
    assert body["slot_count"] == 6


@pytest.mark.parametrize("env_site", [None, "", "MANCHESTER-04", "leeds-01"])
def test_server_refuses_to_start_without_a_valid_site(env_site):
    proc = subprocess.run(
        [sys.executable, "-m", "warehouse_mcp.server"],
        env=server_env(site=env_site),
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 1
    assert "KESTREL_ASSIGNED_SITE" in proc.stderr