from collections import Counter

from warehouse_mcp.store import Store


def test_stock_loaded():
    store = Store.load()
    assert len(store.stock) == 16
    assert len({row.sku for row in store.stock}) == 16
    assert Counter(r.site for r in store.stock) == {
        "LEEDS-01": 7,
        "READING-02": 5,
        "GLASGOW-03": 4,
    }


def test_zero_stock_is_a_real_row():
    store = Store.load()
    row = next(r for r in store.stock if r.sku == "SKU-8809")
    assert row.quantity == 0
    assert row.site == "GLASGOW-03"


def test_docks_loaded():
    store = Store.load()
    assert len(store.docks) == 18
    booked = [s for s in store.docks if s.status == "booked"]
    assert len(booked) == 5
    assert {s.carrier for s in booked} == {"Northbound Freight"}
    assert all(s.carrier is None for s in store.docks if s.status == "available")


def test_exceptions_start_empty():
    assert Store.load().exceptions == []


def test_each_load_is_independent():
    first = Store.load()
    first.stock[0].quantity = 999
    second = Store.load()
    assert second.stock[0].quantity == 240