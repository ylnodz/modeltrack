#!/bin/bash

# Check if the repository exists, clone if not
if [[ ! -d "modeltrack" ]]; then
    git clone https://github.com/ylnodz/modeltrack.git
fi

# Navigate to the project directory
cd modeltrack || exit 1

# Pull the latest changes
if ! git pull; then
    echo "Failed to pull latest changes"
    exit 1
fi

# Check if uv is installed, install if not
if ! command -v uv &> /dev/null; then
    echo "uv not found. Installing Astral uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi

# Ensure the environment is set up
if [[ ! -f ".env" ]]; then
    echo "Error: .env file not found. Please create one with your configuration."
    exit 1
fi

# Sync dependencies using uv
uv sync

# Run the bot
uv run modeltrack
