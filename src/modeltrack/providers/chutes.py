from __future__ import annotations

from ..http import get_json
from ..models import Model
from .base import Provider


class ChutesProvider(Provider):
    key = "chutes"
    label = "Chutes.ai"
    env_keys = ("CHUTES_API_KEY",)
    filter_free = True
    watch_price = True

    async def fetch(self) -> list[Model]:
        key = self._key("CHUTES_API_KEY")
        data = await get_json(
            "https://llm.chutes.ai/v1/models", headers={"Authorization": f"Bearer {key}"}
        )
        items = data.get("data", []) if isinstance(data, dict) else []
        out: list[Model] = []
        for raw in items:
            if not isinstance(raw, dict):
                continue
            mid = str(raw.get("id") or "")
            if not mid:
                continue
            pricing = raw.get("pricing") or {}
            pin = _price(pricing.get("prompt")) if isinstance(pricing, dict) else None
            pout = _price(pricing.get("completion")) if isinstance(pricing, dict) else None
            out.append(
                Model(
                    source=self.key,
                    pk=mid,
                    name=mid,
                    author=str(raw.get("owned_by") or "Chutes"),
                    url="https://chutes.ai/app",
                    is_free=(pin == 0.0 and pout == 0.0)
                    if pin is not None and pout is not None
                    else True,
                    free_note="free tier (rate-limited)",
                    context=raw.get("context_length"),
                    price_in=pin,
                    price_out=pout,
                    description=str(raw.get("description") or ""),
                )
            )
        return out


def _price(value) -> float | None:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if num < 0:
        return None
    return num * 1_000_000  # per-token → per-1M
