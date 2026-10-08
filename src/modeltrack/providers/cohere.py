from __future__ import annotations

from ..http import get_json
from ..models import Model
from .base import Provider


class CohereProvider(Provider):
    key = "cohere"
    label = "Cohere"
    env_keys = ("COHERE_API_KEY",)
    filter_free = False
    watch_context = True

    async def fetch(self) -> list[Model]:
        key = self._key("COHERE_API_KEY")
        data = await get_json(
            "https://api.cohere.com/v1/models",
            headers={"Authorization": f"Bearer {key}"},
        )
        items = data.get("models", []) if isinstance(data, dict) else []
        out: list[Model] = []
        for raw in items:
            if not isinstance(raw, dict):
                continue
            mid = str(raw.get("name") or "")
            if not mid:
                continue
            endpoints = raw.get("endpoints") or []
            if endpoints and "chat" not in endpoints:
                continue
            out.append(
                Model(
                    source=self.key,
                    pk=mid,
                    name=mid,
                    author="Cohere",
                    url="https://docs.cohere.com/docs/models",
                    is_free=True,
                    free_note="free trial tier (non-commercial)",
                    context=raw.get("context_length"),
                )
            )
        return out
