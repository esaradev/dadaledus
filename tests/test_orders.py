from daedalus.orders import OrderStore


def test_order_store_persists_events_and_dedupes_warnings(tmp_path):
    path = tmp_path / "orders.json"
    store = OrderStore(path)
    store.create({"id": "o1", "target": "https://example.com", "state": "quoted"})
    store.append_event("o1", "quote", "quoted")
    store.append_warning("o1", "memory unavailable")
    store.append_warning("o1", "memory unavailable")

    reopened = OrderStore(path)
    order = reopened.read("o1")
    assert order["events"][0]["kind"] == "quote"
    assert order["warnings"] == ["memory unavailable"]
    assert reopened.open_orders()[0]["id"] == "o1"


def test_order_store_conversion_counts_paid_and_lost(tmp_path):
    store = OrderStore(tmp_path / "orders.json")
    store.create({"id": "paid", "target": "x", "state": "funded"})
    store.create({"id": "lost", "target": "y", "state": "lost"})
    assert store.conversion() == 0.5
    assert store.counts() == {"jobs": 2, "paid": 1, "lost": 1, "delivered": 0}
