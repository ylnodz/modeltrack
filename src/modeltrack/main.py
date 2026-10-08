"""ModelTrack entrypoint: wires config, state, tracker, bot, and health API."""

from __future__ import annotations

import asyncio
import logging

import uvicorn

from . import bot as bot_mod
from .api import build_app
from .config import load_config
from .http import close_client
from .state import Store
from .tracker import Tracker

logger = logging.getLogger(__name__)


async def _null_sender(event, content=None) -> None:  # noqa: ANN001
    return None


def main() -> None:
    config = load_config()
    logging.basicConfig(
        level=getattr(logging, config.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    if not config.discord_bot_token or config.discord_channel_id == 0:
        logger.error("DISCORD_BOT_TOKEN and DISCORD_CHANNEL_ID are required")
        raise SystemExit(1)

    store = Store(config.db_path)
    # Sender is replaced by the bot in setup_hook; until then events are dropped.
    tracker = Tracker(config, store, sender=_null_sender)

    async def _serve_api() -> None:
        app = build_app(config, store, tracker)
        server = uvicorn.Server(
            uvicorn.Config(app, host="0.0.0.0", port=config.port, log_level="info")
        )
        await server.serve()

    async def _run() -> None:
        await store.open()
        api_task = asyncio.create_task(_serve_api())
        try:
            await asyncio.to_thread(bot_mod.run, config, store, tracker)
        finally:
            api_task.cancel()
            await close_client()
            await store.close()

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        logger.info("shutting down")
