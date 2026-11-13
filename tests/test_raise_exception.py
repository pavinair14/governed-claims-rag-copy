import json
from datetime import datetime

import pytest

from warehouse_mcp.context import SITES
from warehouse_mcp.errors import ErrorCode, ToolError
from warehouse_mcp.models import ListExceptionsInput, RaiseExceptionInput
from warehouse_mcp.store import Store
from warehouse_mcp.tools.exceptions import list_exceptions, raise_exception


def make_args(
    category="damaged", sku="SKU-8801", description="torn pallet", token=None
):
    return RaiseExceptionInput(
        category=category,
        sku=sku,
        description=description,
        confirmation_token=token,
    )


def preview(confirmations, scope, **kw):
    with pytest.raises(ToolError) as caught:
        raise_exception(confirmations, scope, make_args(**kw))
    assert caught.value.code == ErrorCode.CONFIRMATION_REQUIRED
    return caught.value


def fails_with(confirmations, scope, code, **kw):
    with pytest.raises(ToolError) as caught:
        raise_exception(confirmations, scope, make_args(**kw))
    assert caught.value.code == code
    return caught.value


def do_raise(confirmations, scope, **kw):
    token = preview(confirmations, scope, **kw).details["confirmation_token"]
    return raise_exception(confirmations, scope, make_args(token=token, **kw))


def listed(scope, status="all"):
    result = list_exceptions(scope, ListExceptionsInput(status=status))
    return [e["exception_id"] for e in result["exceptions"]]


def test_preview_describes_the_exception_and_changes_nothing(
    confirmations, make_scope, store
):
    err = preview(confirmations, make_scope("LEEDS-01"))

    assert err.details["proposed_action"] == (
        "Raise a damaged exception for SKU-8801 (Pallet wrap, 500mm clear) at "
        "LEEDS-01: torn pallet"
    )
    assert "EX-" not in err.details["proposed_action"]
    assert store.exceptions == []
    assert store.audit == []


def test_confirmed_exception_gets_a_server_generated_id(confirmations, make_scope, store):
    scope = make_scope("LEEDS-01")
    result = do_raise(confirmations, scope)

    assert result["ok"] is True
    assert result["applied"] is True
    assert result["site"] == "LEEDS-01"
    assert result["exception_id"] == "EX-001"
    assert result["category"] == "damaged"
    assert result["sku"] == "SKU-8801"
    assert result["description"] == "torn pallet"
    assert result["status"] == "open"
    assert result["resolution_note"] is None
    datetime.fromisoformat(result["raised_at"])  # a real timestamp
    assert "site" in store.exceptions[0] and "site" not in result.get("exception", {})

    assert len(store.audit) == 1
    entry = store.audit[0]
    assert entry["action"] == "raise_exception"
    assert entry["exception_id"] == "EX-001"
    assert entry["site"] == "LEEDS-01"


def test_a_raised_exception_appears_in_list_exceptions(confirmations, make_scope):
    scope = make_scope("LEEDS-01")
    do_raise(confirmations, scope)

    assert listed(scope, "open") == ["EX-001"]
    assert listed(scope, "closed") == []


def test_ids_count_up(confirmations, make_scope):
    scope = make_scope("LEEDS-01")
    first = do_raise(confirmations, scope)
    second = do_raise(confirmations, scope, category="missing", sku="SKU-8802")

    assert (first["exception_id"], second["exception_id"]) == ("EX-001", "EX-002")


def test_ids_are_unique_across_sites_but_each_site_lists_only_its_own(
    confirmations, make_scope
):
    leeds, reading = make_scope("LEEDS-01"), make_scope("READING-02")
    a = do_raise(confirmations, leeds)
    b = do_raise(confirmations, reading, sku="SKU-8805")

    assert (a["exception_id"], b["exception_id"]) == ("EX-001", "EX-002")
    assert listed(leeds) == ["EX-001"]
    assert listed(reading) == ["EX-002"]
    assert listed(make_scope("GLASGOW-03")) == []


def test_missing_exception_on_a_zero_stock_sku_is_valid(confirmations, make_scope):
    result = do_raise(
        confirmations, make_scope("GLASGOW-03"), category="missing", sku="SKU-8809"
    )
    assert result["sku"] == "SKU-8809"
    assert result["category"] == "missing"


def test_the_example_call_in_the_preview_commits_successfully(confirmations, make_scope):
    scope = make_scope("LEEDS-01")
    example = preview(confirmations, scope).example_call

    raise_exception(confirmations, scope, RaiseExceptionInput(**example["arguments"]))
    assert listed(scope) == ["EX-001"]


def test_unknown_sku_is_not_found_and_issues_no_token(confirmations, make_scope, store):
    err = fails_with(
        confirmations, make_scope("LEEDS-01"), ErrorCode.NOT_FOUND, sku="SKU-0000"
    )
    assert err.example_call["tool"] == "search_stock"
    assert confirmations.outstanding() == 0
    assert store.exceptions == []


def test_other_sites_sku_is_denied_without_leaking(confirmations, make_scope, store):
    err = fails_with(
        confirmations, make_scope("LEEDS-01"), ErrorCode.SITE_ACCESS_DENIED, sku="SKU-8805"
    )
    text = json.dumps(err.to_envelope())
    for fragment in ["Corner protector", "B-03-7", "READING"]:
        assert fragment not in text
    assert confirmations.outstanding() == 0
    assert store.exceptions == []


def test_token_for_one_description_cannot_raise_another(confirmations, make_scope, store):
    scope = make_scope("LEEDS-01")
    token = preview(confirmations, scope, description="torn pallet").details[
        "confirmation_token"
    ]

    fails_with(
        confirmations,
        scope,
        ErrorCode.CONFIRMATION_INVALID,
        description="crushed pallet",
        token=token,
    )
    assert store.exceptions == []


def test_token_for_one_category_cannot_raise_another(confirmations, make_scope, store):
    scope = make_scope("LEEDS-01")
    token = preview(confirmations, scope, category="damaged").details["confirmation_token"]

    fails_with(
        confirmations, scope, ErrorCode.CONFIRMATION_INVALID, category="missing", token=token
    )
    assert store.exceptions == []


def test_token_cannot_raise_twice(confirmations, make_scope, store):
    scope = make_scope("LEEDS-01")
    token = preview(confirmations, scope).details["confirmation_token"]
    raise_exception(confirmations, scope, make_args(token=token))

    fails_with(confirmations, scope, ErrorCode.CONFIRMATION_INVALID, token=token)
    assert len(store.exceptions) == 1


@pytest.mark.parametrize("site", SITES)
def test_own_skus_reach_a_preview_and_every_other_sites_are_denied(
    site, confirmations, make_scope
):
    scope = make_scope(site)
    for row in Store.load().stock:
        if row.site == site:
            err = preview(confirmations, scope, sku=row.sku)
            assert row.sku in err.details["proposed_action"]
        else:
            err = fails_with(
                confirmations, scope, ErrorCode.SITE_ACCESS_DENIED, sku=row.sku
            )
            text = json.dumps(err.to_envelope())
            assert row.description not in text
            assert row.bin not in text


def test_failed_calls_leave_no_audit_entry(confirmations, make_scope, store):
    scope = make_scope("LEEDS-01")
    fails_with(confirmations, scope, ErrorCode.NOT_FOUND, sku="SKU-0000")
    fails_with(confirmations, scope, ErrorCode.CONFIRMATION_INVALID, token="bogus")
    assert store.audit == []