"""Normalized model representation shared across all providers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Model:
    source: str
    pk: str
    name: str
    author: str = ""
    url: str = ""
    is_free: bool = False
    free_note: str | None = None
    context: int | None = None
    modalities: list[str] = field(default_factory=lambda: ["text"])
    price_in: float | None = None
    price_out: float | None = None
    description: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def key(self) -> str:
        return f"{self.source}:{self.pk}"

    def to_row(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "pk": self.pk,
            "name": self.name,
            "author": self.author,
            "url": self.url,
            "is_free": int(self.is_free),
            "free_note": self.free_note,
            "context": self.context,
            "modalities": ",".join(self.modalities),
            "price_in": self.price_in,
            "price_out": self.price_out,
            "description": self.description,
            "extra": _json_dumps(self.extra),
        }


def _json_dumps(value: Any) -> str:
    import json

    try:
        return json.dumps(value, separators=(",", ":"))
    except (TypeError, ValueError):
        return "{}"


def parse_price(value: Any) -> float | None:
    """Parse a provider price into USD-per-1M-tokens, or None if unavailable.

    Handles OpenRouter's per-token strings (``"0.0000012"``), plain numbers,
    and the sentinel ``-1`` (unavailable).
    """
    if value is None:
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if num < 0:
        return None
    return num


def detect_modalities(raw: dict[str, Any]) -> list[str]:
    """Best-effort modality detection from a provider payload."""
    mods: list[str] = ["text"]
    arch = raw.get("architecture") or {}
    input_mods = arch.get("input_modalities") if isinstance(arch, dict) else None
    if isinstance(input_mods, list):
        for m in input_mods:
            if m and m not in mods:
                mods.append(str(m))
    for key, label in (("image", "image"), ("audio", "audio"), ("video", "video")):
        if raw.get(f"supports_{key}") or raw.get(f"{key}_input"):
            if label not in mods:
                mods.append(label)
    return mods
