import pytest

from warehouse_mcp.context import (
    CallerContext,
    require_site_access,
)


def test_valid_caller_context():
    context = CallerContext(
        caller_id="operator-001",
        assigned_site="LEEDS-01",
    )

    assert context.caller_id == "operator-001"
    assert context.assigned_site == "LEEDS-01"


def test_invalid_site_is_rejected():
    with pytest.raises(ValueError):
        CallerContext(
            caller_id="operator-001",
            assigned_site="INVALID-SITE",
        )


def test_same_site_is_allowed():
    context = CallerContext(
        caller_id="operator-001",
        assigned_site="LEEDS-01",
    )

    require_site_access(context, "LEEDS-01")


def test_cross_site_access_is_rejected():
    context = CallerContext(
        caller_id="operator-001",
        assigned_site="LEEDS-01",
    )

    with pytest.raises(PermissionError):
        require_site_access(context, "READING-02")