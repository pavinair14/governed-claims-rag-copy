import pytest

from warehouse_mcp.context import SITES, SessionContext, StartupError, load_context


@pytest.mark.parametrize("site", SITES)
def test_valid_context_for_each_site(site):
    ctx = load_context({"KESTREL_CALLER_ID": "ops.test", "KESTREL_ASSIGNED_SITE": site})
    assert ctx == SessionContext(caller_id="ops.test", site=site)


def test_missing_site_refuses_to_start():
    with pytest.raises(StartupError):
        load_context({"KESTREL_CALLER_ID": "ops.test"})


@pytest.mark.parametrize("bad", ["", "   ", "leeds-01", "MANCHESTER-04"])
def test_invalid_site_refuses_to_start(bad):
    with pytest.raises(StartupError):
        load_context({"KESTREL_CALLER_ID": "ops.test", "KESTREL_ASSIGNED_SITE": bad})


@pytest.mark.parametrize("bad", ["", "   "])
def test_missing_caller_refuses_to_start(bad):
    with pytest.raises(StartupError):
        load_context({"KESTREL_CALLER_ID": bad, "KESTREL_ASSIGNED_SITE": "LEEDS-01"})


def test_context_cannot_be_changed():
    ctx = load_context({"KESTREL_CALLER_ID": "ops.test", "KESTREL_ASSIGNED_SITE": "LEEDS-01"})
    with pytest.raises(AttributeError):
        ctx.site = "READING-02"