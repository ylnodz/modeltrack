#!/usr/bin/env bash
set -e

# ── Colors ──────────────────────────────────────────────
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# ── Header ──────────────────────────────────────────────
echo -e "${BLUE}"
echo "  ██╗  ██╗ ██████╗ ██╗  ██╗ ██████╗██████╗  █████╗ "
echo "  ██║  ██║██╔═══██╗██║ ██╔╝██╔════╝██╔══██╗██╔══██╗"
echo "  ███████║██║   ██║█████╔╝ ██║     ██████╔╝███████║"
echo "  ██╔══██║██║   ██║██╔═██╗ ██║     ██╔══██╗██╔══██║"
echo "  ██║  ██║╚██████╔╝██║  ██╗╚██████╗██║  ██║██║  ██║"
echo "  ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝"
echo -e "${NC}"
echo -e "${BLUE}  Model Tracker — Setup Script${NC}"
echo ""

# ── 1. Check Python ─────────────────────────────────────
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✖ python3 not found. Please install Python 3.11+ first.${NC}"
    echo "  https://www.python.org/downloads/"
    exit 1
fi

PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo -e "${GREEN}✓${NC} Python ${PY_VERSION} detected"

# ── 2. Install uv ───────────────────────────────────────
if ! command -v uv &> /dev/null; then
    echo -e "${YELLOW}⬇ uv not found. Installing Astral uv...${NC}"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    if ! command -v uv &> /dev/null; then
        echo -e "${RED}✖ uv installation failed. Please install manually: https://docs.astral.sh/uv/getting-started/installation/${NC}"
        exit 1
    fi
fi
echo -e "${GREEN}✓${NC} uv installed"

# ── 3. Create .env if missing ────────────────────────────
if [ ! -f .env ]; then
    echo -e "${YELLOW}⬇ Creating template .env file...${NC}"
    cat << 'EOF' > .env
# ╔══════════════════════════════════════╗
# ║  ModelTrack Configuration            ║
# ╚══════════════════════════════════════╝

# ── Discord (Required) ──────────────────
DISCORD_BOT_TOKEN=your_token_here
DISCORD_CHANNEL_ID=1234567890
DISCORD_GUILD_ID=1234567890
PORT=8000

# ── NVIDIA NIM (Optional) ───────────────
NVIDIA_API_KEY=

# ── Cloudflare Workers AI (Optional) ────
CLOUDFLARE_API_TOKEN=
CLOUDFLARE_ACCOUNT_ID=

# ── Ollama Cloud (Optional) ─────────────
OLLAMA_CLOUD_BASE_URL=https://cloud.ollama.com
OLLAMA_CLOUD_API_KEY=
EOF
    echo -e "${YELLOW}⚠  Template .env created! Edit it with your tokens before running.${NC}"
else
    echo -e "${GREEN}✓${NC} .env already exists — skipping"
fi

# ── 4. Sync dependencies ────────────────────────────────
echo -e "${BLUE}⬇ Installing dependencies...${NC}"
uv sync

# ── 5. Done ──────────────────────────────────────────────
echo ""
echo -e "${GREEN}✔ Setup complete!${NC}"
echo ""
echo -e "  1. Edit ${YELLOW}.env${NC} with your Discord bot token and channel ID"
echo -e "  2. Start the bot with: ${GREEN}uv run modeltrack${NC}"
echo ""
