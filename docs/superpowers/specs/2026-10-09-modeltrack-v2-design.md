# ModelTrack v2 — Design Spec

Date: 2026-10-09
Status: approved (design sections A–H reviewed in chat; 4 open questions resolved)
Author: Hermes (for Irgy / ylnodz)

## 1. Purpose

ModelTrack is a Discord bot that monitors **cloud LLM API providers** and posts when a
model appears, changes, or becomes free. The v1 codebase is a single 563-line
`main.py` with several correctness bugs (24h state amnesia causing re-spam, unhandled
loop exceptions killing tracking silently, per-model full-file JSON rewrites, hardcoded
`is_free=True`). v2 is a full restructure targeting **speed** and **reliability**, with a
modern minimalist Discord embed format that surfaces the fields that matter (context,
modalities, price, free-tier limits).

Scope decisions (locked in chat):
- **Cloud API providers only.** No local inference (no Ollama-local, no LM Studio).
- **Permanent free tiers only.** Trial-credit providers (Cerebras, Together, DeepInfra,
  Fireworks, Novita, Vercel AI Gateway) are **dropped**.
- **Discord is the only output surface.** No public HTTP JSON API. FastAPI is kept for
  `/health` only.
- Per-provider command targeting: `/free openrouter` lists only that provider's free
  models; applies to every provider.

## 2. Success Criteria

- No model is announced twice unless its tracked state genuinely changed.
- A provider failure (timeout, 429, 500, malformed JSON) never kills tracking.
- One cycle finishes in bounded time regardless of provider latency.
- `/free <provider>` returns in <2s from cache; `/free` (all) never blocks past Discord's
  3s interaction window.
- Restart on a wiped filesystem degrades gracefully (one notice, not N embeds).
- Discord rate limits are respected; the bot is not disconnected for flooding.

## 3. Architecture

```
modeltrack/
├── src/modeltrack/
│   ├── __init__.py            # exports main
│   ├── main.py                # entrypoint: wires config, db, bot, api
│   ├── config.py              # env parsing + validation (dataclass)
│   ├── models.py              # Model dataclass (normalized schema)
│   ├── state.py               # SQLite store: models, price_history, events, meta
│   ├── http.py                # shared AsyncClient, retry/backoff/timeout
│   ├── render.py              # embed builders + text formatting
│   ├── tracker.py             # orchestrator: fetch → diff → notify
│   ├── bot.py                 # discord client, slash commands, send queue
│   ├── api.py                 # FastAPI app (/health rich)
│   └── providers/
│       ├── __init__.py        # REGISTRY (auto-discovery)
│       ├── base.py            # Provider ABC
│       ├── openrouter.py  nim.py  cloudflare.py  ollama.py  groq.py
│       ├── gemini.py  mistral.py  huggingface.py  siliconflow.py  zai.py
│       ├── cohere.py  sambanova.py  chutes.py  nebius.py
├── tests/
│   ├── test_providers.py      # respx-mocked fetch + free-rule
│   ├── test_state.py          # diff logic, migrations
│   └── test_render.py         # embed shape assertions
├── docs/superpowers/specs/    # this file
├── .env.example
├── Dockerfile                 # Wispbyte / any Docker host
├── docker-compose.yml         # volume-backed DB
├── pyproject.toml
└── README.md
```

`main.py` is thin glue only. Every provider in its own module. Files stay small enough to
hold in context at once.

## 4. Data Model

Normalized `Model` (one shape across all providers):

| field | type | notes |
|---|---|---|
| `source` | str | provider key, e.g. `openrouter` |
| `pk` | str | stable per-provider model id |
| `name` | str | display name |
| `author` | str | org / owner |
| `url` | str | provider model page |
| `is_free` | bool | provider-specific rule (§6) |
| `free_note` | str \| None | e.g. "free tier: 30 RPM / 1K RPD" |
| `context` | int \| None | context window in tokens |
| `modalities` | list[str] | `text`, `image`, `audio`, `video`, `embedding` |
| `price_in` | float \| None | USD per 1M prompt tokens |
| `price_out` | float \| None | USD per 1M completion tokens |
| `description` | str | truncated at render time |
| `extra` | dict | provider-specific (params size, family, etc.) |

SQLite schema (WAL):

```sql
CREATE TABLE models (
  source TEXT, pk TEXT, name TEXT, author TEXT, url TEXT,
  is_free INTEGER, free_note TEXT, context INTEGER,
  modalities TEXT, price_in REAL, price_out REAL,
  description TEXT, extra TEXT,
  first_seen REAL, last_seen REAL, missing_since REAL,
  PRIMARY KEY (source, pk)
);
CREATE TABLE price_history (
  source TEXT, pk TEXT, ts REAL, price_in REAL, price_out REAL, is_free INTEGER
);
CREATE TABLE events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL,
  source TEXT, pk TEXT, kind TEXT, detail TEXT
);
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
```

`events.kind` ∈ {`new`, `became_free`, `became_paid`, `price_change`, `context_change`,
`deprecated`, `resumed`}.

**No time-based deletion.** `seen` is permanent. Re-announcement happens only on real
state transition. `missing_since` supports optional deprecation detection (model absent
from provider for N consecutive cycles → `deprecated` event, no removal).

## 5. Tracking Cycle

Interval: 30 minutes (configurable via `TRACK_INTERVAL_MINUTES`).

1. `asyncio.TaskGroup` gathers all providers; each wrapped in `asyncio.wait_for`
   (`PROVIDER_TIMEOUT_SECONDS`, default 25) so one slow provider cannot stall the cycle.
2. Provider returns `list[Model]` or raises; a raising provider is logged and skipped this
   cycle, never aborting the others.
3. Diff each model against `models` table:
   - not present → `new` (post only if provider's `filter_free` or model is free)
   - `is_free` False→True → `became_free` (post, highlight)
   - `is_free` True→False → `became_paid` (post, warning)
   - price changed → `price_change` (post if provider opted into price alerts)
   - context changed → `context_change` (post if opted in)
4. Persist all changes in **one transaction per cycle** (not per model).
5. Enqueue embeds to the send queue; the queue flushes respecting Discord rate limits.

## 6. Provider Contract

```python
class Provider(ABC):
    key: str  # "openrouter"
    label: str  # "OpenRouter"
    env_keys: tuple[str, ...]  # ("OPENROUTER_API_KEY",)
    filter_free: bool  # only announce free models
    watch_price: bool  # emit price_change events
    watch_context: bool  # emit context_change events

    async def fetch(self, client: httpx.AsyncClient) -> list[Model]: ...
    def is_free(self, raw: dict) -> bool: ...  # provider-specific rule
```

Registry auto-discovers modules under `providers/`; a provider with missing env keys is
reported as `unconfigured` in `/health` and skipped in cycles.

**Free rules (explicit, no blanket `True`):**
- OpenRouter — `:free` suffix OR both prices parse to 0 (numeric compare, handles `0.00`,
  exponent forms; `-1` = unavailable, not free).
- NVIDIA NIM — NGC endpoint carries `Free Endpoint` label.
- Cloudflare Workers AI — free within Workers AI daily neuron allocation (`free_note`
  states the limit; not a blanket True).
- Ollama Cloud — free within cloud tier; `free_note` states assumption.
- Groq — free tier (rate-limited); `free_note` states RPM/RPD.
- Gemini (AI Studio) — free tier per model; `free_note` states RPM/RPD.
- Mistral — free "Experiment" tier; `free_note` states data-training caveat.
- HuggingFace Inference — free within provider routing limits.
- SiliconFlow / Z.AI / Cohere / SambaNova / Chutes / Nebius — per provider docs; each
  declares its own rule and note.

Providers with **no pricing endpoint** set `price_in/out = None` and a `free_note`
describing the free-tier policy rather than asserting a false $0.

## 7. Reliability

- **Retries:** httpx transport retries on connect/read errors; manual exponential backoff
  with jitter on 429/5xx (respect `Retry-After`).
- **Loop guard:** `@track_models.error` handler logs and the loop keeps running; loop runs
  `reconnect=True`. Tracking can never die silently while the bot stays online.
- **Send queue:** single consumer, token-bucket limiter, honors Discord 429
  `retry_after`, caps embeds per message at 10.
- **Interaction safety:** `/free` reads from SQLite; `/free` (all providers) defers and
  answers from cache, never live-fetching inside the 3s window.
- **Startup recovery:** DB file missing → create schema, set `meta.resumed`, post a single
  "resumed tracking — no model history" notice instead of re-announcing every model.
- **Structured logging:** key=value lines, per-cycle summary (providers ok/failed,
  models seen, events emitted, elapsed ms).

## 8. Discord Output (modern minimalist)

Design goals: dense but scannable, minimal emoji, consistent color language, always show
context and modality, price or free-tier policy always present.

Embed template:

```
**Llama 3.3 70B**              ← title; free models prefixed with a single 🟢, paid with 🔴
Groq · 128K ctx · text         ← author line: provider · context · modalities
─────────────────────────────
$0.00/M in · $0.00/M out       ← OR  "free tier: 30 RPM · 1K RPD"
one-line description…
```

- Color language: free = green, price change = amber, became-paid = orange, deprecated =
  grey. One color per embed, no rainbow.
- Fields shown inline, no redundant "Open" field repeated as a link when the title is
  already the link.
- `became_free` → green embed + message content `now free` (mention toggle via
  `ANNOUNCE_MENTION`).
- `became_paid` → orange embed + `no longer free` content.
- Long descriptions truncated to 200 chars at a word boundary.

### `/free` command

- `/free` → summary embed: per-provider counts + total. **Fewer messages.**
- `/free provider:<name>` → that provider's free models only, paginated with buttons
  (prev/next) if they exceed 10 embeds; otherwise a single message.
- Provider choices via autocomplete from the registry.
- Discord slash command exposes `provider` as an optional choice, e.g.
  `/free openrouter`.

## 9. Ops

- `Dockerfile` (python:3.12-slim, uv-installed deps, non-root).
- `docker-compose.yml` with named/bind volume for the SQLite DB.
- `DB_PATH` env-configurable, default `/home/container/modeltrack.db` (Wispbyte persists
  `/home/container`; the path is overridable for other hosts).
- `.env.example` lists every provider key, all optional except Discord.
- `pyproject.toml`: drop unused `huggingface-hub` (use REST), add `aiosqlite`; keep
  `discord.py`, `fastapi`, `uvicorn`, `httpx`, `python-dotenv`.
- `setup.sh` / `startup.sh` retained, updated to not re-clone destructively.
- Tests: `pytest` + `respx` for provider fetch/free-rule, state diff, render shape. CI:
  ruff + pytest.

## 10. Implementation Order

1. Skeleton, `config.py`, `models.py`
2. `state.py` (SQLite store, schema, diff helpers)
3. `http.py` (client, retry/backoff/timeout)
4. `providers/base.py` + registry; refactor existing 5 providers
5. `tracker.py` (cycle, diff, events, single-transaction persist)
6. `render.py` (embeds, format)
7. `bot.py` (commands, send queue, loop guard)
8. New providers (permanent free set)
9. `api.py` `/health`
10. Tests + CI
11. Dockerfile / compose / README / .env.example

## 11. Out of Scope

- Local inference providers.
- Trial-credit providers.
- Public HTTP JSON API / RSS / webhooks.
- Cross-provider model identity dedupe (deferred; revisit after v2 ships).
