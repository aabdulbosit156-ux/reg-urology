# syntax=docker/dockerfile:1.7
#
# Single-service image: builds the frontend, builds the Python backend, and ships
# one runtime that serves the static UI, exposes the API, and co-hosts the
# Telegram worker in-process (REGUROLOG_PROCESS=all).

ARG NODE_VERSION=24.19.0
ARG PYTHON_VERSION=3.13.15
ARG UV_VERSION=0.11.16


# ── Frontend build ───────────────────────────────────────────────────────────
FROM node:${NODE_VERSION}-alpine3.23 AS web-build

WORKDIR /app
ENV CI=true

RUN npm install --global npm@10.9.8

COPY package.json package-lock.json ./
COPY apps/web/package.json ./apps/web/package.json

RUN npm ci --omit=dev --ignore-scripts

COPY apps/web ./apps/web

RUN npm run build --workspace=@regurolog/web


# ── Backend build ────────────────────────────────────────────────────────────
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

FROM python:${PYTHON_VERSION}-slim-trixie AS backend-build

COPY --from=uv /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

COPY pyproject.toml uv.lock ./
COPY apps/api/pyproject.toml ./apps/api/pyproject.toml

RUN uv sync --frozen --no-dev --no-install-workspace

COPY apps/api ./apps/api

RUN uv sync --frozen --no-dev --no-editable


# ── Runtime ──────────────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim-trixie AS runtime

LABEL org.opencontainers.image.title="RegUrolog" \
      org.opencontainers.image.description="RegUrolog all-in-one: UI, API and Telegram worker"

RUN groupadd --system --gid 10001 regurolog \
    && useradd --system --uid 10001 --gid regurolog --home-dir /app --shell /usr/sbin/nologin regurolog

WORKDIR /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    REGUROLOG_PROCESS=all \
    WEB_DIST_DIR=/app/web

COPY --from=backend-build --chown=regurolog:regurolog /app/.venv /app/.venv
COPY --from=backend-build --chown=regurolog:regurolog /app/apps/api/alembic /app/apps/api/alembic
COPY --from=backend-build --chown=regurolog:regurolog /app/apps/api/alembic.ini /app/apps/api/alembic.ini
COPY --from=web-build --chown=regurolog:regurolog /app/apps/web/dist /app/web
COPY --chown=regurolog:regurolog docker-entrypoint.sh /app/docker-entrypoint.sh

RUN chmod +x /app/docker-entrypoint.sh

USER regurolog

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT','8000') + '/api/v1/health/live').read()"

ENTRYPOINT ["/app/docker-entrypoint.sh"]
