import json

import pytest

from warehouse_mcp.context import SITES
from warehouse_mcp.errors import ErrorCode, ToolError
from warehouse_mcp.models import GetStockInput
from warehouse_mcp.store import Store
from warehouse_mcp.tools.stock import get_stock


def call(scope, sku):
    return get_stock(scope, GetStockInput(sku=sku))


def test_same_site_sku(make_scope):
    result = call(make_scope("LEEDS-01"), "SKU-8801")
    assert result == {
        "ok": True,
        "site": "LEEDS-01",
        "sku": "SKU-8801",
        "description": "Pallet wrap, 500mm clear",
        "unit": "each",
        "locations": [{"bin": "A-12-3", "quantity": 240}],
        "total_quantity": 240,
    }


def test_zero_stock_is_a_success_not_an_error(make_scope):
    result = call(make_scope("GLASGOW-03"), "SKU-8809")
    assert result["ok"] is True
    assert result["total_quantity"] == 0
    assert result["locations"] == [{"bin": "C-08-2", "quantity": 0}]


def test_unknown_sku_is_not_found(make_scope):
    with pytest.raises(ToolError) as caught:
        call(make_scope("LEEDS-01"), "SKU-0000")
    assert caught.value.code == ErrorCode.NOT_FOUND


def test_cross_site_sku_is_denied_without_leaking(make_scope):
    with pytest.raises(ToolError) as caught:
        call(make_scope("LEEDS-01"), "SKU-8805")

    assert caught.value.code == ErrorCode.SITE_ACCESS_DENIED
    text = json.dumps(caught.value.to_envelope())
    for fragment in ["Corner protector", "1200", "B-03-7", "READING"]:
        assert fragment not in text


@pytest.mark.parametrize("site", SITES)
def test_every_own_sku_works_and_every_other_is_denied(site, make_scope):
    scope = make_scope(site)
    for row in Store.load().stock:
        if row.site == site:
            assert call(scope, row.sku)["total_quantity"] == row.quantity
        else:
            with pytest.raises(ToolError) as caught:
                call(scope, row.sku)
            assert caught.value.code == ErrorCode.SITE_ACCESS_DENIED