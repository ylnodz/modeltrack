from __future__ import annotations

from .base import Provider


class SambaNovaProvider(Provider):
    key = "sambanova"
    label = "SambaNova Cloud"
    env_keys = ("SAMBANOVA_API_KEY",)
    filter_free = False

    async def fetch(self):
        return await self.fetch_openai_compatible(
            "https://api.sambanova.ai/v1",
            api_key=self._key("SAMBANOVA_API_KEY"),
        )

    def model_url(self, pk: str) -> str:
        return "https://cloud.sambanova.ai/"

    def is_free(self, raw, price_in, price_out) -> bool:
        return True

    def free_note(self, raw) -> str | None:
        return "free tier (rate-limited)"
