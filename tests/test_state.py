"""State store + diff logic tests."""

from __future__ import annotations

import pytest

from modeltrack.models import Model
from modeltrack.state import (
    BECAME_FREE,
    BECAME_PAID,
    NEW,
    PRICE_CHANGE,
    Store,
)


def model(pk="m1", *, free=False, pin=1.0, pout=2.0, ctx=1000) -> Model:
    return Model(
        source="test",
        pk=pk,
        name=f"Model {pk}",
        url="https://example.com",
        is_free=free,
        price_in=pin,
        price_out=pout,
        context=ctx,
    )


@pytest.fixture
async def store(tmp_path):
    s = Store(str(tmp_path / "state.db"))
    await s.open()
    yield s
    await s.close()


async def test_new_model_emits_new(store):
    events = await store.diff_and_apply(
        {"test": [model()]}, watch_price={"test"}, watch_context={"test"}
    )
    assert [e.kind for e in events] == [NEW]
    assert len(await store.all_models()) == 1


async def test_no_duplicate_on_unchanged(store):
    await store.diff_and_apply({"test": [model()]}, watch_price={"test"}, watch_context={"test"})
    events = await store.diff_and_apply(
        {"test": [model()]}, watch_price={"test"}, watch_context={"test"}
    )
    assert events == []


async def test_became_free_and_paid(store):
    await store.diff_and_apply(
        {"test": [model(free=False)]}, watch_price={"test"}, watch_context={"test"}
    )
    events = await store.diff_and_apply(
        {"test": [model(free=True)]}, watch_price={"test"}, watch_context={"test"}
    )
    assert [e.kind for e in events] == [BECAME_FREE]

    events = await store.diff_and_apply(
        {"test": [model(free=False)]}, watch_price={"test"}, watch_context={"test"}
    )
    assert [e.kind for e in events] == [BECAME_PAID]


async def test_price_change(store):
    await store.diff_and_apply(
        {"test": [model(pin=1.0)]}, watch_price={"test"}, watch_context={"test"}
    )
    events = await store.diff_and_apply(
        {"test": [model(pin=3.0)]}, watch_price={"test"}, watch_context={"test"}
    )
    assert PRICE_CHANGE in {e.kind for e in events}


async def test_state_survives_no_24h_amnesia(store):
    """A model seen once is never re-announced due to time passing."""
    await store.diff_and_apply({"test": [model()]}, watch_price={"test"}, watch_context={"test"})
    await store._db.execute("UPDATE models SET last_seen = last_seen - 200000")  # > 2 days
    await store._db.commit()
    events = await store.diff_and_apply(
        {"test": [model()]}, watch_price={"test"}, watch_context={"test"}
    )
    assert events == []


async def test_free_models_query(store):
    await store.diff_and_apply(
        {"test": [model("a", free=True), model("b", free=False)]},
        watch_price={"test"},
        watch_context={"test"},
    )
    free = await store.free_models()
    assert [m.pk for m in free] == ["a"]
    assert await store.free_models("other") == []


async def test_counts(store):
    await store.diff_and_apply(
        {"test": [model("a", free=True), model("b", free=False)]},
        watch_price={"test"},
        watch_context={"test"},
    )
    counts = await store.counts()
    assert counts["test"] == (2, 1)


async def test_fresh_flag(tmp_path):
    s = Store(str(tmp_path / "new.db"))
    await s.open()
    assert s.is_fresh is True
    await s.close()
    s2 = Store(str(tmp_path / "new.db"))
    await s2.open()
    assert s2.is_fresh is False
    await s2.close()
