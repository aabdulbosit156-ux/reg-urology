# 1-bosqich checkpointi — Railway-ready root access

- Holat: kod yakunlandi; real PostgreSQL integration gate Railway ulanishida bajariladi
- Sana: 2026-08-26
- Source of truth: `RegUrolog_Codex_Plan.md`

## Yetkazilganlar

- `Settings` production fail-fast validatsiyasi, Railway `DATABASE_URL` normalizatsiyasi va secret
  kontrakti.
- Async SQLAlchemy database lifecycle, alohida liveness/readiness va Alembic baseline migratsiyasi.
- Root login: constant-time token tekshiruvi, PostgreSQL rate-limit, 1 soatlik hashed sessiya, auth
  epoch rotation revoke, CSRF/Origin, logout va redacted audit.
- Barcha API xatolari uchun `code/message/field_errors/request_id` kontrakti.
- Real `/auth/me`, `/auth/root`, `/auth/logout` bilan ishlaydigan responsive Flowbite UI; token
  `localStorage` yoki URLga yozilmaydi.
- 390px mobile va 1440px desktop root-login acceptance; 44px submit target va overflow testi.
- Railway native `web + private api + managed postgres`, web reverse proxy, security headerlar,
  healthchecklar va amaldagi TypeScript IaC.
- GitHub Actions remote PostgreSQLda migratsiya + integration test va Chromiumda responsive E2E
  bajaradi; bu lokal Docker talab qilmaydi.
- Docker/Docker Compose lokal talablaridan voz kechildi; qaror ADR-0002da qayd etildi.

## Lokal tekshiruv dalili

| Tekshiruv | Natija |
|---|---|
| Backend pytest | 7 passed, 1 PostgreSQL integration skipped |
| Ruff | passed |
| strict mypy | passed |
| Alembic PostgreSQL offline SQL | passed |
| Frontend TypeScript | passed |
| Vitest | 4 passed |
| Vite production build | passed |
| Playwright responsive E2E | 2 passed: mobile-390, desktop-1440 |
| Production Node static/proxy smoke | web 200, proxied auth 401, CSP present |

Skipped integration test muvaffaqiyatsizlik emas: foydalanuvchi talabi bo‘yicha lokal PostgreSQL yoki
Docker o‘rnatilmadi. `TEST_DATABASE_URL` berilganda test root login → session → CSRF logout oqimini
haqiqiy migratsiya qilingan PostgreSQLda bajaradi.
