from __future__ import annotations

from typing import Any

from ..models import Model, detect_modalities, parse_price
from .base import Provider


class OpenRouterProvider(Provider):
    key = "openrouter"
    label = "OpenRouter"
    # Public /models endpoint — key optional (raises rate limits when present).
    env_keys = ()
    filter_free = True
    watch_price = True
    watch_context = True

    def configured(self) -> bool:
        return True

    async def fetch(self) -> list[Model]:
        data = await self._get()
        items = data.get("data", []) if isinstance(data, dict) else []
        out: list[Model] = []
        for raw in items:
            if not isinstance(raw, dict):
                continue
            mid = str(raw.get("id") or "")
            if not mid:
                continue
            pricing = raw.get("pricing") or {}
            # OpenRouter prices are USD per token → scale to per 1M tokens.
            pin = parse_price(pricing.get("prompt")) if isinstance(pricing, dict) else None
            pout = parse_price(pricing.get("completion")) if isinstance(pricing, dict) else None
            if pin is not None:
                pin *= 1_000_000
            if pout is not None:
                pout *= 1_000_000
            is_free = mid.endswith(":free") or (pin == 0.0 and pout == 0.0)
            out.append(
                Model(
                    source=self.key,
                    pk=mid,
                    name=str(raw.get("name") or mid),
                    author=str((raw.get("top_provider") or {}).get("name") or "OpenRouter"),
                    url=f"https://openrouter.ai/models/{mid}",
                    is_free=is_free,
                    free_note="free tier on OpenRouter" if is_free else None,
                    context=raw.get("context_length"),
                    modalities=detect_modalities(raw),
                    price_in=pin,
                    price_out=pout,
                    description=str(raw.get("description") or ""),
                    extra={"architecture": raw.get("architecture", {})}
                    if raw.get("architecture")
                    else {},
                )
            )
        return out

    async def _get(self) -> Any:
        from ..http import get_json

        headers = {}
        key = self._key("OPENROUTER_API_KEY")
        if key:
            headers["Authorization"] = f"Bearer {key}"
        return await get_json("https://openrouter.ai/api/v1/models", headers=headers)

    def is_free_rule(self) -> str:
        return ":free suffix or $0 pricing"
