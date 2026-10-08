from __future__ import annotations

from ..http import get_json
from ..models import Model
from .base import Provider


class CloudflareProvider(Provider):
    key = "cloudflare"
    label = "Cloudflare Workers AI"
    env_keys = ("CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID")
    filter_free = False
    watch_price = False

    async def fetch(self) -> list[Model]:
        token = self._key("CLOUDFLARE_API_TOKEN")
        account = self._key("CLOUDFLARE_ACCOUNT_ID")
        url = f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/models/search"
        data = await get_json(url, headers={"Authorization": f"Bearer {token}"})
        models = _extract(data)

        out: list[Model] = []
        for raw in models:
            if not isinstance(raw, dict):
                continue
            mid = str(raw.get("id") or raw.get("name") or "")
            if not mid:
                continue
            out.append(
                Model(
                    source=self.key,
                    pk=mid,
                    name=str(raw.get("name") or mid),
                    author="Cloudflare",
                    url=f"https://developers.cloudflare.com/workers-ai/models/{mid}/",
                    # Free within the daily neuron allocation, not unconditionally $0.
                    is_free=True,
                    free_note="free within 10k neurons/day",
                    context=_as_int(raw.get("required_input_size")),
                    description=str(raw.get("description") or ""),
                )
            )
        return out


def _extract(data) -> list:
    if isinstance(data, dict):
        for key in ("result", "models"):
            val = data.get(key)
            if isinstance(val, list):
                return val
    if isinstance(data, list):
        return data
    return []


def _as_int(v) -> int | None:
    try:
        return int(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None
