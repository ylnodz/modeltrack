"""Provider base class and shared helpers."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

import httpx

from ..http import get_json
from ..models import Model, detect_modalities, parse_price

logger = logging.getLogger(__name__)


class Provider(ABC):
    """One cloud LLM API provider.

    Subclasses declare metadata and implement :meth:`fetch`. ``is_free`` is
    provider-specific and must never blanket-assert True without a documented
    free-tier policy.
    """

    key: str = ""
    label: str = ""
    env_keys: tuple[str, ...] = ()
    filter_free: bool = False
    watch_price: bool = False
    watch_context: bool = False

    def __init__(self, config) -> None:  # noqa: ANN001 - Config type by duck-typing
        self.config = config

    def configured(self) -> bool:
        return all(self.config.get(k) for k in self.env_keys)

    def _key(self, env: str) -> str | None:
        return self.config.get(env)

    @abstractmethod
    async def fetch(self) -> list[Model]:
        """Return the provider's current model catalog."""

    # ── shared helper for OpenAI-compatible /v1/models endpoints ──
    async def fetch_openai_compatible(
        self,
        base_url: str,
        *,
        api_key: str | None = None,
        auth_header: str = "Authorization",
        auth_prefix: str = "Bearer ",
        extra_headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        price_scale: float = 1.0,
    ) -> list[Model]:
        """Fetch a standard OpenAI ``{"data": [...]}`` model list."""
        headers: dict[str, str] = dict(extra_headers or {})
        if api_key:
            headers[auth_header] = f"{auth_prefix}{api_key}"
        data = await get_json(f"{base_url.rstrip('/')}/models", headers=headers, params=params)
        if isinstance(data, dict):
            items = data.get("data") or data.get("models") or []
        elif isinstance(data, list):
            items = data
        else:
            items = []

        out: list[Model] = []
        for raw in items:
            if not isinstance(raw, dict):
                continue
            mid = str(raw.get("id") or raw.get("name") or "")
            if not mid:
                continue
            pricing = raw.get("pricing") or {}
            price_in = parse_price(pricing.get("prompt")) if isinstance(pricing, dict) else None
            price_out = (
                parse_price(pricing.get("completion")) if isinstance(pricing, dict) else None
            )
            if price_scale != 1.0:
                price_in = price_in * price_scale if price_in is not None else None
                price_out = price_out * price_scale if price_out is not None else None
            out.append(
                Model(
                    source=self.key,
                    pk=mid,
                    name=str(raw.get("name") or raw.get("display_name") or mid),
                    author=str(raw.get("owned_by") or raw.get("provider") or self.label),
                    url=self.model_url(mid),
                    is_free=self.is_free(raw, price_in, price_out),
                    free_note=self.free_note(raw),
                    context=_as_int(raw.get("context_length") or raw.get("context_window")),
                    modalities=detect_modalities(raw),
                    price_in=price_in,
                    price_out=price_out,
                    description=str(raw.get("description") or ""),
                    extra=_extra(raw),
                )
            )
        return out

    def model_url(self, pk: str) -> str:
        """Provider model page URL. Override where a direct page exists."""
        return ""

    def is_free(self, raw: dict[str, Any], price_in: float | None, price_out: float | None) -> bool:
        """Default rule: free when both prices are known and zero."""
        if price_in is None or price_out is None:
            return False
        return price_in == 0.0 and price_out == 0.0

    def free_note(self, raw: dict[str, Any]) -> str | None:
        return None


def _as_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extra(raw: dict[str, Any]) -> dict[str, Any]:
    keep = {}
    for k in ("details", "architecture", "object", "created", "max_tokens", "deprecation"):
        if k in raw and raw[k] not in (None, ""):
            keep[k] = raw[k]
    return keep


def client_headers(api_key: str | None) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"} if api_key else {}


def raise_for_status(resp: httpx.Response) -> None:
    resp.raise_for_status()
