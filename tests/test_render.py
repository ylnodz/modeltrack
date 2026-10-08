"""Embed rendering tests."""

from __future__ import annotations

from modeltrack.models import Model
from modeltrack.render import base_embed, chunk, render_digest, render_event
from modeltrack.state import BECAME_FREE, BECAME_PAID, PRICE_CHANGE


def sample(*, free=True, pin=0.0, pout=0.0, ctx=131072) -> Model:
    return Model(
        source="openrouter",
        pk="meta/llama:free",
        name="Llama 3.3 70B",
        author="Meta",
        url="https://openrouter.ai/models/meta/llama:free",
        is_free=free,
        price_in=pin,
        price_out=pout,
        context=ctx,
        modalities=["text"],
        description="A very long " + "word " * 100,
    )


def test_free_embed_shows_context_and_price():
    embed = base_embed(sample(free=True), color=0x2ECC71, prefix="🆓 ")
    assert "131K ctx" in embed.footer.text
    assert "free" in embed.description


def test_paid_embed_shows_price_per_million():
    embed = base_embed(sample(free=False, pin=5.0, pout=15.0), color=0x9B59B6)
    assert "$5.00/M in" in embed.description
    assert "$15.00/M out" in embed.description


def test_description_truncated():
    embed = base_embed(sample(), color=0x2ECC71)
    assert embed.fields
    assert len(embed.fields[0].value) <= 200
    assert embed.fields[0].value.endswith("…")


def test_became_free_has_content():
    embed, content = render_event(BECAME_FREE, sample(free=True))
    assert content and "now free" in content
    assert embed.color.value == 0x2ECC71


def test_became_paid_warns():
    embed, content = render_event(BECAME_PAID, sample(free=False))
    assert content and "no longer free" in content
    assert embed.color.value == 0xE67E22


def test_price_change_field():
    embed, _ = render_event(
        PRICE_CHANGE, sample(free=False, pin=3.0), {"price_in": 1.0, "price_out": 2.0}
    )
    assert any("Price change" in f.name for f in embed.fields)


def test_digest_counts_and_total():
    embed = render_digest({"openrouter": (10, 4), "groq": (5, 3)})
    assert "7 free models" in embed.footer.text
    assert "openrouter" not in embed.description  # label used, not raw key
    assert "OpenRouter" in embed.description


def test_chunk_size():
    from discord import Embed

    parts = chunk([Embed(title=str(i)) for i in range(25)], size=10)
    assert [len(p) for p in parts] == [10, 10, 5]
