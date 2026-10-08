from __future__ import annotations

import os
import json
import asyncio
import time
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from discord.ext import tasks, commands
from discord import Embed, Intents
from fastapi import FastAPI
import uvicorn
import discord

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Config ──────────────────────────────────────────────
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = int(os.environ.get("DISCORD_CHANNEL_ID", "0"))
DISCORD_GUILD_ID = int(os.environ.get("DISCORD_GUILD_ID", "0"))
PORT = int(os.environ.get("PORT", 8000))

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY")
CLOUDFLARE_API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN")
CLOUDFLARE_ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
OLLAMA_CLOUD_BASE_URL = os.environ.get("OLLAMA_CLOUD_BASE_URL", "https://cloud.ollama.com")
OLLAMA_CLOUD_API_KEY = os.environ.get("OLLAMA_CLOUD_API_KEY")

# ── FastAPI ─────────────────────────────────────────────
app = FastAPI()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}


# ── State persistence ───────────────────────────────────
STATE_FILE = Path("state.json")


def _load_state() -> dict[str, dict[str, Any]]:
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text())
            logger.info(f"Loaded {len(data)} entries from state.json")
            return data
        except (json.JSONDecodeError, OSError):
            logger.warning("Corrupt state.json — starting fresh")
    return {}


def _save_state() -> None:
    try:
        STATE_FILE.write_text(json.dumps(posted_models))
    except OSError as e:
        logger.error(f"Failed to save state: {e}")


posted_models: dict[str, dict[str, Any]] = _load_state()


def cleanup_old_entries() -> None:
    cutoff = time.time() - 86400
    old_keys = [k for k, v in posted_models.items() if v["timestamp"] < cutoff]
    for k in old_keys:
        del posted_models[k]
    if old_keys:
        _save_state()


def get_status(source: str, model_id: str) -> dict[str, Any] | None:
    cleanup_old_entries()
    return posted_models.get(f"{source}:{model_id}")


def mark_as_posted(source: str, model_id: str, is_free: bool) -> None:
    posted_models[f"{source}:{model_id}"] = {
        "timestamp": time.time(),
        "is_free": bool(is_free),
    }
    _save_state()


# ── Shared async HTTP client ────────────────────────────
http_client: httpx.AsyncClient | None = None


async def get_client() -> httpx.AsyncClient:
    global http_client
    if http_client is None or http_client.is_closed:
        http_client = httpx.AsyncClient(timeout=20.0)
    return http_client


async def close_client() -> None:
    global http_client
    if http_client and not http_client.is_closed:
        await http_client.aclose()


# ── Embed helpers ───────────────────────────────────────
FREE_COLOR = 0x00C853
NIM_COLOR = 0x76B900
CF_COLOR = 0xF38020
OLLAMA_COLOR = 0x000000
MODERN_COLORS = {
    "free": FREE_COLOR,
    "orange": 0xF97316,
    "purple": 0x9B59B6,
    "teal": 0x1ABC9C,
    "dark": 0x2C3E50,
    "gray": 0x6B7280,
}


def _embed_base(title: str, url: str | None = None, *, color: int = FREE_COLOR) -> Embed:
    embed = Embed(title=title, url=url, color=color, timestamp=datetime.now(timezone.utc))
    embed.set_footer(text="✨ Model Tracker")
    return embed


def _truncate(text: str, limit: int = 300) -> str:
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


# ── Fetch: OpenRouter ───────────────────────────────────
async def fetch_openrouter() -> list[dict[str, Any]]:
    try:
        client = await get_client()
        headers = {}
        if OPENROUTER_API_KEY:
            headers["Authorization"] = f"Bearer {OPENROUTER_API_KEY}"
        resp = await client.get(
            "https://openrouter.ai/api/v1/models",
            headers=headers,
        )
        resp.raise_for_status()
        models = resp.json().get("data", [])
        results = []
        for m in models:
            pricing = m.get("pricing") or {}
            prompt_price = pricing.get("prompt")
            completion_price = pricing.get("completion")
            prompt_str = str(prompt_price) if prompt_price is not None else ""
            completion_str = str(completion_price) if completion_price is not None else ""
            
            mid = m.get("id", "")
            is_free = (
                ":free" in mid
                or (prompt_str in ("0", "0.0") and completion_str in ("0", "0.0"))
            )
            results.append({
                "id": mid,
                "name": m.get("name") or mid or "Unknown",
                "author": m.get("provider", "OpenRouter"),
                "url": f"https://openrouter.ai/models/{mid}",
                "likes": prompt_price,
                "is_free": is_free,
                "description": m.get("description", ""),
                "context_length": m.get("context_length"),
            })
        return results
    except Exception as e:
        logger.error(f"Error fetching OpenRouter models: {e}")
        return []


# ── Fetch: NVIDIA NIM ──────────────────────────────────
async def fetch_nvidia_nim() -> list[dict[str, Any]]:
    if not NVIDIA_API_KEY:
        return []
    try:
        client = await get_client()
        headers = {"Authorization": f"Bearer {NVIDIA_API_KEY}"}

        models_resp = await client.get(
            "https://integrate.api.nvidia.com/v1/models", headers=headers
        )
        models_resp.raise_for_status()
        models_data = models_resp.json().get("data", [])
        if not models_data:
            return []

        endpoints_resp = await client.get(
            "https://api.ngc.nvidia.com/v2/endpoints?page-size=1000"
        )
        endpoints_resp.raise_for_status()
        endpoints = endpoints_resp.json().get("artifacts", [])

        free_map: dict[str, bool] = {}
        for ep in endpoints:
            name = ep.get("name")
            display = ep.get("displayName")
            is_free = "Free Endpoint" in ep.get("labels", [])
            if name:
                free_map[name] = is_free
            if display:
                free_map[display] = is_free

        results = []
        for m in models_data:
            mid = m.get("id", "")
            is_free = free_map.get(mid, False) or free_map.get(mid.split("/")[-1], False)
            results.append({
                "id": mid,
                "name": mid,
                "author": m.get("owned_by", "NVIDIA"),
                "url": f"https://build.nvidia.com/models/{mid}",
                "likes": None,
                "is_free": is_free,
                "description": "",
            })
        return results
    except Exception as e:
        logger.error(f"Error fetching NVIDIA NIM models: {e}")
        return []


# ── Fetch: Cloudflare Workers AI ────────────────────────
async def fetch_cloudflare_workers_ai() -> list[dict[str, Any]]:
    if not CLOUDFLARE_API_TOKEN or not CLOUDFLARE_ACCOUNT_ID:
        return []
    try:
        client = await get_client()
        url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/models/search"
        resp = await client.get(
            url, headers={"Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}"}
        )
        resp.raise_for_status()
        data = resp.json()
        models = data.get("result", [])
        if not models:
            models = data.get("models", [])
        if not models and isinstance(data, list):
            models = data

        results = []
        for m in models:
            mid = m.get("id", "")
            results.append({
                "id": mid,
                "name": m.get("name", mid),
                "author": "Cloudflare",
                "url": f"https://developers.cloudflare.com/workers-ai/models/{mid}",
                "likes": None,
                "is_free": True,
                "description": m.get("description", ""),
                "context_length": m.get("required_input_size"),
            })
        return results
    except Exception as e:
        logger.error(f"Error fetching Cloudflare Workers AI models: {e}")
        return []


# ── Fetch: Ollama Cloud ────────────────────────────────
async def fetch_ollama_cloud() -> list[dict[str, Any]]:
    if not OLLAMA_CLOUD_API_KEY:
        return []
    try:
        client = await get_client()
        headers = {"Authorization": f"Bearer {OLLAMA_CLOUD_API_KEY}"}
        resp = await client.get(f"{OLLAMA_CLOUD_BASE_URL}/api/tags", headers=headers)
        resp.raise_for_status()
        models = resp.json().get("models", [])

        results = []
        for m in models:
            mid = m.get("name", "")
            results.append({
                "id": mid,
                "name": mid,
                "author": "Ollama",
                "url": f"{OLLAMA_CLOUD_BASE_URL}/models/{mid}",
                "likes": None,
                "is_free": True,
                "description": m.get("description", ""),
                "details": m.get("details", {}),
            })
        return results
    except Exception as e:
        logger.error(f"Error fetching Ollama Cloud models: {e}")
        return []


# ── Fetch: Groq ─────────────────────────────────────────
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")


async def fetch_groq() -> list[dict[str, Any]]:
    if not GROQ_API_KEY:
        return []
    try:
        client = await get_client()
        resp = await client.get(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        )
        resp.raise_for_status()
        models = resp.json().get("data", [])

        results = []
        for m in models:
            mid = m.get("id", "")
            results.append({
                "id": mid,
                "name": mid,
                "author": m.get("owned_by", "Groq"),
                "url": "https://console.groq.com/docs/models",
                "likes": None,
                "is_free": True,  # Groq models are free (rate-limited)
                "description": m.get("description", ""),
            })
        return results
    except Exception as e:
        logger.error(f"Error fetching Groq models: {e}")
        return []


# ── Embed builders ──────────────────────────────────────
def create_or_embed(model: dict[str, Any], *, highlight_free: bool = False) -> Embed:
    free = bool(model.get("is_free"))
    color = MODERN_COLORS["free"] if highlight_free or free else MODERN_COLORS["purple"]
    prefix = "🆓 FREE • " if highlight_free else ("🆓 " if free else "")
    title = f"{prefix}🔮 {model['name']}"
    embed = _embed_base(title, url=model["url"], color=color)
    embed.set_author(name=model.get("author", "OpenRouter"))
    prompt_price = model.get("likes")
    if free:
        desc = "🎉 **FREE** — prompt & completion cost $0/M tokens"
    elif prompt_price:
        desc = f"Prompt: ${prompt_price}/M tokens"
    else:
        desc = "Pricing: N/A"
    if model.get("context_length"):
        desc += f"\nContext: {model['context_length']:,} tokens"
    text = _truncate(model.get("description", ""), 240)
    if text:
        desc += f"\n{text}"
    embed.description = desc
    embed.add_field(name="Open", value=f"[View on OpenRouter]({model['url']})", inline=False)
    return embed


def create_nim_embed(model: dict[str, Any], *, highlight_free: bool = False) -> Embed:
    free = bool(model.get("is_free"))
    color = MODERN_COLORS["free"] if highlight_free or free else NIM_COLOR
    prefix = "🆓 FREE • " if highlight_free else ("🆓 " if free else "")
    title = f"{prefix}⚡ {model['name']}"
    embed = _embed_base(title, url=model["url"], color=color)
    embed.set_author(name=model.get("author", "NVIDIA"))
    desc = f"Model: {model['id']}"
    if free:
        desc += "\n🎉 **FREE** (Free Endpoint available)"
    embed.description = desc
    embed.add_field(name="Open", value=f"[View on NVIDIA Build]({model['url']})", inline=False)
    return embed


def create_cf_embed(model: dict[str, Any], *, highlight_free: bool = False) -> Embed:
    title = f"☁️ {model['name']}"
    embed = _embed_base(title, url=model["url"], color=CF_COLOR)
    embed.set_author(name="Cloudflare Workers AI")
    desc = "🎉 **FREE** (within Workers AI limits)"
    if model.get("description"):
        desc += f"\n{_truncate(model['description'], 200)}"
    if model.get("context_length"):
        desc += f"\nContext: {model['context_length']:,} tokens"
    embed.description = desc
    embed.add_field(name="Open", value=f"[View Documentation]({model['url']})", inline=False)
    return embed


def create_ollama_embed(model: dict[str, Any], *, highlight_free: bool = False) -> Embed:
    title = f"🦙 {model['name']}"
    embed = _embed_base(title, url=model["url"], color=OLLAMA_COLOR)
    embed.set_author(name="Ollama Cloud")
    desc = "🎉 **FREE** (assumed)"
    if model.get("description"):
        desc += f"\n{_truncate(model['description'], 200)}"
    details = model.get("details", {})
    if isinstance(details, dict):
        if "parameter_size" in details:
            desc += f"\nSize: {details['parameter_size']}"
        if "family" in details:
            desc += f"\nFamily: {details['family']}"
    embed.description = desc
    embed.add_field(name="Open", value=f"[View Model]({model['url']})", inline=False)
    return embed


def create_groq_embed(model: dict[str, Any], *, highlight_free: bool = False) -> Embed:
    title = f"⚡ {model['name']}"
    embed = _embed_base(title, url=model["url"], color=0xF55036)
    embed.set_author(name="Groq")
    desc = "🎉 **FREE** (rate-limited)"
    if model.get("description"):
        desc += f"\n{_truncate(model['description'], 200)}"
    embed.description = desc
    embed.add_field(name="Open", value=f"[View on Groq]({model['url']})", inline=False)
    return embed


# ── Unified fetch all providers ─────────────────────────
async def fetch_all() -> dict[str, list[dict[str, Any]]]:
    or_models, nim_models, cf_models, ollama_models, groq_models = await asyncio.gather(
        fetch_openrouter(),
        fetch_nvidia_nim(),
        fetch_cloudflare_workers_ai(),
        fetch_ollama_cloud(),
        fetch_groq(),
    )
    return {
        "or": or_models,
        "nim": nim_models,
        "cf": cf_models,
        "ollama": ollama_models,
        "groq": groq_models,
    }


# ── Provider config (source key → embed func + highlight) ─
PROVIDERS = {
    "or":     {"embed_func": create_or_embed,     "highlight": True,  "filter_free": True},
    "nim":    {"embed_func": create_nim_embed,     "highlight": True,  "filter_free": True},
    "cf":     {"embed_func": create_cf_embed,      "highlight": False, "filter_free": False},
    "ollama": {"embed_func": create_ollama_embed,  "highlight": False, "filter_free": False},
    "groq":   {"embed_func": create_groq_embed,    "highlight": False, "filter_free": False},
}


# ── Discord Bot ─────────────────────────────────────────
intents = Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready() -> None:
    logger.info(f"Bot logged in as {bot.user}")
    try:
        if DISCORD_GUILD_ID:
            guild = discord.Object(id=DISCORD_GUILD_ID)
            synced = await bot.tree.sync(guild=guild)
        else:
            synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} slash command(s)")
    except Exception as e:
        logger.error(f"Failed to sync slash commands: {e}")
    track_models.start()


@bot.tree.command(name="free", description="Show currently free models")
async def free_command(interaction: discord.Interaction) -> None:
    await interaction.response.defer(thinking=True)
    all_models = await fetch_all()

    embeds: list[Embed] = []
    for source, cfg in PROVIDERS.items():
        models = all_models.get(source, [])
        for m in models:
            if cfg["filter_free"] and not m.get("is_free"):
                continue
            embeds.append(cfg["embed_func"](m, highlight_free=cfg["highlight"]))

    if not embeds:
        await interaction.followup.send("No free models found right now.")
        return

    chunks = [embeds[i: i + 10] for i in range(0, len(embeds), 10)]
    for idx, chunk in enumerate(chunks):
        if idx == 0:
            await interaction.followup.send(
                content=f"🆓 **Currently Free Models** — {len(embeds)} found",
                embeds=chunk,
            )
        else:
            await interaction.followup.send(embeds=chunk)


# ── Background task ─────────────────────────────────────
@tasks.loop(minutes=30)
async def track_models() -> None:
    if not DISCORD_BOT_TOKEN or DISCORD_CHANNEL_ID == 0:
        logger.warning("Missing DISCORD_BOT_TOKEN or DISCORD_CHANNEL_ID")
        return

    channel = bot.get_channel(DISCORD_CHANNEL_ID)
    if channel is None:
        logger.warning(f"Channel {DISCORD_CHANNEL_ID} not found")
        return

    all_models = await fetch_all()

    for source, cfg in PROVIDERS.items():
        models = all_models.get(source, [])
        for m in models:
            mid = m["id"]
            current_free = bool(m.get("is_free"))
            stored = get_status(source, mid)

            if stored is None:
                if cfg["filter_free"] and not current_free:
                    mark_as_posted(source, mid, current_free)
                    continue
                embed = cfg["embed_func"](m, highlight_free=cfg["highlight"] and current_free)
                await channel.send(embed=embed)
                mark_as_posted(source, mid, current_free)
                continue

            was_free = bool(stored.get("is_free"))
            if current_free and not was_free:
                embed = cfg["embed_func"](m, highlight_free=True)
                await channel.send(
                    content=f"🆓 **{m.get('name', mid)} is now FREE!**",
                    embed=embed,
                )
            mark_as_posted(source, mid, current_free)


@track_models.before_loop
async def before_track_models() -> None:
    await bot.wait_until_ready()


# ── Entry point ─────────────────────────────────────────
async def _run_fastapi() -> None:
    config = uvicorn.Config(app, host="0.0.0.0", port=PORT, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


def main() -> None:
    async def _run() -> None:
        fastapi_task = asyncio.create_task(_run_fastapi())
        try:
            await bot.start(DISCORD_BOT_TOKEN)
        finally:
            fastapi_task.cancel()
            await close_client()

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        logger.info("Shutting down")


if __name__ == "__main__":
    main()
