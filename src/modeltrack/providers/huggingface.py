from __future__ import annotations

from .base import Provider


class HuggingFaceProvider(Provider):
    key = "huggingface"
    label = "HuggingFace Inference"
    env_keys = ("HUGGINGFACE_API_KEY",)
    filter_free = False

    async def fetch(self):
        return await self.fetch_openai_compatible(
            "https://router.huggingface.co/v1",
            api_key=self._key("HUGGINGFACE_API_KEY"),
        )

    def model_url(self, pk: str) -> str:
        return f"https://huggingface.co/{pk}"

    def is_free(self, raw, price_in, price_out) -> bool:
        return True

    def free_note(self, raw) -> str | None:
        return "free within Inference Providers routing limits"
