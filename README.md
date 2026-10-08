# 🔮 ModelTrack

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**ModelTrack** is a high-performance Discord bot that monitors AI model providers for updates and tracks which models are currently available for **FREE**.

It currently supports tracking across:
- 🔮 **OpenRouter**
- ⚡ **NVIDIA NIM**
- ☁️ **Cloudflare Workers AI**
- 🦙 **Ollama Cloud**

---

## ⚡ Quick Start (One Command)

```bash
git clone https://github.com/ylnodz/modeltrack.git && cd modeltrack && bash setup.sh
```

This will:
1. Install [uv](https://github.com/astral-sh/uv) if you don't have it
2. Create a template `.env` file for your API keys
3. Install all dependencies automatically

Then just edit `.env` with your tokens and run:

```bash
uv run modeltrack
```

---

## 📋 Manual Installation

<details>
<summary>Prefer to set up manually? Click here.</summary>

### Prerequisites

- [Python 3.11+](https://www.python.org/downloads/)
- [uv](https://github.com/astral-sh/uv)

### Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/ylnodz/modeltrack.git
   cd modeltrack
   ```

2. **Install dependencies**
   ```bash
   uv sync
   ```

3. **Create `.env`** with your tokens (see [Configuration](#-configuration) below)

4. **Run the bot**
   ```bash
   uv run modeltrack
   ```

</details>

---

## ⚙️ Configuration

Create a `.env` file in the project root:

| Variable | Required | Description |
| :--- | :---: | :--- |
| `DISCORD_BOT_TOKEN` | ✅ | Your Discord bot token from [Discord Developer Portal](https://discord.com/developers/applications) |
| `DISCORD_CHANNEL_ID` | ✅ | The channel ID where the bot posts updates |
| `DISCORD_GUILD_ID` | | Server ID for instant slash command sync (optional, slower global sync without it) |
| `NVIDIA_API_KEY` | | Your NVIDIA API key for NIM model tracking |
| `CLOUDFLARE_API_TOKEN` | | Cloudflare API token for Workers AI tracking |
| `CLOUDFLARE_ACCOUNT_ID` | | Your Cloudflare account ID |
| `OLLAMA_CLOUD_API_KEY` | | Ollama Cloud API key |

> 💡 At least **Discord** credentials are required. All provider keys are optional — the bot will skip providers without keys.

---

## 🛠️ Commands

| Command | Description |
| :--- | :--- |
| `/free` | Lists all models currently available for $0.00 across all providers |

---

## 📦 Project Structure

```text
modeltrack/
├── src/
│   └── modeltrack/
│       ├── __init__.py
│       └── main.py          # Bot logic & API fetching
├── pyproject.toml           # Package configuration & dependencies
├── uv.lock                  # Pinned dependency versions
├── setup.sh                 # One-click setup script
└── README.md
```

---

## 🤝 Contributing

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

Distributed under the MIT License.

---

<p align="center">
  Built with ❤️ using <a href="https://github.com/astral-sh/uv">uv</a>
</p>
