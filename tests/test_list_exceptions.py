from warehouse_mcp.models import ListExceptionsInput
from warehouse_mcp.tools.exceptions import list_exceptions


def make_exception(exception_id, site, status="open", sku="SKU-8801", note=None):
    return {
        "exception_id": exception_id,
        "site": site,
        "category": "damaged",
        "sku": sku,
        "description": "torn pallet",
        "status": status,
        "raised_at": "2026-04-08T09:00:00Z",
        "resolution_note": note,
    }


def call(scope, status="open"):
    return list_exceptions(scope, ListExceptionsInput(status=status))


def test_empty_store_is_a_success_not_an_error(make_scope):
    result = call(make_scope("LEEDS-01"))
    assert result["ok"] is True
    assert result["exceptions"] == []
    assert result["exception_count"] == 0


def test_defaults_to_open_only(make_scope, store):
    store.exceptions += [
        make_exception("EX-001", "LEEDS-01", "open"),
        make_exception("EX-002", "LEEDS-01", "closed", note="replaced"),
    ]
    result = list_exceptions(make_scope("LEEDS-01"), ListExceptionsInput())
    assert [e["exception_id"] for e in result["exceptions"]] == ["EX-001"]


def test_status_filters(make_scope, store):
    store.exceptions += [
        make_exception("EX-001", "LEEDS-01", "open"),
        make_exception("EX-002", "LEEDS-01", "closed", note="replaced"),
    ]
    scope = make_scope("LEEDS-01")
    assert [e["exception_id"] for e in call(scope, "closed")["exceptions"]] == ["EX-002"]
    assert call(scope, "all")["exception_count"] == 2
    assert call(scope, "closed")["exceptions"][0]["resolution_note"] == "replaced"


def test_only_own_site_is_listed(make_scope, store):
    store.exceptions += [
        make_exception("EX-001", "LEEDS-01"),
        make_exception("EX-002", "READING-02", sku="SKU-8805"),
    ]
    leeds = call(make_scope("LEEDS-01"), "all")
    assert [e["exception_id"] for e in leeds["exceptions"]] == ["EX-001"]

    reading = call(make_scope("READING-02"), "all")
    assert [e["exception_id"] for e in reading["exceptions"]] == ["EX-002"]


def test_internal_site_field_is_not_exposed(make_scope, store):
    store.exceptions.append(make_exception("EX-001", "LEEDS-01"))
    item = call(make_scope("LEEDS-01"))["exceptions"][0]
    assert "site" not in item
    assert set(item) == {
        "exception_id", "category", "sku", "description",
        "status", "raised_at", "resolution_note",
    }