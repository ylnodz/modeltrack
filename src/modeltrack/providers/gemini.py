from __future__ import annotations

from ..http import get_json
from ..models import Model
from .base import Provider


class GeminiProvider(Provider):
    key = "gemini"
    label = "Google AI Studio"
    env_keys = ("GEMINI_API_KEY",)
    filter_free = False
    watch_context = True

    async def fetch(self) -> list[Model]:
        key = self._key("GEMINI_API_KEY")
        data = await get_json(
            "https://generativelanguage.googleapis.com/v1beta/models",
            params={"key": key or "", "pageSize": "1000"},
        )
        items = data.get("models", []) if isinstance(data, dict) else []
        out: list[Model] = []
        for raw in items:
            if not isinstance(raw, dict):
                continue
            full = str(raw.get("name") or "")
            if not full:
                continue
            mid = full.split("/", 1)[-1]
            methods = raw.get("supportedGenerationMethods") or []
            if methods and "generateContent" not in methods:
                continue
            out.append(
                Model(
                    source=self.key,
                    pk=mid,
                    name=str(raw.get("displayName") or mid),
                    author="Google",
                    url="https://ai.google.dev/gemini-api/docs/models",
                    is_free=True,
                    free_note="free tier (RPM/RPD varies by model)",
                    context=raw.get("inputTokenLimit"),
                    modalities=["text"],
                    description=str(raw.get("description") or ""),
                )
            )
        return out
