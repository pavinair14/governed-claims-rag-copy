import json

import pytest

from warehouse_mcp.context import SITES
from warehouse_mcp.errors import ErrorCode, ToolError
from warehouse_mcp.models import CorrectStockInput, GetStockInput
from warehouse_mcp.store import Store
from warehouse_mcp.tools.stock import correct_stock, get_stock


def make_args(
    sku="SKU-8802", bin="A-12-4", qty=175, reason="recount", token=None
):
    return CorrectStockInput(
        sku=sku,
        bin=bin,
        corrected_quantity=qty,
        reason=reason,
        confirmation_token=token,
    )


def preview(confirmations, scope, **kw):
    with pytest.raises(ToolError) as caught:
        correct_stock(confirmations, scope, make_args(**kw))
    assert caught.value.code == ErrorCode.CONFIRMATION_REQUIRED
    return caught.value


def fails_with(confirmations, scope, code, **kw):
    with pytest.raises(ToolError) as caught:
        correct_stock(confirmations, scope, make_args(**kw))
    assert caught.value.code == code
    return caught.value


def total(scope, sku):
    return get_stock(scope, GetStockInput(sku=sku))["total_quantity"]


def test_preview_states_old_and_new_quantity_and_changes_nothing(
    confirmations, make_scope, store
):
    scope = make_scope("LEEDS-01")
    err = preview(confirmations, scope)

    assert err.details["proposed_action"] == (
        "Correct the recorded quantity of SKU-8802 (Pallet wrap, 500mm black) in bin "
        "A-12-4 at LEEDS-01 from 180 to 175 each (difference -5). Reason: recount. "
        "This feeds the month-end stock count."
    )
    assert total(scope, "SKU-8802") == 180
    assert store.audit == []


def test_confirmed_correction_is_applied_and_visible_to_a_later_read(
    confirmations, make_scope, store
):
    scope = make_scope("LEEDS-01")
    token = preview(confirmations, scope).details["confirmation_token"]

    result = correct_stock(confirmations, scope, make_args(token=token))

    assert result == {
        "ok": True,
        "site": "LEEDS-01",
        "applied": True,
        "sku": "SKU-8802",
        "bin": "A-12-4",
        "unit": "each",
        "previous_quantity": 180,
        "corrected_quantity": 175,
        "difference": -5,
        "reason": "recount",
    }
    assert total(scope, "SKU-8802") == 175
    assert len(store.audit) == 1
    entry = store.audit[0]
    assert entry["action"] == "correct_stock"
    assert entry["before"] == {"quantity": 180}
    assert entry["after"] == {"quantity": 175}
    assert entry["reason"] == "recount"
    assert entry["site"] == "LEEDS-01"


def test_a_correction_upwards_shows_a_positive_difference(confirmations, make_scope):
    scope = make_scope("LEEDS-01")
    err = preview(confirmations, scope, qty=200)
    assert "(difference +20)" in err.details["proposed_action"]


def test_zero_is_a_valid_corrected_quantity(confirmations, make_scope):
    scope = make_scope("LEEDS-01")
    token = preview(confirmations, scope, sku="SKU-8801", bin="A-12-3", qty=0).details[
        "confirmation_token"
    ]
    correct_stock(
        confirmations, scope, make_args(sku="SKU-8801", bin="A-12-3", qty=0, token=token)
    )
    assert total(scope, "SKU-8801") == 0


def test_the_example_call_in_the_preview_commits_successfully(confirmations, make_scope):
    scope = make_scope("LEEDS-01")
    example = preview(confirmations, scope).example_call

    correct_stock(confirmations, scope, CorrectStockInput(**example["arguments"]))
    assert total(scope, "SKU-8802") == 175


def test_same_quantity_is_refused_as_nothing_to_correct(confirmations, make_scope, store):
    scope = make_scope("LEEDS-01")
    err = fails_with(confirmations, scope, ErrorCode.INVALID_ARGUMENT, qty=180)

    assert err.field == "corrected_quantity"
    assert err.details["recorded_quantity"] == 180
    assert confirmations.outstanding() == 0
    assert store.audit == []


def test_wrong_bin_lists_the_bins_that_hold_the_sku(confirmations, make_scope):
    err = fails_with(
        confirmations, make_scope("LEEDS-01"), ErrorCode.NOT_FOUND, bin="A-99-9"
    )
    assert err.field == "bin"
    assert err.details["bins_holding_sku"] == ["A-12-4"]
    assert err.example_call["arguments"]["bin"] == "A-12-4"
    assert confirmations.outstanding() == 0


def test_unknown_sku_is_not_found(confirmations, make_scope):
    fails_with(
        confirmations, make_scope("LEEDS-01"), ErrorCode.NOT_FOUND, sku="SKU-0000"
    )


def test_other_sites_sku_is_denied_without_leaking(confirmations, make_scope):
    err = fails_with(
        confirmations,
        make_scope("LEEDS-01"),
        ErrorCode.SITE_ACCESS_DENIED,
        sku="SKU-8805",
        bin="B-03-7",
    )
    text = json.dumps(err.to_envelope())
    for fragment in ["Corner protector", "1200", "B-03-7", "READING"]:
        assert fragment not in text
    assert confirmations.outstanding() == 0


def test_other_sites_bin_with_own_sku_is_denied(confirmations, make_scope):
    fails_with(
        confirmations, make_scope("LEEDS-01"), ErrorCode.SITE_ACCESS_DENIED, bin="B-03-7"
    )


def test_quantity_changed_after_the_preview_voids_the_token(confirmations, make_scope):
    scope = make_scope("LEEDS-01")
    token = preview(confirmations, scope).details["confirmation_token"]

    scope.rows_for_sku("SKU-8802")[0].quantity = 170  # someone else corrects it first

    fails_with(confirmations, scope, ErrorCode.CONFIRMATION_INVALID, token=token)
    assert total(scope, "SKU-8802") == 170


def test_token_for_one_quantity_cannot_apply_another(confirmations, make_scope):
    scope = make_scope("LEEDS-01")
    token = preview(confirmations, scope, qty=175).details["confirmation_token"]

    fails_with(confirmations, scope, ErrorCode.CONFIRMATION_INVALID, qty=100, token=token)
    assert total(scope, "SKU-8802") == 180


def test_replaying_a_used_token_changes_nothing(confirmations, make_scope, store):
    scope = make_scope("LEEDS-01")
    token = preview(confirmations, scope).details["confirmation_token"]
    correct_stock(confirmations, scope, make_args(token=token))

    # The record already shows 175, so the replay is refused as "nothing to correct".
    fails_with(confirmations, scope, ErrorCode.INVALID_ARGUMENT, token=token)

    assert total(scope, "SKU-8802") == 175
    assert len(store.audit) == 1

def test_a_correction_only_changes_the_callers_own_site(confirmations, make_scope):
    leeds = make_scope("LEEDS-01")
    token = preview(confirmations, leeds).details["confirmation_token"]
    correct_stock(confirmations, leeds, make_args(token=token))

    assert total(make_scope("READING-02"), "SKU-8805") == 1200
    assert total(make_scope("GLASGOW-03"), "SKU-8809") == 0


@pytest.mark.parametrize("site", SITES)
def test_own_skus_reach_a_preview_and_every_other_sites_are_denied(
    site, confirmations, make_scope
):
    scope = make_scope(site)
    for row in Store.load().stock:
        args = dict(sku=row.sku, bin=row.bin, qty=row.quantity + 1)
        if row.site == site:
            err = preview(confirmations, scope, **args)
            assert row.sku in err.details["proposed_action"]
        else:
            err = fails_with(confirmations, scope, ErrorCode.SITE_ACCESS_DENIED, **args)
            text = json.dumps(err.to_envelope())
            assert row.description not in text
            assert row.bin not in text


def test_failed_calls_leave_no_audit_entry(confirmations, make_scope, store):
    scope = make_scope("LEEDS-01")
    fails_with(confirmations, scope, ErrorCode.NOT_FOUND, bin="A-99-9")
    fails_with(confirmations, scope, ErrorCode.CONFIRMATION_INVALID, token="bogus")
    assert store.audit == []