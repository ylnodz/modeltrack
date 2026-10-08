"""Environment configuration for ModelTrack.

Every provider key is optional. Only Discord credentials are required for the
bot to run; a provider with a missing key is reported as ``unconfigured`` and
skipped during tracking cycles.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Config:
    # ── Discord (required) ──────────────────────────────
    discord_bot_token: str | None = None
    discord_channel_id: int = 0
    discord_guild_id: int = 0

    # ── Runtime ─────────────────────────────────────────
    port: int = 8000
    db_path: str = "/home/container/modeltrack.db"
    track_interval_minutes: int = 30
    provider_timeout_seconds: float = 25.0
    log_level: str = "INFO"
    announce_mention: bool = False

    # ── Provider keys ───────────────────────────────────
    openrouter_api_key: str | None = None
    nvidia_api_key: str | None = None
    cloudflare_api_token: str | None = None
    cloudflare_account_id: str | None = None
    ollama_cloud_base_url: str = "https://ollama.com"
    ollama_cloud_api_key: str | None = None
    groq_api_key: str | None = None
    gemini_api_key: str | None = None
    mistral_api_key: str | None = None
    huggingface_api_key: str | None = None
    siliconflow_api_key: str | None = None
    zai_api_key: str | None = None
    cohere_api_key: str | None = None
    sambanova_api_key: str | None = None
    chutes_api_key: str | None = None
    nebius_api_key: str | None = None

    extra: dict[str, str] = field(default_factory=dict)

    def get(self, name: str, default: str | None = None) -> str | None:
        """Look up an env var by its UPPER_SNAKE name (provider convenience)."""
        attr = name.lower()
        value = getattr(self, attr, None)
        if value in (None, ""):
            return os.environ.get(name, default)
        return value if isinstance(value, str) else str(value)


def load_config() -> Config:
    cfg = Config(
        discord_bot_token=os.environ.get("DISCORD_BOT_TOKEN"),
        discord_channel_id=_int("DISCORD_CHANNEL_ID", 0),
        discord_guild_id=_int("DISCORD_GUILD_ID", 0),
        port=_int("PORT", 8000),
        db_path=os.environ.get("DB_PATH", "/home/container/modeltrack.db"),
        track_interval_minutes=_int("TRACK_INTERVAL_MINUTES", 30),
        provider_timeout_seconds=_float("PROVIDER_TIMEOUT_SECONDS", 25.0),
        log_level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        announce_mention=_bool("ANNOUNCE_MENTION", False),
        openrouter_api_key=os.environ.get("OPENROUTER_API_KEY"),
        nvidia_api_key=os.environ.get("NVIDIA_API_KEY"),
        cloudflare_api_token=os.environ.get("CLOUDFLARE_API_TOKEN"),
        cloudflare_account_id=os.environ.get("CLOUDFLARE_ACCOUNT_ID"),
        ollama_cloud_base_url=os.environ.get("OLLAMA_CLOUD_BASE_URL", "https://ollama.com"),
        ollama_cloud_api_key=os.environ.get("OLLAMA_CLOUD_API_KEY"),
        groq_api_key=os.environ.get("GROQ_API_KEY"),
        gemini_api_key=os.environ.get("GEMINI_API_KEY"),
        mistral_api_key=os.environ.get("MISTRAL_API_KEY"),
        huggingface_api_key=os.environ.get("HUGGINGFACE_API_KEY"),
        siliconflow_api_key=os.environ.get("SILICONFLOW_API_KEY"),
        zai_api_key=os.environ.get("ZAI_API_KEY"),
        cohere_api_key=os.environ.get("COHERE_API_KEY"),
        sambanova_api_key=os.environ.get("SAMBANOVA_API_KEY"),
        chutes_api_key=os.environ.get("CHUTES_API_KEY"),
        nebius_api_key=os.environ.get("NEBIUS_API_KEY"),
    )
    return cfg
