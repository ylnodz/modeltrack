"""Discord embed rendering — modern, minimalist, information-dense.

Color language (one color per embed, no rainbow):
  free        green
  became_paid orange
  price       amber
  deprecated  grey
"""

from __future__ import annotations

from datetime import UTC, datetime

from discord import Embed

from .models import Model
from .state import BECAME_FREE, BECAME_PAID, CONTEXT_CHANGE, DEPRECATED, PRICE_CHANGE

FREE_COLOR = 0x2ECC71
PAID_COLOR = 0xE67E22
PRICE_COLOR = 0xF1C40F
GREY_COLOR = 0x95A5A6

MAX_EMBEDS_PER_MESSAGE = 10
DESC_LIMIT = 200

MODALITY_ICON = {
    "text": "text",
    "image": "img",
    "audio": "audio",
    "video": "video",
    "embedding": "embed",
}


def _ctx(context: int | None) -> str:
    if not context:
        return "ctx n/a"
    if context >= 1000:
        return f"{round(context / 1000)}K ctx"
    return f"{context} ctx"


def _mods(model: Model) -> str:
    return " · ".join(MODALITY_ICON.get(m, m) for m in model.modalities) or "text"


def _price_line(model: Model) -> str:
    if model.is_free:
        if model.free_note:
            return model.free_note
        return "free"
    if model.price_in is None and model.price_out is None:
        return model.free_note or "pricing n/a"
    pin = f"${model.price_in:.2f}" if model.price_in is not None else "?"
    pout = f"${model.price_out:.2f}" if model.price_out is not None else "?"
    return f"{pin}/M in · {pout}/M out"


def _subtitle(model: Model) -> str:
    label = _label_for(model.source)
    return f"{label} · {_ctx(model.context)} · {_mods(model)}"


_LABELS = {
    "openrouter": "OpenRouter",
    "nim": "NVIDIA NIM",
    "cloudflare": "Cloudflare",
    "ollama": "Ollama Cloud",
    "groq": "Groq",
    "gemini": "Google AI Studio",
    "mistral": "Mistral",
    "huggingface": "HuggingFace",
    "siliconflow": "SiliconFlow",
    "zai": "Z.AI",
    "cohere": "Cohere",
    "sambanova": "SambaNova",
    "chutes": "Chutes",
    "nebius": "Nebius",
}


def _label_for(source: str) -> str:
    return _LABELS.get(source, source)


def _truncate(text: str, limit: int = DESC_LIMIT) -> str:
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0]
    return f"{cut}…"


def base_embed(model: Model, *, color: int, prefix: str = "") -> Embed:
    title = f"{prefix}{model.name}"
    embed = Embed(
        title=title,
        url=model.url or None,
        color=color,
        timestamp=datetime.now(UTC),
    )
    embed.description = f"`{_price_line(model)}`"
    desc = _truncate(model.description)
    if desc:
        embed.add_field(name="\u200b", value=desc, inline=False)
    embed.set_footer(text=_subtitle(model))
    return embed


def render_event(kind: str, model: Model, old: dict | None = None) -> tuple[Embed, str | None]:
    """Return (embed, optional message content) for an event."""
    old = old or {}
    label = _label_for(model.source)
    if kind == BECAME_FREE:
        embed = base_embed(model, color=FREE_COLOR)
        return embed, f"{model.name} is now free on {label}"
    if kind == BECAME_PAID:
        embed = base_embed(model, color=PAID_COLOR)
        return embed, f"{model.name} is no longer free on {label}"
    if kind == PRICE_CHANGE:
        embed = base_embed(model, color=PRICE_COLOR)
        old_in = old.get("price_in")
        old_out = old.get("price_out")

        def fmt(v):
            return "?" if v is None else f"${v:.2f}"

        embed.add_field(
            name="Price change",
            value=(
                f"was {fmt(old_in)}/{fmt(old_out)} → {fmt(model.price_in)}/{fmt(model.price_out)}/M"
            ),
            inline=False,
        )
        return embed, None
    if kind == CONTEXT_CHANGE:
        embed = base_embed(model, color=PRICE_COLOR)
        embed.add_field(
            name="Context change",
            value=f"was {_ctx(old.get('context'))} → {_ctx(model.context)}",
            inline=False,
        )
        return embed, None
    if kind == DEPRECATED:
        embed = base_embed(model, color=GREY_COLOR)
        return embed, f"{model.name} no longer listed on {label}"
    # default / new
    color = FREE_COLOR if model.is_free else 0x9B59B6
    embed = base_embed(model, color=color, prefix="🟢 " if model.is_free else "")
    return embed, None


def render_digest(counts: dict[str, tuple[int, int]]) -> Embed:
    """One summary embed for ``/free``: per-provider counts + total."""
    lines = []
    total_free = 0
    for source in sorted(counts):
        total, free = counts[source]
        total_free += free
        if free:
            lines.append(f"`{_label_for(source):<16} {free:>4} free / {total} total`")
    embed = Embed(
        title="Free models",
        color=FREE_COLOR,
        timestamp=datetime.now(UTC),
    )
    embed.description = "\n".join(lines) or "No free models tracked yet."
    embed.set_footer(text=f"{total_free} free models · use /free provider:<name>")
    return embed


def chunk(embeds: list[Embed], size: int = MAX_EMBEDS_PER_MESSAGE) -> list[list[Embed]]:
    return [embeds[i : i + size] for i in range(0, len(embeds), size)]
