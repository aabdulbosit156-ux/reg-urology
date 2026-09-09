# Backend

FastAPI + SQLAlchemy (async) + Alembic + PostgreSQL. See [PLAN.md](../PLAN.md) for the full spec.

## Setup

```
uv sync
cp .env.example .env
# set DATABASE_URL, JWT_SECRET, DEV_PASSWORD_HASH (see .env.example for how to generate the hash)
```

## Run

```
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

API is served under `/api` (e.g. `/api/health`, `/api/auth/dev-login`).

## Migrations

```
uv run alembic revision --autogenerate -m "message"
uv run alembic upgrade head
```
