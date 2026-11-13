import json

import pytest

from warehouse_mcp.context import SITES
from warehouse_mcp.errors import ErrorCode, ToolError
from warehouse_mcp.models import SearchStockInput
from warehouse_mcp.store import Store
from warehouse_mcp.tools.stock import search_stock


def call(scope, query):
    return search_stock(scope, SearchStockInput(query=query))


def test_ambiguous_returns_all_candidates_without_quantities(make_scope):
    result = call(make_scope("LEEDS-01"), "pallet wrap")

    assert result["match_status"] == "multiple"
    assert [m["sku"] for m in result["matches"]] == ["SKU-8801", "SKU-8802"]
    for m in result["matches"]:
        assert set(m) == {"sku", "description"}
    assert "locations" not in result
    assert "total_quantity" not in result
    assert "get_stock" in result["next_step"]


def test_unambiguous_answers_directly_with_quantity(make_scope):
    result = call(make_scope("LEEDS-01"), "void fill")

    assert result["match_status"] == "single"
    assert len(result["matches"]) == 1
    match = result["matches"][0]
    assert match["sku"] == "SKU-8811"
    assert match["total_quantity"] == 420
    assert "next_step" not in result


def test_void_fill_is_single_at_both_sites_that_have_it(make_scope):
    glasgow = call(make_scope("GLASGOW-03"), "void fill")
    assert glasgow["match_status"] == "single"
    assert glasgow["matches"][0]["sku"] == "SKU-8810"


def test_zero_stock_product_appears_among_candidates(make_scope):
    result = call(make_scope("GLASGOW-03"), "shrink film")
    assert [m["sku"] for m in result["matches"]] == ["SKU-8808", "SKU-8809"]


def test_zero_stock_single_match_is_a_success(make_scope):
    result = call(make_scope("GLASGOW-03"), "600mm shrink film")
    assert result["match_status"] == "single"
    assert result["matches"][0]["total_quantity"] == 0


def test_no_match_is_not_found_with_a_way_forward(make_scope):
    with pytest.raises(ToolError) as caught:
        call(make_scope("LEEDS-01"), "forklift battery")

    err = caught.value
    assert err.code == ErrorCode.NOT_FOUND
    assert err.field == "query"
    assert err.example_call["tool"] == "search_stock"


def test_other_sites_products_are_never_found_or_hinted(make_scope):
    with pytest.raises(ToolError) as caught:
        call(make_scope("LEEDS-01"), "edge board")

    assert caught.value.code == ErrorCode.NOT_FOUND
    text = json.dumps(caught.value.to_envelope())
    for fragment in ["SKU-8807", "B-05-2", "READING", "340"]:
        assert fragment not in text


@pytest.mark.parametrize("site", SITES)
def test_every_full_description_finds_exactly_its_own_product(site, make_scope):
    scope = make_scope(site)
    for row in Store.load().stock:
        if row.site != site:
            continue
        result = call(scope, row.description)
        assert result["match_status"] == "single", row.description
        assert result["matches"][0]["sku"] == row.sku