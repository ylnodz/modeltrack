"""Tracker orchestration tests (fake provider, real store)."""

from __future__ import annotations

import pytest

from modeltrack.models import Model
from modeltrack.state import Store
from modeltrack.tracker import Tracker


class FakeProvider:
    key = "fake"
    label = "Fake"
    filter_free = True
    watch_price = False
    watch_context = False

    def __init__(self, models):
        self._models = models

    def configured(self):
        return True

    async def fetch(self):
        return list(self._models)


class BoomProvider(FakeProvider):
    key = "boom"

    async def fetch(self):
        raise RuntimeError("provider exploded")


def mk(pk="m1", free=True) -> Model:
    return Model(source="fake", pk=pk, name=pk, is_free=free)


@pytest.fixture
async def store(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    await s.open()
    yield s
    await s.close()


async def _tracker(store, providers, config):
    sent = []

    async def sender(event, content=None):
        sent.append((event.kind, event.model.pk))

    t = Tracker(config, store, sender=sender)
    t.providers = providers
    return t, sent


async def test_first_cycle_seeds_silently(store, config):
    t, sent = await _tracker(store, [FakeProvider([mk("a")])], config)
    await t.run_cycle()
    assert sent == []
    assert len(await store.all_models()) == 1


async def test_later_cycle_announces_new(store, config):
    t, sent = await _tracker(store, [FakeProvider([mk("a")])], config)
    await t.run_cycle()  # seed
    # add a second model on the next cycle
    t.providers = [FakeProvider([mk("a"), mk("b")])]
    await t.run_cycle()
    assert sent == [("new", "b")]


async def test_filter_free_suppresses_paid(store, config):
    t, sent = await _tracker(store, [FakeProvider([mk("a")])], config)
    await t.run_cycle()
    t.providers = [FakeProvider([mk("a"), mk("paid", free=False)])]
    await t.run_cycle()
    assert sent == []  # filter_free provider must not announce paid models
    # ...but the model is still recorded in state
    assert len(await store.all_models()) == 2


async def test_one_failing_provider_does_not_kill_cycle(store, config):
    ok = FakeProvider([mk("a")])
    t, sent = await _tracker(store, [ok, BoomProvider([])], config)
    summary = await t.run_cycle()
    assert summary["ok"] == ["fake"]
    assert summary["failed"] == ["boom"]
    assert t.provider_status["boom"].startswith("error:")
