FROM python:3.12-slim

# uv for fast, locked dependency installs
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

# Install dependencies first (layer cache), then the project
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-install-project --no-dev

COPY src ./src
COPY scripts ./scripts
COPY setup.sh startup.sh ./
RUN uv sync --frozen --no-dev

# Non-root runtime user; DB lives on a mounted volume
RUN useradd -m -u 1000 modeltrack && mkdir -p /data && chown -R modeltrack /app /data
USER modeltrack

ENV DB_PATH=/data/modeltrack.db
EXPOSE 8000

CMD ["uv", "run", "--no-dev", "modeltrack"]
