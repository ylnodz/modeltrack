"""Discord bot: slash commands, send queue, and the tracking loop."""

from __future__ import annotations

import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import tasks

from .providers import all_providers
from .render import chunk, render_digest, render_event
from .state import Event, Store
from .tracker import Tracker

logger = logging.getLogger(__name__)

PAGE_SIZE = 10


class SendQueue:
    """Single-consumer sender that respects Discord rate limits."""

    def __init__(self, client: discord.Client) -> None:
        self.client = client
        self._q: asyncio.Queue = asyncio.Queue()
        self._task: asyncio.Task | None = None
        self.channel_id = 0

    def bind(self, channel_id: int) -> None:
        self.channel_id = channel_id

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            self._task = None

    async def put(self, embed: discord.Embed, content: str | None = None) -> None:
        await self._q.put((embed, content))

    async def _run(self) -> None:
        while True:
            embed, content = await self._q.get()
            try:
                await self._deliver(embed, content)
            except Exception as exc:  # noqa: BLE001
                logger.warning("send failed err=%s", exc)
            finally:
                self._q.task_done()

    async def _deliver(self, embed: discord.Embed, content: str | None) -> None:
        channel = self.client.get_channel(self.channel_id)
        if channel is None:
            logger.warning("channel %s not found", self.channel_id)
            return
        for attempt in range(3):
            try:
                await channel.send(content=content, embed=embed)
                return
            except discord.HTTPException as exc:
                if exc.status == 429 and attempt < 2:
                    await asyncio.sleep(getattr(exc, "retry_after", 2.0) or 2.0)
                    continue
                raise


class ModelTrackBot(discord.Client):
    def __init__(self, config, store: Store, tracker: Tracker) -> None:  # noqa: ANN001
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.config = config
        self.store = store
        self.tracker = tracker
        self.tree = app_commands.CommandTree(self)
        self.queue = SendQueue(self)
        self._register_commands()

    # ── events ──────────────────────────────────────────
    async def setup_hook(self) -> None:
        self.queue.bind(self.config.discord_channel_id)
        self.queue.start()
        if self.config.discord_guild_id:
            guild = discord.Object(id=self.config.discord_guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
        else:
            synced = await self.tree.sync()
        logger.info("synced %d slash command(s)", len(synced))
        self.tracker.sender = self.send_event
        track_loop.change_interval(minutes=self.config.track_interval_minutes)
        track_loop.start()

    async def on_ready(self) -> None:
        logger.info("logged in as %s", self.user)

    async def close(self) -> None:
        await self.queue.stop()
        await super().close()

    async def send_event(self, event: Event, content: str | None = None) -> None:
        embed, default_content = render_event(event.kind, event.model, event.old)
        await self.queue.put(embed, content or default_content)

    # ── commands ────────────────────────────────────────
    def _register_commands(self) -> None:
        choices = [app_commands.Choice(name=p.label, value=p.key) for p in all_providers()]

        @self.tree.command(name="free", description="List free models")
        @app_commands.describe(provider="Limit to a single provider")
        @app_commands.choices(provider=choices)
        async def free_cmd(
            interaction: discord.Interaction,
            provider: app_commands.Choice[str] | None = None,
        ) -> None:
            await interaction.response.defer(thinking=True)
            key = provider.value if provider else None
            models = await self.store.free_models(key)
            if not models:
                await interaction.followup.send("No free models tracked yet.")
                return
            if provider is None:
                counts = await self.store.counts()
                await interaction.followup.send(embed=render_digest(counts))
                return
            embeds = [render_event("new", m)[0] for m in models]
            pages = chunk(embeds, PAGE_SIZE)
            view = PagerView(pages) if len(pages) > 1 else None
            await interaction.followup.send(
                content=f"🆓 {len(models)} free on {provider.name}",
                embeds=pages[0],
                view=view,
            )

        @self.tree.command(name="status", description="Show tracker status")
        async def status_cmd(interaction: discord.Interaction) -> None:
            await interaction.response.defer(thinking=True)
            summary = self.tracker.last_summary or {}
            counts = await self.store.counts()
            lines = [f"`{k}: {v}`" for k, v in sorted(self.tracker.provider_status.items())]
            embed = discord.Embed(title="ModelTrack status", color=0x3498DB)
            embed.add_field(
                name="Last cycle",
                value=(
                    f"models {summary.get('models', 0)} · events {summary.get('events', 0)} "
                    f"· {summary.get('elapsed_ms', 0)}ms"
                ),
                inline=False,
            )
            embed.add_field(name="Providers", value="\n".join(lines) or "none", inline=False)
            embed.set_footer(
                text=f"{sum(f for _, f in counts.values())} free / "
                f"{sum(t for t, _ in counts.values())} total"
            )
            await interaction.followup.send(embed=embed)


class PagerView(discord.ui.View):
    def __init__(self, pages: list[list[discord.Embed]]) -> None:
        super().__init__(timeout=120)
        self.pages = pages
        self.index = 0

    async def _update(self, interaction: discord.Interaction) -> None:
        self.index = max(0, min(self.index, len(self.pages) - 1))
        await interaction.response.edit_message(embeds=self.pages[self.index], view=self)

    @discord.ui.button(label="Prev", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction: discord.Interaction, _button) -> None:  # noqa: ANN001
        self.index -= 1
        await self._update(interaction)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, _button) -> None:  # noqa: ANN001
        self.index += 1
        await self._update(interaction)


@tasks.loop(minutes=30)
async def track_loop() -> None:
    bot = track_loop.bot  # set in start helper
    await bot.tracker.run_cycle()


@track_loop.error
async def track_loop_error(exc: Exception) -> None:
    logger.error("track loop error (loop continues): %s", exc)


def run(config, store: Store, tracker: Tracker) -> None:
    bot = ModelTrackBot(config, store, tracker)
    track_loop.bot = bot  # type: ignore[attr-defined]
    bot.run(config.discord_bot_token, log_handler=None)
