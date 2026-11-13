import pytest

from warehouse_mcp.context import SessionContext
from warehouse_mcp.scope import Scope
from warehouse_mcp.store import Store

from warehouse_mcp.confirm import Confirmations


@pytest.fixture
def store():
    return Store.load()


@pytest.fixture
def make_scope(store):
    def _make(site: str) -> Scope:
        return Scope(store, SessionContext(caller_id="ops.test", site=site))

    return _make

@pytest.fixture
def confirmations():
    return Confirmations()