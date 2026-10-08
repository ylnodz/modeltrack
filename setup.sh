#!/usr/bin/env bash
set -e

GREEN='\033[0;32m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'

echo -e "${BLUE}  ModelTrack — Setup${NC}\n"

# 1. Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✖ python3 not found. Install Python 3.11+ first.${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} Python $(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"

# 2. uv
if ! command -v uv &> /dev/null; then
    echo -e "${YELLOW}⬇ Installing uv...${NC}"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi
echo -e "${GREEN}✓${NC} uv $(uv --version | awk '{print $2}')"

# 3. .env
if [ ! -f .env ]; then
    cp .env.example .env
    echo -e "${YELLOW}⚠  Created .env from .env.example — fill in your Discord token + channel id.${NC}"
else
    echo -e "${GREEN}✓${NC} .env already exists — skipping"
fi

# 4. deps
echo -e "${BLUE}⬇ Installing dependencies...${NC}"
uv sync

echo -e "\n${GREEN}✔ Setup complete!${NC}"
echo -e "  1. Edit ${YELLOW}.env${NC} with your Discord credentials"
echo -e "  2. Start with ${GREEN}uv run modeltrack${NC}\n"
