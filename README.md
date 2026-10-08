# 🔮 ModelTrack

[![CI](https://github.com/ylnodz/modeltrack/actions/workflows/ci.yml/badge.svg)](https://github.com/ylnodz/modeltrack/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/badge/uv-managed-261230.svg)](https://github.com/astral-sh/uv)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Discord bot that watches **cloud LLM API providers** and announces when a model
appears, changes, or becomes **free**.

Tracked providers (permanent free tiers only — trial-credit providers are excluded):

| key | provider |
| :--- | :--- |
| `openrouter` | OpenRouter |
| `nim` | NVIDIA NIM |
| `cloudflare` | Cloudflare Workers AI |
| `ollama` | Ollama Cloud |
| `groq` | Groq |
| `gemini` | Google AI Studio |
| `mistral` | Mistral La Plateforme |
| `huggingface` | HuggingFace Inference |
| `siliconflow` | SiliconFlow |
| `zai` | Z.AI |
| `cohere` | Cohere |
| `sambanova` | SambaNova Cloud |
| `chutes` | Chutes.ai |
| `nebius` | Nebius Token Factory |

Every provider key is optional. Unconfigured providers show as `unconfigured`
in `/health` and are skipped during tracking.

---

## ✨ What's new in v2

- **No more re-spam.** State lives in SQLite with permanent history; a model is
  announced only on a real transition (new, became free, became paid, price change,
  context change, deprecated). The old 24h auto-expiry that re-announced everything
  daily is gone.
- **Tracking can't die silently.** Per-provider timeouts, retries with backoff, and a
  loop error handler keep cycles running even when a provider fails.
- **One transaction per cycle** instead of a full-file JSON rewrite per model.
- **Real free detection** per provider instead of hardcoded `is_free: True`.
- **Modern, dense embeds**: provider · context · modalities on the byline, price or
  free-tier policy always visible.

---

## ⚡ Quick start

```bash
git clone https://github.com/ylnodz/modeltrack.git && cd modeltrack
bash setup.sh          # installs uv, creates .env, syncs deps
# edit .env with your Discord bot token + channel id
uv run modeltrack
```

Or with Docker:

```bash
cp .env.example .env   # fill in Discord credentials
docker compose up -d --build
```

---

## ⚙️ Configuration

All settings live in `.env` (see [`.env.example`](.env.example)):

| Variable | Required | Description |
| :--- | :---: | :--- |
| `DISCORD_BOT_TOKEN` | ✅ | Bot token from the [Developer Portal](https://discord.com/developers/applications) |
| `DISCORD_CHANNEL_ID` | ✅ | Channel where updates are posted |
| `DISCORD_GUILD_ID` | | Guild id for instant slash-command sync |
| `DB_PATH` | | SQLite path (default `/home/container/modeltrack.db`) |
| `TRACK_INTERVAL_MINUTES` | | Cycle interval (default `30`) |
| `PROVIDER_TIMEOUT_SECONDS` | | Per-provider timeout (default `25`) |
| `ANNOUNCE_MENTION` | | Prefix became-free notices with `@here` |
| `PORT` | | Health endpoint port (default `8000`) |
| provider keys | | `OPENROUTER_API_KEY`, `GROQ_API_KEY`, `GEMINI_API_KEY`, … all optional |

> 💡 OpenRouter's `/models` endpoint is public — its key is optional and only raises
> rate limits. Every other provider is skipped until its key is present.

---

## 🛠️ Commands

| Command | Description |
| :--- | :--- |
| `/free` | One summary embed: free-model counts per provider |
| `/free provider:<name>` | Free models for a single provider (paginated if long) |
| `/status` | Last cycle stats and per-provider status |

---

## 📡 Health endpoint

`GET /health` returns tracker state:

```json
{
  "status": "healthy",
  "last_run": 1791482661.26,
  "providers": {"openrouter": "ok (467)", "groq": "unconfigured"},
  "models_total": 467,
  "models_free": 19,
  "interval_minutes": 30
}
```

---

## 🧪 Development

```bash
uv sync --extra dev
uv run pytest                      # unit tests (network mocked)
uv run python scripts/smoke.py     # live end-to-end check (needs network)
uv run ruff check . && uv run ruff format --check .
```

---

## 📦 Project structure

```text
src/modeltrack/
├── config.py        # env parsing
├── models.py        # normalized Model schema
├── state.py         # SQLite store + diff logic
├── http.py          # shared client, retry/backoff
├── render.py        # embed builders
├── tracker.py       # fetch → diff → notify
├── bot.py           # slash commands, send queue, loop
├── api.py           # /health
└── providers/        # one module per provider (auto-discovered)
```

---

## 📄 License

MIT.
