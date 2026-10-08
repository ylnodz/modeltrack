from __future__ import annotations

from ..http import get_json
from ..models import Model
from .base import Provider


class NvidiaNimProvider(Provider):
    key = "nim"
    label = "NVIDIA NIM"
    env_keys = ("NVIDIA_API_KEY",)
    filter_free = True
    watch_context = False

    async def fetch(self) -> list[Model]:
        key = self._key("NVIDIA_API_KEY")
        headers = {"Authorization": f"Bearer {key}"}
        models_data = await get_json("https://integrate.api.nvidia.com/v1/models", headers=headers)
        items = models_data.get("data", []) if isinstance(models_data, dict) else []
        if not items:
            return []

        free_map: dict[str, bool] = {}
        try:
            ep_data = await get_json("https://api.ngc.nvidia.com/v2/endpoints?page-size=1000")
            endpoints = ep_data.get("artifacts", []) if isinstance(ep_data, dict) else []
            for ep in endpoints:
                is_free = "Free Endpoint" in (ep.get("labels") or [])
                for field in ("name", "displayName"):
                    val = ep.get(field)
                    if val:
                        free_map[val] = is_free
        except Exception:  # noqa: BLE001 - endpoint metadata is best-effort
            free_map = {}

        out: list[Model] = []
        for raw in items:
            mid = str(raw.get("id") or "")
            if not mid:
                continue
            is_free = free_map.get(mid, False) or free_map.get(mid.split("/")[-1], False)
            out.append(
                Model(
                    source=self.key,
                    pk=mid,
                    name=mid,
                    author=str(raw.get("owned_by") or "NVIDIA"),
                    url=f"https://build.nvidia.com/{mid}",
                    is_free=is_free,
                    free_note="free endpoint available" if is_free else None,
                    extra={},
                )
            )
        return out
