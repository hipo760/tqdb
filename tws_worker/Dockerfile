# ── Stage 1: build virtualenv ─────────────────────────────────────────────────
FROM python:3.11-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency metadata first (layer-cache friendly)
COPY pyproject.toml uv.lock* ./
COPY ibkr_libs/ ibkr_libs/

# Build the venv with all dependencies (no dev extras)
RUN uv sync --frozen --no-dev

# ── Stage 2: runtime image ────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Copy the virtualenv from the builder stage
COPY --from=builder /app/.venv .venv

# Copy application source
COPY kline_fetcher.py ./

# Default config (user should mount their own over /config/config.yaml)
COPY config.yaml /config/config.yaml

ENV PATH="/app/.venv/bin:$PATH"
ENV CONFIG_PATH="/config/config.yaml"
ENV PYTHONUNBUFFERED=1

# Health-check: verify the module can be imported
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import kline_fetcher" || exit 1

CMD ["python", "kline_fetcher.py"]
