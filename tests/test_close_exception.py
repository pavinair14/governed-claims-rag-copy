import json

import pytest

from warehouse_mcp.errors import ErrorCode, ToolError
from warehouse_mcp.models import (
    CloseExceptionInput,
    ListExceptionsInput,
    RaiseExceptionInput,
)
from warehouse_mcp.tools.exceptions import (
    close_exception,
    list_exceptions,
    raise_exception,
)


def seed(store, exception_id="EX-001", site="LEEDS-01", status="open", sku="SKU-8801",
         description="torn pallet", note=None):
    store.exceptions.append(
        {
            "exception_id": exception_id,
            "site": site,
            "category": "damaged",
            "sku": sku,
            "description": description,
            "status": status,
            "raised_at": "2026-04-08T09:00:00+00:00",
            "resolution_note": note,
        }
    )


def make_args(exception_id="EX-001", note="replaced the pallet", token=None):
    return CloseExceptionInput(
        exception_id=exception_id, resolution_note=note, confirmation_token=token
    )


def preview(confirmations, scope, **kw):
    with pytest.raises(ToolError) as caught:
        close_exception(confirmations, scope, make_args(**kw))
    assert caught.value.code == ErrorCode.CONFIRMATION_REQUIRED
    return caught.value


def fails_with(confirmations, scope, code, **kw):
    with pytest.raises(ToolError) as caught:
        close_exception(confirmations, scope, make_args(**kw))
    assert caught.value.code == code
    return caught.value


def listed(scope, status):
    result = list_exceptions(scope, ListExceptionsInput(status=status))
    return {e["exception_id"]: e for e in result["exceptions"]}


def test_preview_describes_the_exception_and_warns_closing_is_final(
    confirmations, make_scope, store
):
    seed(store)
    err = preview(confirmations, make_scope("LEEDS-01"))

    text = err.details["proposed_action"]
    assert text.startswith(
        "Close exception EX-001 (damaged, SKU-8801: torn pallet) at LEEDS-01 with the "
        "resolution note: replaced the pallet."
    )
    assert "no way to reopen" in text
    assert listed(make_scope("LEEDS-01"), "open").keys() == {"EX-001"}
    assert store.audit == []


def test_confirmed_close_is_applied_and_visible_to_a_later_read(
    confirmations, make_scope, store
):
    seed(store)
    scope = make_scope("LEEDS-01")
    token = preview(confirmations, scope).details["confirmation_token"]

    result = close_exception(confirmations, scope, make_args(token=token))

    assert result["ok"] is True
    assert result["applied"] is True
    assert result["exception_id"] == "EX-001"
    assert result["status"] == "closed"
    assert result["resolution_note"] == "replaced the pallet"
    assert "site" in result and result["site"] == "LEEDS-01"

    assert listed(scope, "open") == {}
    assert listed(scope, "closed")["EX-001"]["resolution_note"] == "replaced the pallet"
    assert len(store.audit) == 1
    entry = store.audit[0]
    assert entry["action"] == "close_exception"
    assert entry["before"]["status"] == "open"
    assert entry["after"]["status"] == "closed"


def test_the_example_call_in_the_preview_commits_successfully(
    confirmations, make_scope, store
):
    seed(store)
    scope = make_scope("LEEDS-01")
    example = preview(confirmations, scope).example_call

    close_exception(confirmations, scope, CloseExceptionInput(**example["arguments"]))
    assert listed(scope, "closed").keys() == {"EX-001"}


def test_full_lifecycle_raise_then_list_then_close(confirmations, make_scope):
    scope = make_scope("LEEDS-01")
    with pytest.raises(ToolError) as caught:
        raise_exception(
            confirmations,
            scope,
            RaiseExceptionInput(category="damaged", sku="SKU-8801", description="torn pallet"),
        )
    token = caught.value.details["confirmation_token"]
    raised = raise_exception(
        confirmations,
        scope,
        RaiseExceptionInput(
            category="damaged",
            sku="SKU-8801",
            description="torn pallet",
            confirmation_token=token,
        ),
    )

    exception_id = next(iter(listed(scope, "open")))
    assert exception_id == raised["exception_id"]

    token = preview(confirmations, scope, exception_id=exception_id).details[
        "confirmation_token"
    ]
    close_exception(
        confirmations, scope, make_args(exception_id=exception_id, token=token)
    )
    assert listed(scope, "open") == {}


def test_already_closed_fails_at_preview_with_the_existing_note_and_no_token(
    confirmations, make_scope, store
):
    seed(store, status="closed", note="replaced by Dave")
    err = fails_with(confirmations, make_scope("LEEDS-01"), ErrorCode.ALREADY_CLOSED)

    assert err.field == "exception_id"
    assert err.details == {"resolution_note": "replaced by Dave"}
    assert "Do not retry" in err.suggested_action
    assert confirmations.outstanding() == 0
    assert store.audit == []


def test_closing_twice_is_already_closed_and_keeps_the_first_note(
    confirmations, make_scope, store
):
    seed(store)
    scope = make_scope("LEEDS-01")
    token = preview(confirmations, scope).details["confirmation_token"]
    close_exception(confirmations, scope, make_args(token=token))

    err = fails_with(confirmations, scope, ErrorCode.ALREADY_CLOSED, note="a second note")
    assert err.details["resolution_note"] == "replaced the pallet"
    assert listed(scope, "closed")["EX-001"]["resolution_note"] == "replaced the pallet"
    assert len(store.audit) == 1


def test_closed_by_someone_else_between_preview_and_commit(
    confirmations, make_scope, store
):
    seed(store)
    scope = make_scope("LEEDS-01")
    token = preview(confirmations, scope).details["confirmation_token"]

    store.exceptions[0]["status"] = "closed"
    store.exceptions[0]["resolution_note"] = "closed by a colleague"

    fails_with(confirmations, scope, ErrorCode.ALREADY_CLOSED, token=token)
    assert listed(scope, "closed")["EX-001"]["resolution_note"] == "closed by a colleague"


def test_token_for_one_note_cannot_close_with_another(confirmations, make_scope, store):
    seed(store)
    scope = make_scope("LEEDS-01")
    token = preview(confirmations, scope, note="replaced the pallet").details[
        "confirmation_token"
    ]

    fails_with(
        confirmations,
        scope,
        ErrorCode.CONFIRMATION_INVALID,
        note="something else entirely",
        token=token,
    )
    assert listed(scope, "open").keys() == {"EX-001"}


def test_token_for_one_exception_cannot_close_another(confirmations, make_scope, store):
    seed(store, "EX-001")
    seed(store, "EX-002", description="crushed corner")
    scope = make_scope("LEEDS-01")
    token = preview(confirmations, scope, exception_id="EX-001").details[
        "confirmation_token"
    ]

    fails_with(
        confirmations,
        scope,
        ErrorCode.CONFIRMATION_INVALID,
        exception_id="EX-002",
        token=token,
    )
    assert listed(scope, "open").keys() == {"EX-001", "EX-002"}


def test_unknown_id_is_not_found_with_a_way_forward(confirmations, make_scope, store):
    seed(store)
    err = fails_with(
        confirmations, make_scope("LEEDS-01"), ErrorCode.NOT_FOUND, exception_id="EX-999"
    )
    assert err.field == "exception_id"
    assert err.example_call["tool"] == "list_exceptions"
    assert confirmations.outstanding() == 0


def test_other_sites_exception_is_denied_without_leaking(
    confirmations, make_scope, store
):
    seed(
        store,
        "EX-001",
        site="READING-02",
        sku="SKU-8805",
        description="crushed corner protectors",
    )
    err = fails_with(
        confirmations, make_scope("LEEDS-01"), ErrorCode.SITE_ACCESS_DENIED
    )

    text = json.dumps(err.to_envelope())
    for fragment in ["crushed", "SKU-8805", "READING", "Corner protector"]:
        assert fragment not in text
    assert confirmations.outstanding() == 0
    assert store.exceptions[0]["status"] == "open"


def test_same_site_close_works_alongside_cross_site_refusal(
    confirmations, make_scope, store
):
    seed(store, "EX-001", site="LEEDS-01")
    seed(store, "EX-002", site="READING-02", sku="SKU-8805")
    leeds = make_scope("LEEDS-01")

    token = preview(confirmations, leeds, exception_id="EX-001").details[
        "confirmation_token"
    ]
    close_exception(confirmations, leeds, make_args(exception_id="EX-001", token=token))

    fails_with(
        confirmations, leeds, ErrorCode.SITE_ACCESS_DENIED, exception_id="EX-002"
    )
    assert listed(make_scope("READING-02"), "open").keys() == {"EX-002"}


def test_failed_calls_leave_no_audit_entry(confirmations, make_scope, store):
    seed(store, "EX-001", status="closed", note="done")
    seed(store, "EX-002")  # open, so a bogus token gets as far as the token check
    scope = make_scope("LEEDS-01")

    fails_with(confirmations, scope, ErrorCode.ALREADY_CLOSED, exception_id="EX-001")
    fails_with(confirmations, scope, ErrorCode.NOT_FOUND, exception_id="EX-999")
    fails_with(
        confirmations,
        scope,
        ErrorCode.CONFIRMATION_INVALID,
        exception_id="EX-002",
        token="bogus",
    )

    assert store.audit == []
    assert listed(scope, "open").keys() == {"EX-002"}