from __future__ import annotations

from .base import Provider


class NebiusProvider(Provider):
    key = "nebius"
    label = "Nebius Token Factory"
    env_keys = ("NEBIUS_API_KEY",)
    filter_free = False

    async def fetch(self):
        return await self.fetch_openai_compatible(
            "https://api.studio.nebius.com/v1",
            api_key=self._key("NEBIUS_API_KEY"),
        )

    def model_url(self, pk: str) -> str:
        return "https://studio.nebius.com/"

    def is_free(self, raw, price_in, price_out) -> bool:
        if price_in is not None and price_out is not None:
            return price_in == 0.0 and price_out == 0.0
        return True

    def free_note(self, raw) -> str | None:
        return "free tier (rate-limited)"
