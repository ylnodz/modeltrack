"""Smoke test: real network fetch through the tracker, real SQLite, real /health.

Not part of the unit suite (needs network). Run: uv run python scripts/smoke.py
"""

from __future__ import annotations

import asyncio
import os
import tempfile

from modeltrack.api import build_app
from modeltrack.config import Config
from modeltrack.state import Store
from modeltrack.tracker import Tracker


async def main() -> None:
    tmp = tempfile.mkdtemp()
    cfg = Config(
        discord_bot_token="x",
        discord_channel_id=1,
        openrouter_api_key=os.environ.get("OPENROUTER_API_KEY", ""),
        groq_api_key=os.environ.get("GROQ_API_KEY", ""),
        db_path=f"{tmp}/smoke.db",
    )

    sent: list[tuple[str, str, str]] = []

    async def sender(event, content=None):
        sent.append((event.kind, event.model.source, event.model.pk))

    store = Store(cfg.db_path)
    await store.open()
    tracker = Tracker(cfg, store, sender=sender)

    # cycle 1 — fresh DB, everything is "new" → seeded silently (no spam)
    s1 = await tracker.run_cycle(announce=True)
    print("cycle1 summary:", s1)
    print("cycle1 announced:", len(sent), "(expected 0 — fresh-DB seed)")
    counts = await store.counts()
    print("counts:", counts)

    free = await store.free_models("openrouter")
    print(f"openrouter free models: {len(free)}")
    for m in free[:6]:
        print(f"   {m.pk}  ctx={m.context}  in={m.price_in} out={m.price_out}")

    # cycle 2 — unchanged data ⇒ no events (no duplicate spam)
    s2 = await tracker.run_cycle(announce=True)
    print("cycle2 summary:", s2, "announced:", len(sent), "(expected 0 — unchanged)")

    # cycle 3 — forget one model ⇒ it must re-announce exactly once
    assert store._db is not None
    victim = await store._db.execute("SELECT pk FROM models WHERE source='openrouter' LIMIT 1")
    row = await victim.fetchone()
    await store._db.execute("DELETE FROM models WHERE source='openrouter' AND pk=?", (row[0],))
    await store._db.commit()
    print(f"deleted {row[0]} to simulate a brand-new model")
    sent.clear()
    s3 = await tracker.run_cycle(announce=True)
    print("cycle3 summary:", s3, "announced:", sent)

    app = build_app(cfg, store, tracker)
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/health")
        data = r.json()
        print("health:", r.status_code)
        print("  providers:", data["providers"])
        print("  models_total:", data["models_total"], "models_free:", data["models_free"])

    await store.close()


if __name__ == "__main__":
    asyncio.run(main())
