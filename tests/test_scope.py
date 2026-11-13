import json

import pytest

from warehouse_mcp.context import SITES
from warehouse_mcp.errors import ErrorCode, ToolError
from warehouse_mcp.store import Store

FOREIGN_FRAGMENTS = ["Corner protector", "1200", "B-03-7", "READING"]


def test_stock_rows_are_limited_to_own_site(make_scope):
    assert len(make_scope("LEEDS-01").stock_rows()) == 7
    assert len(make_scope("READING-02").stock_rows()) == 5
    assert len(make_scope("GLASGOW-03").stock_rows()) == 4


def test_same_site_sku_returns_rows(make_scope):
    rows = make_scope("LEEDS-01").rows_for_sku("SKU-8801")
    assert [r.bin for r in rows] == ["A-12-3"]


def test_cross_site_sku_is_denied_without_leaking(make_scope):
    with pytest.raises(ToolError) as caught:
        make_scope("LEEDS-01").rows_for_sku("SKU-8805")

    assert caught.value.code == ErrorCode.SITE_ACCESS_DENIED
    text = json.dumps(caught.value.to_envelope())
    for fragment in FOREIGN_FRAGMENTS:
        assert fragment not in text


def test_unknown_sku_is_not_found_with_a_next_step(make_scope):
    with pytest.raises(ToolError) as caught:
        make_scope("LEEDS-01").rows_for_sku("SKU-0000")

    assert caught.value.code == ErrorCode.NOT_FOUND
    assert caught.value.example_call["tool"] == "search_stock"


@pytest.mark.parametrize("site", SITES)
def test_every_sku_is_own_or_denied_never_both(site, make_scope):
    scope = make_scope(site)
    for row in Store.load().stock:
        if row.site == site:
            assert scope.rows_for_sku(row.sku)
        else:
            with pytest.raises(ToolError) as caught:
                scope.rows_for_sku(row.sku)
            assert caught.value.code == ErrorCode.SITE_ACCESS_DENIED


def test_own_bins_accepted(make_scope):
    make_scope("LEEDS-01").require_own_bin("A-12-3")
    make_scope("LEEDS-01").require_own_bin("YARD-1")
    make_scope("READING-02").require_own_bin("B-03-7")


def test_other_sites_bin_is_denied(make_scope):
    with pytest.raises(ToolError) as caught:
        make_scope("LEEDS-01").require_own_bin("B-03-7", field="to_bin")
    assert caught.value.code == ErrorCode.SITE_ACCESS_DENIED


def test_unrecognised_bin_is_invalid(make_scope):
    with pytest.raises(ToolError) as caught:
        make_scope("LEEDS-01").require_own_bin("Z-99", field="to_bin")
    assert caught.value.code == ErrorCode.INVALID_ARGUMENT
    assert caught.value.field == "to_bin"


def test_docks_only_show_own_site(make_scope):
    slots = make_scope("LEEDS-01").dock_slots("2026-04-08")
    assert len(slots) == 6
    assert {s.site for s in slots} == {"LEEDS-01"}
    assert make_scope("LEEDS-01").dock_slots("2026-04-09") == []
    assert make_scope("LEEDS-01").scheduled_dates() == ["2026-04-08"]


def test_exceptions_are_site_scoped(store, make_scope):
    store.exceptions.append(
        {"exception_id": "EX-001", "site": "READING-02", "description": "crushed corner protectors"}
    )

    assert make_scope("READING-02").get_exception("EX-001")["exception_id"] == "EX-001"

    with pytest.raises(ToolError) as denied:
        make_scope("LEEDS-01").get_exception("EX-001")
    assert denied.value.code == ErrorCode.SITE_ACCESS_DENIED
    assert "crushed" not in json.dumps(denied.value.to_envelope())

    with pytest.raises(ToolError) as missing:
        make_scope("LEEDS-01").get_exception("EX-999")
    assert missing.value.code == ErrorCode.NOT_FOUND