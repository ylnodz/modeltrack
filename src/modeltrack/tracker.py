"""Tracking orchestrator: fetch → diff → notify."""

from __future__ import annotations

import asyncio
import logging
import time

from .config import Config
from .providers import build_providers
from .state import BECAME_FREE, Event, Store

logger = logging.getLogger(__name__)


class Tracker:
    def __init__(self, config: Config, store: Store, sender) -> None:  # noqa: ANN001
        self.config = config
        self.store = store
        self.sender = sender  # async callable(embed, content) -> None
        self.providers = build_providers(config)
        self.last_run: float | None = None
        self.last_summary: dict = {}
        self.provider_status: dict[str, str] = {}

    async def run_cycle(self, *, announce: bool = True) -> dict:
        started = time.time()
        fetched: dict[str, list] = {}
        ok, failed = [], []

        configured = [p for p in self.providers if p.configured()]

        async def _one(provider):
            # Bounded per-provider so one slow provider cannot stall the cycle.
            models = await asyncio.wait_for(
                provider.fetch(), timeout=self.config.provider_timeout_seconds
            )
            return provider.key, models

        results = await asyncio.gather(*(_one(p) for p in configured), return_exceptions=True)
        for provider, result in zip(configured, results, strict=True):
            if isinstance(result, BaseException):
                failed.append(provider.key)
                self.provider_status[provider.key] = f"error: {type(result).__name__}"
                logger.warning("provider failed key=%s err=%s", provider.key, result)
            else:
                key, models = result
                fetched[key] = models
                ok.append(key)
                self.provider_status[key] = f"ok ({len(models)})"
        for p in self.providers:
            if not p.configured():
                self.provider_status[p.key] = "unconfigured"

        watch_price = {p.key for p in self.providers if p.watch_price}
        watch_context = {p.key for p in self.providers if p.watch_context}

        events = await self.store.diff_and_apply(
            fetched, watch_price=watch_price, watch_context=watch_context
        )

        # First-ever run on an empty DB: seed silently rather than spamming.
        seeding = not await self.store.get_meta("seeded")
        if not announce or seeding:
            events = []
        await self.store.set_meta("seeded", "1")

        by_key = {p.key: p for p in self.providers}

        def _wanted(event: Event) -> bool:
            provider = by_key.get(event.model.source)
            # A provider that only tracks free models does not announce paid ones.
            if provider and provider.filter_free and not event.model.is_free:
                return False
            return True

        emitted = 0
        for event in events:
            if not _wanted(event):
                continue
            try:
                await self._emit(event)
                emitted += 1
                await self.store.record_event(event)
            except Exception as exc:  # noqa: BLE001 - never let one event kill cycle
                logger.warning("emit failed kind=%s pk=%s err=%s", event.kind, event.model.pk, exc)

        elapsed = time.time() - started
        self.last_run = time.time()
        self.last_summary = {
            "ok": ok,
            "failed": failed,
            "models": sum(len(v) for v in fetched.values()),
            "events": emitted,
            "elapsed_ms": round(elapsed * 1000),
        }
        logger.info(
            "cycle done ok=%d failed=%d models=%d events=%d elapsed_ms=%d",
            len(ok),
            len(failed),
            self.last_summary["models"],
            emitted,
            self.last_summary["elapsed_ms"],
        )
        return self.last_summary

    async def _emit(self, event: Event) -> None:
        content = None
        if event.kind == BECAME_FREE and self.config.announce_mention:
            content = "@here"
        await self.sender(event, content)
