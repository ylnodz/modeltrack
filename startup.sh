#!/usr/bin/env bash
# Start ModelTrack in the current directory (Wispbyte / panel friendly).
# Does NOT clone or pull — deploy the code, then run this.
set -e

cd "$(dirname "$0")"

if [ ! -f .env ]; then
    echo "Error: .env not found. Copy .env.example to .env and fill it in." >&2
    exit 1
fi

if ! command -v uv &> /dev/null; then
    echo "uv not found. Installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi

uv sync
exec uv run modeltrack
