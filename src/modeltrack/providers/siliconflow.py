from __future__ import annotations

from .base import Provider


class SiliconFlowProvider(Provider):
    key = "siliconflow"
    label = "SiliconFlow"
    env_keys = ("SILICONFLOW_API_KEY",)
    filter_free = False

    async def fetch(self):
        return await self.fetch_openai_compatible(
            "https://api.siliconflow.cn/v1",
            api_key=self._key("SILICONFLOW_API_KEY"),
        )

    def model_url(self, pk: str) -> str:
        return "https://cloud.siliconflow.cn/models"

    def is_free(self, raw, price_in, price_out) -> bool:
        return True

    def free_note(self, raw) -> str | None:
        return "free tier (subset of models, rate-limited)"
