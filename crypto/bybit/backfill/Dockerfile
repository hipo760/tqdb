# ---------------------------------------------------------------------------
# Stage 1 — dependency installer
# Build context: crypto/   (one level above bybit/)
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS builder

# Copy uv binary from the official distroless image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Install dependencies as a separate cached layer before copying source.
# pyproject.toml + uv.lock live at crypto/ (the build context root).
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv sync --locked --no-install-project --no-editable

# Copy only the files the service needs:
#   bybit/backfill/  — the service modules
#   bybit/http_client.py — shared HTTP helper
COPY bybit/backfill/ /app/
COPY bybit/http_client.py /app/http_client.py

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv sync --locked --no-editable

# ---------------------------------------------------------------------------
# Stage 2 — lean runtime image
# ---------------------------------------------------------------------------
FROM python:3.11-slim

LABEL maintainer="TQDB Team"
LABEL description="Bybit kline → Cassandra minbar backfill service"

# Non-root user for security
RUN groupadd --gid 1000 appuser \
 && useradd --uid 1000 --gid appuser --no-create-home appuser

WORKDIR /app

# Copy the pre-built venv and source from the builder
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
COPY --from=builder --chown=appuser:appuser /app /app

# Put the venv's bin directory on PATH so `python` and all entry-points resolve
ENV PATH="/app/.venv/bin:$PATH"

# Cassandra connection
ENV CASSANDRA_HOST=cassandra
ENV CASSANDRA_PORT=9042
ENV CASSANDRA_USER=""
ENV CASSANDRA_PASSWORD=""
ENV CASSANDRA_KEYSPACE=tqdb1
ENV CASSANDRA_TABLE=minbar

# Symbol source
ENV SYMBOL_SOURCE=api
ENV SYMBOL_API_URL=""
ENV SYMBOL_API_TOKEN=""

# Daily backfill window
ENV DAILY_BACKFILL_DAYS=3

# API server
ENV API_HOST=0.0.0.0
ENV API_PORT=8000

EXPOSE 8000

USER appuser

CMD ["python", "main.py"]
