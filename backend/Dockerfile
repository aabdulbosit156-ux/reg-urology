# Single image for both Railway services that run this backend, switched by SERVICE_ROLE:
#   - web (default): runs migrations, then the FastAPI app under uvicorn
#   - bot:           set SERVICE_ROLE=bot on that service's variables — runs aiogram
#                    long-polling (`python -m app.bot.run`) instead.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# Install dependencies first so this layer is cached across code-only changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project --no-dev

COPY . .
RUN uv sync --locked --no-dev

EXPOSE 8000

CMD ["sh", "-c", "if [ \"$SERVICE_ROLE\" = \"bot\" ]; then python -m app.bot.run; else alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}; fi"]
