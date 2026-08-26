# RegUrolog

Telegram orqali bemor murojaatlarini yig‘ish, xodimlar qayta aloqasi, 15 daqiqalik qabul kalendari
va boshqaruv hisobotlari uchun modulli monolit.

Asosiy talablar [RegUrolog_Codex_Plan.md](RegUrolog_Codex_Plan.md)da. 0–8-bosqichlarning V1 kodi
tayyor; lokal va production gate holati [yakuniy checkpoint](docs/checkpoints/phases-2-8.md)da.

## Lokal ish — Dockersiz

Lokal kompyuterga Docker yoki PostgreSQL o‘rnatish talab qilinmaydi. Bazasiz ham unit, contract,
offline migration, frontend va responsive browser testlari ishlaydi:

```powershell
uv sync --all-extras
uv run pytest
uv run ruff check apps/api
uv run mypy apps/api/src

npm install
npm run check
npm run test:e2e --workspace @regurolog/web
```

`pytest` ichidagi PostgreSQL integration testi `TEST_DATABASE_URL` bo‘lmasa ongli ravishda skip
qilinadi. Railway PostgreSQL ulangach migratsiya va shu test real bazada bajariladi.

## Lokal dev serverlar

`.env.example`dan `.env` yarating. Bazasiz liveness va root-login UI ko‘rinadi, ammo haqiqiy login
uchun `DATABASE_URL` kerak.

```powershell
uv run uvicorn regurolog_api.main:app --app-dir apps/api/src --reload
npm run dev --workspace @regurolog/web
```

Vite `/api` so‘rovlarini `http://127.0.0.1:8000`ga proxy qiladi.

## Railway

Production Dockerfile ishlatmaydi: Railway Railpack lockfilelardan native build qiladi. Topologiya:
ochiq `web`, private `api`, private `worker`, managed `postgres`. Aniq build/start, secret,
migration va rollback qadamlari [Railway deploy qo‘llanmasi](docs/deployment/railway.md)da; kundalik
ekspluatatsiya [runbook](docs/operations/runbook.md)da; infra source of truth
[.railway/railway.ts](.railway/railway.ts).
