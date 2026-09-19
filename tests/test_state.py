from warehouse_mcp.data_store import WarehouseDataStore
from warehouse_mcp.state import WarehouseState


def test_state_initializes_from_supplied_data():
    store = WarehouseDataStore(
        "data/stock_snapshot.csv",
        "data/dock_schedule.jsonl",
    )

    stock = store.load_stock()
    dock_schedule = store.load_dock_schedule()

    state = WarehouseState(stock, dock_schedule)

    assert len(state.stock) == 16
    assert len(state.dock_schedule) == 18
    assert state.exceptions == {}


def test_exception_ids_are_generated_sequentially():
    state = WarehouseState([], [])

    assert state.create_exception_id() == "EXC-0001"
    assert state.create_exception_id() == "EXC-0002"