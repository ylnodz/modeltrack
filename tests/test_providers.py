"""Provider fetch + free-rule tests (network mocked with respx)."""

from __future__ import annotations

import httpx
import pytest
import respx

from modeltrack.providers import all_providers
from modeltrack.providers.groq import GroqProvider
from modeltrack.providers.openrouter import OpenRouterProvider

OPENROUTER_PAYLOAD = {
    "data": [
        {
            "id": "meta/llama-3.3-70b:free",
            "name": "Llama 3.3 70B (free)",
            "pricing": {"prompt": "0", "completion": "0"},
            "context_length": 131072,
            "description": "A free Llama.",
            "architecture": {"input_modalities": ["text"]},
        },
        {
            "id": "openai/gpt-4o",
            "name": "GPT-4o",
            "pricing": {"prompt": "0.000005", "completion": "0.000015"},
            "context_length": 128000,
            "description": "Paid.",
        },
        {
            "id": "vendor/unavailable",
            "name": "Unavailable",
            "pricing": {"prompt": "-1", "completion": "-1"},
        },
    ]
}


@respx.mock
async def test_openrouter_free_rule(config):
    respx.get("https://openrouter.ai/api/v1/models").mock(
        return_value=httpx.Response(200, json=OPENROUTER_PAYLOAD)
    )
    models = await OpenRouterProvider(config).fetch()
    by_id = {m.pk: m for m in models}

    assert by_id["meta/llama-3.3-70b:free"].is_free is True
    assert by_id["meta/llama-3.3-70b:free"].context == 131072
    # paid model: prices scaled per 1M tokens
    assert by_id["openai/gpt-4o"].is_free is False
    assert by_id["openai/gpt-4o"].price_in == pytest.approx(5.0)
    assert by_id["openai/gpt-4o"].price_out == pytest.approx(15.0)
    # -1 sentinel = unavailable, not a bogus $0
    assert by_id["vendor/unavailable"].is_free is False
    assert by_id["vendor/unavailable"].price_in is None


@respx.mock
async def test_groq_free_note(config):
    respx.get("https://api.groq.com/openai/v1/models").mock(
        return_value=httpx.Response(
            200, json={"data": [{"id": "llama-3.3-70b-versatile", "owned_by": "Meta"}]}
        )
    )
    models = await GroqProvider(config).fetch()
    assert len(models) == 1
    assert models[0].is_free is True
    assert models[0].free_note


def test_registry_discovers_all(config):
    keys = {p.key for p in all_providers()}
    expected = {
        "openrouter",
        "nim",
        "cloudflare",
        "ollama",
        "groq",
        "gemini",
        "mistral",
        "huggingface",
        "siliconflow",
        "zai",
        "cohere",
        "sambanova",
        "chutes",
        "nebius",
    }
    assert expected <= keys


def test_no_trial_providers(config):
    keys = {p.key for p in all_providers()}
    assert not keys & {"cerebras", "together", "deepinfra", "fireworks", "novita", "vercel"}


async def test_unconfigured_provider_skipped(config):
    from modeltrack.providers import configured_providers

    provider = OpenRouterProvider(config)
    assert provider.configured() is True
    from modeltrack.providers.sambanova import SambaNovaProvider

    assert SambaNovaProvider(config).configured() is False
    assert "openrouter" in {p.key for p in configured_providers(config)}
    assert "sambanova" not in {p.key for p in configured_providers(config)}
