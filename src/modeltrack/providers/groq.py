from __future__ import annotations

from .base import Provider


class GroqProvider(Provider):
    key = "groq"
    label = "Groq"
    env_keys = ("GROQ_API_KEY",)
    filter_free = False

    async def fetch(self):
        return await self.fetch_openai_compatible(
            "https://api.groq.com/openai/v1",
            api_key=self._key("GROQ_API_KEY"),
        )

    def model_url(self, pk: str) -> str:
        return "https://console.groq.com/docs/models"

    def is_free(self, raw, price_in, price_out) -> bool:
        return True

    def free_note(self, raw) -> str | None:
        return "free tier (rate-limited)"
