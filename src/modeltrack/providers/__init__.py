"""Provider registry (auto-discovery).

Each module in this package that defines a ``Provider`` subclass is picked up
at import time. A provider whose ``env_keys`` are unset is reported as
``unconfigured`` and skipped during cycles.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from typing import TYPE_CHECKING

from .base import Provider

if TYPE_CHECKING:
    from ..config import Config

logger = logging.getLogger(__name__)

PROVIDER_CLASSES: list[type[Provider]] = []


def _discover() -> None:
    if PROVIDER_CLASSES:
        return
    package = __name__
    for modinfo in pkgutil.iter_modules(__path__):
        name = modinfo.name
        if name in {"base"} or name.startswith("_"):
            continue
        module = importlib.import_module(f"{package}.{name}")
        for attr in vars(module).values():
            if (
                isinstance(attr, type)
                and issubclass(attr, Provider)
                and attr is not Provider
                and attr.key
                and attr.__module__ == module.__name__
            ):
                PROVIDER_CLASSES.append(attr)
    PROVIDER_CLASSES.sort(key=lambda p: p.key)


def all_providers() -> list[type[Provider]]:
    _discover()
    return list(PROVIDER_CLASSES)


def build_providers(config: Config) -> list[Provider]:
    return [cls(config) for cls in all_providers()]


def configured_providers(config: Config) -> list[Provider]:
    return [p for p in build_providers(config) if p.configured()]


def unconfigured_keys(config: Config) -> list[str]:
    return [p.key for p in build_providers(config) if not p.configured()]


def provider_choices() -> list[str]:
    return [p.key for p in all_providers()]
