"""SQLite-backed state store.

Replaces v1's ``state.json``. No time-based deletion: a model's history is
permanent, so re-announcement happens only on a genuine state transition
(new, became_free, became_paid, price_change, context_change, deprecated).
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import aiosqlite

from .models import Model

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS models (
  source TEXT NOT NULL,
  pk TEXT NOT NULL,
  name TEXT, author TEXT, url TEXT,
  is_free INTEGER NOT NULL DEFAULT 0,
  free_note TEXT, context INTEGER,
  modalities TEXT, price_in REAL, price_out REAL,
  description TEXT, extra TEXT,
  first_seen REAL, last_seen REAL, missing_since REAL,
  PRIMARY KEY (source, pk)
);
CREATE TABLE IF NOT EXISTS price_history (
  source TEXT NOT NULL, pk TEXT NOT NULL, ts REAL NOT NULL,
  price_in REAL, price_out REAL, is_free INTEGER
);
CREATE INDEX IF NOT EXISTS idx_price_hist ON price_history (source, pk, ts);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL NOT NULL, source TEXT, pk TEXT, kind TEXT, detail TEXT
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""

# Event kinds
NEW = "new"
BECAME_FREE = "became_free"
BECAME_PAID = "became_paid"
PRICE_CHANGE = "price_change"
CONTEXT_CHANGE = "context_change"
DEPRECATED = "deprecated"


@dataclass
class Event:
    kind: str
    model: Model
    detail: str = ""
    old: dict[str, Any] = field(default_factory=dict)


def _row_to_model(row: aiosqlite.Row) -> Model:
    mods = row["modalities"] or ""
    return Model(
        source=row["source"],
        pk=row["pk"],
        name=row["name"] or row["pk"],
        author=row["author"] or "",
        url=row["url"] or "",
        is_free=bool(row["is_free"]),
        free_note=row["free_note"],
        context=row["context"],
        modalities=[m for m in mods.split(",") if m] or ["text"],
        price_in=row["price_in"],
        price_out=row["price_out"],
        description=row["description"] or "",
        extra=_safe_json(row["extra"]),
    )


def _safe_json(raw: Any) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


class Store:
    """Async SQLite state store (WAL mode, single writer)."""

    def __init__(self, path: str) -> None:
        self.path = path
        self._db: aiosqlite.Connection | None = None
        self._fresh = False

    @property
    def is_fresh(self) -> bool:
        """True when the DB file did not exist before ``open()``."""
        return self._fresh

    async def open(self) -> None:
        existed = Path(self.path).exists()
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self.path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA synchronous=NORMAL")
        await self._db.executescript(SCHEMA)
        await self._db.commit()
        self._fresh = not existed
        if self._fresh:
            await self._db.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES ('resumed', ?)",
                (str(time.time()),),
            )
            await self._db.commit()
        logger.info("state opened path=%s fresh=%s", self.path, self._fresh)

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None

    # ── reads ───────────────────────────────────────────
    async def all_models(self, source: str | None = None) -> list[Model]:
        assert self._db is not None
        if source:
            cur = await self._db.execute("SELECT * FROM models WHERE source=?", (source,))
        else:
            cur = await self._db.execute("SELECT * FROM models")
        rows = await cur.fetchall()
        return [_row_to_model(r) for r in rows]

    async def free_models(self, source: str | None = None) -> list[Model]:
        assert self._db is not None
        if source:
            cur = await self._db.execute(
                "SELECT * FROM models WHERE is_free=1 AND source=? ORDER BY name", (source,)
            )
        else:
            cur = await self._db.execute(
                "SELECT * FROM models WHERE is_free=1 ORDER BY source, name"
            )
        rows = await cur.fetchall()
        return [_row_to_model(r) for r in rows]

    async def counts(self) -> dict[str, tuple[int, int]]:
        """source -> (total, free)"""
        assert self._db is not None
        cur = await self._db.execute(
            "SELECT source, COUNT(*), SUM(is_free) FROM models GROUP BY source"
        )
        rows = await cur.fetchall()
        return {r[0]: (r[1] or 0, r[2] or 0) for r in rows}

    async def get_meta(self, key: str) -> str | None:
        assert self._db is not None
        cur = await self._db.execute("SELECT value FROM meta WHERE key=?", (key,))
        row = await cur.fetchone()
        return row[0] if row else None

    async def set_meta(self, key: str, value: str) -> None:
        assert self._db is not None
        await self._db.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, value)
        )
        await self._db.commit()

    # ── diff + persist ──────────────────────────────────
    async def diff_and_apply(
        self,
        fetched: dict[str, list[Model]],
        *,
        watch_price: set[str],
        watch_context: set[str],
    ) -> list[Event]:
        """Diff a cycle's fetch against stored state; persist in one transaction.

        Returns the list of events worth announcing. Models absent from the
        provider this cycle are marked ``missing_since`` (deprecation is only
        reported after ``DEPRECATION_CYCLES`` consecutive misses).
        """
        assert self._db is not None
        now = time.time()
        events: list[Event] = []

        cur = await self._db.execute("SELECT * FROM models")
        existing_rows = await cur.fetchall()
        existing: dict[str, aiosqlite.Row] = {f"{r['source']}:{r['pk']}": r for r in existing_rows}
        seen_keys: set[str] = set()

        for source, models in fetched.items():
            for m in models:
                key = m.key()
                seen_keys.add(key)
                row = existing.get(key)

                if row is None:
                    events.append(Event(kind=NEW, model=m))
                    await self._upsert(m, now, now, None)
                    await self._price_point(m, now)
                    continue

                was_free = bool(row["is_free"])
                if m.is_free and not was_free:
                    events.append(Event(kind=BECAME_FREE, model=m, old={"is_free": False}))
                elif not m.is_free and was_free:
                    events.append(Event(kind=BECAME_PAID, model=m, old={"is_free": True}))

                if source in watch_price:
                    old_in, old_out = row["price_in"], row["price_out"]
                    if _changed(old_in, m.price_in) or _changed(old_out, m.price_out):
                        events.append(
                            Event(
                                kind=PRICE_CHANGE,
                                model=m,
                                old={"price_in": old_in, "price_out": old_out},
                            )
                        )
                        await self._price_point(m, now)

                if source in watch_context and _changed(row["context"], m.context):
                    events.append(
                        Event(
                            kind=CONTEXT_CHANGE,
                            model=m,
                            old={"context": row["context"]},
                        )
                    )

                await self._upsert(m, now, row["first_seen"] or now, None)
                if _changed(row["price_in"], m.price_in) or _changed(row["price_out"], m.price_out):
                    await self._price_point(m, now)

        # deprecation detection (missing 3 consecutive cycles)
        for key, row in existing.items():
            if key in seen_keys:
                continue
            missing_since = row["missing_since"]
            if missing_since is None:
                await self._db.execute(
                    "UPDATE models SET missing_since=? WHERE source=? AND pk=?",
                    (now, row["source"], row["pk"]),
                )
            else:
                cycles_missing = int((now - missing_since) / 1800) + 1
                if cycles_missing >= 3:
                    model = _row_to_model(row)
                    events.append(Event(kind=DEPRECATED, model=model))

        await self._db.commit()
        return events

    async def _upsert(
        self, m: Model, now: float, first_seen: float, missing_since: float | None
    ) -> None:
        assert self._db is not None
        row = m.to_row()
        await self._db.execute(
            """
            INSERT INTO models
              (source, pk, name, author, url, is_free, free_note, context,
               modalities, price_in, price_out, description, extra,
               first_seen, last_seen, missing_since)
            VALUES
              (:source, :pk, :name, :author, :url, :is_free, :free_note, :context,
               :modalities, :price_in, :price_out, :description, :extra,
               :first_seen, :last_seen, :missing_since)
            ON CONFLICT(source, pk) DO UPDATE SET
              name=excluded.name, author=excluded.author, url=excluded.url,
              is_free=excluded.is_free, free_note=excluded.free_note,
              context=excluded.context, modalities=excluded.modalities,
              price_in=excluded.price_in, price_out=excluded.price_out,
              description=excluded.description, extra=excluded.extra,
              last_seen=excluded.last_seen, missing_since=excluded.missing_since
            """,
            {**row, "first_seen": first_seen, "last_seen": now, "missing_since": missing_since},
        )

    async def _price_point(self, m: Model, now: float) -> None:
        assert self._db is not None
        await self._db.execute(
            "INSERT INTO price_history (source, pk, ts, price_in, price_out, is_free) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (m.source, m.pk, now, m.price_in, m.price_out, int(m.is_free)),
        )

    async def record_event(self, event: Event) -> None:
        assert self._db is not None
        await self._db.execute(
            "INSERT INTO events (ts, source, pk, kind, detail) VALUES (?, ?, ?, ?, ?)",
            (time.time(), event.model.source, event.model.pk, event.kind, event.detail),
        )
        await self._db.commit()


def _changed(old: Any, new: Any) -> bool:
    """Compare two nullable numerics, treating sub-cent noise as unchanged."""
    if old is None and new is None:
        return False
    if old is None or new is None:
        return True
    try:
        return abs(float(old) - float(new)) > 1e-9
    except (TypeError, ValueError):
        return old != new
