# Repo-root Dockerfile used ONLY by the Telegram bot Railway service, which builds from the
# repository root (its Root Directory is unset). The web + frontend services have their own
# Root Directories (backend/, frontend/) and their own Dockerfiles, so they never use this one.
#
# It builds the same backend package and runs aiogram long-polling.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# Install dependencies first so this layer is cached across code-only changes.
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --locked --no-install-project --no-dev

COPY backend/ .
RUN uv sync --locked --no-dev

CMD ["python", "-m", "app.bot.run"]
