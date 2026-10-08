from __future__ import annotations

from .base import Provider


class ZaiProvider(Provider):
    key = "zai"
    label = "Z.AI"
    env_keys = ("ZAI_API_KEY",)
    filter_free = False

    async def fetch(self):
        return await self.fetch_openai_compatible(
            "https://api.z.ai/api/paas/v4",
            api_key=self._key("ZAI_API_KEY"),
        )

    def model_url(self, pk: str) -> str:
        return "https://docs.z.ai/guides/overview/pricing"

    def is_free(self, raw, price_in, price_out) -> bool:
        return True

    def free_note(self, raw) -> str | None:
        return "free tier (GLM Flash series)"
