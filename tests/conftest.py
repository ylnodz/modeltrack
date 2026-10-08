"""Shared test fixtures."""

from __future__ import annotations

import pytest

from modeltrack.config import Config


@pytest.fixture
def config() -> Config:
    return Config(
        discord_bot_token="test-token",
        discord_channel_id=123,
        openrouter_api_key="or-key",
        groq_api_key="groq-key",
        gemini_api_key="gem-key",
        db_path=":memory:",
    )
