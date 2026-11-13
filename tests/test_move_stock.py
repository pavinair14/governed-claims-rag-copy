import json

import pytest

from warehouse_mcp.context import SITES
from warehouse_mcp.errors import ErrorCode, ToolError
from warehouse_mcp.models import GetStockInput, MoveStockInput
from warehouse_mcp.store import Store
from warehouse_mcp.tools.stock import get_stock, move_stock

NEW_BIN = {"LEEDS-01": "A-90-1", "READING-02": "B-90-1", "GLASGOW-03": "C-90-1"}


def make_args(sku="SKU-8801", from_bin="A-12-3", to_bin="A-13-1", qty=20, token=None):
    return MoveStockInput(
        sku=sku,
        from_bin=from_bin,
        to_bin=to_bin,
        quantity=qty,
        confirmation_token=token,
    )


def preview(confirmations, scope, **kw):
    with pytest.raises(ToolError) as caught:
        move_stock(confirmations, scope, make_args(**kw))
    assert caught.value.code == ErrorCode.CONFIRMATION_REQUIRED
    return caught.value


def fails_with(confirmations, scope, code, **kw):
    with pytest.raises(ToolError) as caught:
        move_stock(confirmations, scope, make_args(**kw))
    assert caught.value.code == code
    return caught.value


def do_move(confirmations, scope, **kw):
    token = preview(confirmations, scope, **kw).details["confirmation_token"]
    return move_stock(confirmations, scope, make_args(token=token, **kw))


def bins(scope, sku="SKU-8801"):
    result = get_stock(scope, GetStockInput(sku=sku))
    return {loc["bin"]: loc["quantity"] for loc in result["locations"]}


def grand_total(store):
    return sum(r.quantity for r in store.stock)


def test_preview_describes_both_bins_and_changes_nothing(confirmations, make_scope, store):
    scope = make_scope("LEEDS-01")
    err = preview(confirmations, scope)

    assert err.details["proposed_action"] == (
        "Move 20 each of SKU-8801 (Pallet wrap, 500mm clear) from bin A-12-3 to bin "
        "A-13-1 at LEEDS-01. Bin A-12-3 will go from 240 to 220; bin A-13-1 will go "
        "from 0 to 20. Total stock stays at 240. Bin A-13-1 does not currently hold "
        "this SKU."
    )
    assert bins(scope) == {"A-12-3": 240}
    assert store.audit == []


def test_partial_move_splits_the_sku_across_two_bins(confirmations, make_scope, store):
    scope = make_scope("LEEDS-01")
    before = grand_total(store)

    result = do_move(confirmations, scope)

    assert result == {
        "ok": True,
        "site": "LEEDS-01",
        "applied": True,
        "sku": "SKU-8801",
        "unit": "each",
        "from_bin": "A-12-3",
        "to_bin": "A-13-1",
        "quantity_moved": 20,
        "from_bin_quantity": 220,
        "to_bin_quantity": 20,
        "total_quantity": 240,
    }
    assert bins(scope) == {"A-12-3": 220, "A-13-1": 20}
    assert grand_total(store) == before
    assert len(store.audit) == 1
    entry = store.audit[0]
    assert entry["action"] == "move_stock"
    assert entry["before"] == {"A-12-3": 240, "A-13-1": 0}
    assert entry["after"] == {"A-12-3": 220, "A-13-1": 20}


def test_moving_everything_leaves_the_sku_in_one_bin(confirmations, make_scope):
    scope = make_scope("LEEDS-01")
    do_move(confirmations, scope, qty=240)
    assert bins(scope) == {"A-13-1": 240}


def test_second_move_into_the_same_bin_adds_to_it(confirmations, make_scope):
    scope = make_scope("LEEDS-01")
    do_move(confirmations, scope, qty=20)

    err = preview(confirmations, scope, qty=30)
    assert "does not currently hold" not in err.details["proposed_action"]
    assert "bin A-13-1 will go from 20 to 50" in err.details["proposed_action"]

    do_move(confirmations, scope, qty=30)
    assert bins(scope) == {"A-12-3": 190, "A-13-1": 50}


def test_a_reverse_move_undoes_a_move(confirmations, make_scope, store):
    scope = make_scope("LEEDS-01")
    before = grand_total(store)
    do_move(confirmations, scope, qty=20)
    do_move(confirmations, scope, from_bin="A-13-1", to_bin="A-12-3", qty=20)

    assert bins(scope) == {"A-12-3": 240}
    assert grand_total(store) == before


def test_too_much_is_insufficient_stock_with_the_numbers(confirmations, make_scope, store):
    err = fails_with(
        confirmations, make_scope("LEEDS-01"), ErrorCode.INSUFFICIENT_STOCK, qty=241
    )
    assert err.field == "quantity"
    assert err.details == {"available": 240, "requested": 241}
    assert err.example_call["arguments"]["quantity"] == 240
    assert confirmations.outstanding() == 0
    assert store.audit == []


def test_the_example_call_for_insufficient_stock_reaches_a_preview(
    confirmations, make_scope
):
    scope = make_scope("LEEDS-01")
    example = fails_with(
        confirmations, scope, ErrorCode.INSUFFICIENT_STOCK, qty=241
    ).example_call

    with pytest.raises(ToolError) as caught:
        move_stock(confirmations, scope, MoveStockInput(**example["arguments"]))
    assert caught.value.code == ErrorCode.CONFIRMATION_REQUIRED


def test_moving_from_a_zero_stock_bin_is_insufficient_with_no_example(
    confirmations, make_scope
):
    err = fails_with(
        confirmations,
        make_scope("GLASGOW-03"),
        ErrorCode.INSUFFICIENT_STOCK,
        sku="SKU-8809",
        from_bin="C-08-2",
        to_bin="C-08-9",
        qty=1,
    )
    assert err.details["available"] == 0
    assert err.example_call is None


def test_same_source_and_destination_is_invalid(confirmations, make_scope):
    err = fails_with(
        confirmations,
        make_scope("LEEDS-01"),
        ErrorCode.INVALID_ARGUMENT,
        to_bin="A-12-3",
    )
    assert err.field == "to_bin"


def test_a_bin_from_another_sites_zone_is_denied_as_destination(confirmations, make_scope):
    err = fails_with(
        confirmations,
        make_scope("LEEDS-01"),
        ErrorCode.SITE_ACCESS_DENIED,
        to_bin="B-03-7",
    )
    text = json.dumps(err.to_envelope())
    assert "READING" not in text
    assert "Corner protector" not in text
    assert confirmations.outstanding() == 0


def test_a_bin_from_another_sites_zone_is_denied_as_source(confirmations, make_scope):
    fails_with(
        confirmations,
        make_scope("LEEDS-01"),
        ErrorCode.SITE_ACCESS_DENIED,
        from_bin="B-03-7",
    )


def test_unrecognised_bin_is_invalid_and_lists_the_prefixes(confirmations, make_scope):
    err = fails_with(
        confirmations, make_scope("LEEDS-01"), ErrorCode.INVALID_ARGUMENT, to_bin="Z-99"
    )
    assert err.field == "to_bin"
    assert err.details["valid_prefixes"] == ["A-", "YARD-"]


def test_source_bin_that_does_not_hold_the_sku_lists_the_bins_that_do(
    confirmations, make_scope
):
    err = fails_with(
        confirmations, make_scope("LEEDS-01"), ErrorCode.NOT_FOUND, from_bin="A-99-9"
    )
    assert err.field == "from_bin"
    assert err.details["bins_holding_sku"] == ["A-12-3"]
    assert err.example_call["arguments"]["from_bin"] == "A-12-3"


def test_unknown_sku_is_not_found(confirmations, make_scope):
    fails_with(
        confirmations, make_scope("LEEDS-01"), ErrorCode.NOT_FOUND, sku="SKU-0000"
    )


def test_other_sites_sku_is_denied(confirmations, make_scope):
    err = fails_with(
        confirmations,
        make_scope("LEEDS-01"),
        ErrorCode.SITE_ACCESS_DENIED,
        sku="SKU-8805",
        from_bin="B-03-7",
        to_bin="B-03-9",
    )
    assert "Corner protector" not in json.dumps(err.to_envelope())


def test_stock_changed_after_the_preview_voids_the_token(confirmations, make_scope):
    scope = make_scope("LEEDS-01")
    token = preview(confirmations, scope).details["confirmation_token"]

    scope.rows_for_sku("SKU-8801")[0].quantity = 230  # someone corrects it first

    with pytest.raises(ToolError) as caught:
        move_stock(confirmations, scope, make_args(token=token))
    assert caught.value.code == ErrorCode.CONFIRMATION_INVALID
    assert bins(scope) == {"A-12-3": 230}


def test_token_for_one_quantity_cannot_move_another(confirmations, make_scope):
    scope = make_scope("LEEDS-01")
    token = preview(confirmations, scope, qty=20).details["confirmation_token"]

    with pytest.raises(ToolError) as caught:
        move_stock(confirmations, scope, make_args(qty=200, token=token))
    assert caught.value.code == ErrorCode.CONFIRMATION_INVALID
    assert bins(scope) == {"A-12-3": 240}


def test_a_move_only_changes_the_callers_own_site(confirmations, make_scope, store):
    do_move(confirmations, make_scope("LEEDS-01"))
    assert bins(make_scope("READING-02"), "SKU-8805") == {"B-03-7": 1200}
    assert bins(make_scope("GLASGOW-03"), "SKU-8809") == {"C-08-2": 0}


@pytest.mark.parametrize("site", SITES)
def test_own_skus_reach_a_preview_and_every_other_sites_are_denied(
    site, confirmations, make_scope
):
    scope = make_scope(site)
    for row in Store.load().stock:
        args = dict(sku=row.sku, from_bin=row.bin, to_bin=NEW_BIN[site], qty=1)
        if row.site != site:
            err = fails_with(confirmations, scope, ErrorCode.SITE_ACCESS_DENIED, **args)
            text = json.dumps(err.to_envelope())
            assert row.description not in text
            assert row.bin not in text
        elif row.quantity == 0:
            fails_with(confirmations, scope, ErrorCode.INSUFFICIENT_STOCK, **args)
        else:
            err = preview(confirmations, scope, **args)
            assert row.sku in err.details["proposed_action"]


def test_failed_calls_leave_no_audit_entry(confirmations, make_scope, store):
    scope = make_scope("LEEDS-01")
    fails_with(confirmations, scope, ErrorCode.INSUFFICIENT_STOCK, qty=241)
    fails_with(confirmations, scope, ErrorCode.INVALID_ARGUMENT, to_bin="Z-99")
    fails_with(confirmations, scope, ErrorCode.CONFIRMATION_INVALID, token="bogus")
    assert store.audit == []