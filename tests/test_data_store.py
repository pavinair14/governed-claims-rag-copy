from pathlib import Path

from warehouse_mcp.data_store import WarehouseDataStore


ROOT = Path(__file__).resolve().parents[1]

store = WarehouseDataStore(
    stock_file=ROOT / "data" / "stock_snapshot.csv",
    dock_file=ROOT / "data" / "dock_schedule.jsonl",
)


def test_load_stock():
    records = store.load_stock()

    assert len(records) == 16
    assert records[0]["sku"]
    assert records[0]["site"]
    assert records[0]["quantity"]


def test_load_dock_schedule():
    records = store.load_dock_schedule()

    assert len(records) == 18
    assert records[0]["site"]
    assert records[0]["date"]
    assert records[0]["slot"]
    assert records[0]["status"]