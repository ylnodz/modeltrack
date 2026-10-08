from __future__ import annotations

from ..http import get_json
from ..models import Model
from .base import Provider


class MistralProvider(Provider):
    key = "mistral"
    label = "Mistral La Plateforme"
    env_keys = ("MISTRAL_API_KEY",)
    filter_free = False
    watch_context = True

    async def fetch(self) -> list[Model]:
        key = self._key("MISTRAL_API_KEY")
        data = await get_json(
            "https://api.mistral.ai/v1/models", headers={"Authorization": f"Bearer {key}"}
        )
        items = data.get("data", []) if isinstance(data, dict) else []
        out: list[Model] = []
        for raw in items:
            if not isinstance(raw, dict):
                continue
            mid = str(raw.get("id") or "")
            if not mid:
                continue
            out.append(
                Model(
                    source=self.key,
                    pk=mid,
                    name=mid,
                    author="Mistral AI",
                    url="https://docs.mistral.ai/getting-started/models/",
                    is_free=True,
                    free_note="free Experiment tier (data used for training)",
                    context=raw.get("max_context_length"),
                    description=str(raw.get("description") or ""),
                )
            )
        return out
