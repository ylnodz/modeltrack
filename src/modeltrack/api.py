"""FastAPI app exposing a rich /health endpoint (no public model API)."""

from __future__ import annotations

import time

from fastapi import FastAPI

from .providers import unconfigured_keys


def build_app(config, store, tracker) -> FastAPI:  # noqa: ANN001
    app = FastAPI(title="ModelTrack", version="2.0.0")

    @app.get("/health")
    async def health() -> dict:
        counts = await store.counts()
        total_free = sum(free for _, free in counts.values())
        return {
            "status": "healthy",
            "last_run": tracker.last_run,
            "seconds_since_run": (
                round(time.time() - tracker.last_run) if tracker.last_run else None
            ),
            "last_summary": tracker.last_summary,
            "providers": tracker.provider_status,
            "unconfigured": unconfigured_keys(config),
            "models_total": sum(total for total, _ in counts.values()),
            "models_free": total_free,
            "interval_minutes": config.track_interval_minutes,
        }

    return app
