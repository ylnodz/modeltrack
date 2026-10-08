from __future__ import annotations

from ..http import get_json
from ..models import Model
from .base import Provider


class OllamaCloudProvider(Provider):
    key = "ollama"
    label = "Ollama Cloud"
    env_keys = ("OLLAMA_CLOUD_API_KEY",)
    filter_free = False

    async def fetch(self) -> list[Model]:
        base = self.config.ollama_cloud_base_url.rstrip("/")
        key = self._key("OLLAMA_CLOUD_API_KEY")
        data = await get_json(f"{base}/api/tags", headers={"Authorization": f"Bearer {key}"})
        models = data.get("models", []) if isinstance(data, dict) else []

        out: list[Model] = []
        for raw in models:
            if not isinstance(raw, dict):
                continue
            mid = str(raw.get("name") or raw.get("model") or "")
            if not mid:
                continue
            details = raw.get("details") or {}
            out.append(
                Model(
                    source=self.key,
                    pk=mid,
                    name=mid,
                    author="Ollama",
                    url=f"{base}/library/{mid.split(':')[0]}",
                    is_free=True,
                    free_note="free within Ollama Cloud usage tier",
                    description=str(raw.get("description") or ""),
                    extra={"details": details} if details else {},
                )
            )
        return out
