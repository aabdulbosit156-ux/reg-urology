# Railway deploy kontrakti

RegUrolog bitta servis sifatida deploy qilinadi. Rootdagi `Dockerfile` frontendni va
Python backendni bitta image ichiga yig‘adi; o‘sha image bir jarayonda static UI’ni beradi,
API’ni ochadi va Telegram worker’ini ichida (`REGUROLOG_PROCESS=all`) ishlatadi. Topologiya
ikki resursdan iborat: `app` va Railway boshqaradigan `postgres`.

## Servis

| Servis | Dockerfile | Ichida ishlaydigan | Healthcheck |
|---|---|---|---|
| `app` | `/Dockerfile` | API + frontend + worker (`REGUROLOG_PROCESS=all`) | `/api/v1/health/ready` |
| `postgres` | Railway managed PostgreSQL | Railway boshqaradi | Railway boshqaradi |

Frontend `/api/*` so‘rovlarini xuddi shu origin orqali API’ga yuboradi (same-origin, proxy
kerak emas). Migratsiya container startida avtomatik bajariladi.

## Birinchi deploy

1. Railway project yarating va GitHub repositoriyani `app` servisiga source qiling. Root
   directory `/` bo‘lib qolsin: rootdagi `uv.lock` va `package-lock.json` build uchun kerak.
2. Servisning **Build Command** va **Custom Start Command** maydonlarini bo‘sh qoldiring —
   build Dockerfile’dan, start esa image entrypointidan (`docker-entrypoint.sh`) olinadi.
3. Projectga PostgreSQL qo‘shing.
4. `app` servisiga faqat quyidagilarni kiriting:

   - `ADMIN_TOKEN`: kamida 32 random byte (`openssl rand -hex 32`). Bu yagona majburiy secret —
     `SESSION_SECRET`, `APP_ENCRYPTION_KEY` va `WEBHOOK_SECRET` kod ichida shundan deterministik
     hosil qilinadi (ADMIN_TOKEN o‘zgarmaguncha barqaror, ma’lumot yo‘qolmaydi);
   - `DATABASE_URL`: Railway Postgres reference — `${{Postgres.DATABASE_URL}}`.

   `PUBLIC_BASE_URL` avtomatik `RAILWAY_PUBLIC_DOMAIN`dan olinadi; `COOKIE_SECURE`,
   `TRUST_PROXY_HEADERS`, `REGUROLOG_ENV=production` va CORS Railway’da avtomatik to‘g‘rilanadi.
   Ularni qo‘lda kiritish shart emas. Secretlarni Git, frontend environment yoki build logiga
   yozmang.
5. `app` servisida public domain yarating. Deploy tugagach:
   - `https://<domain>/` — UI;
   - `https://<domain>/api/v1/health/live` — API liveness;
   - `https://<domain>/api/v1/health/ready` — PostgreSQL readiness.
6. Root orqali botni ulang. Backend `getMe` bilan tekshiradi, tokenni encrypted saqlaydi va
   webhook URL/header secretni Telegramga o‘zi o‘rnatadi (`PUBLIC_BASE_URL` shuning uchun kerak).

Migratsiya `docker-entrypoint.sh` ichida `alembic upgrade head` bilan har startda ishlaydi;
alohida pre-deploy command shart emas. Repositoryda eski `railway.json`/`railway.toml`
ishlatilmaydi.

### Alohida servislar (ixtiyoriy)

Katta yuklamada worker’ni ajratish kerak bo‘lsa, xuddi shu image’ni ikkinchi servisda
`REGUROLOG_PROCESS=worker` bilan ishga tushiring va birinchisini `REGUROLOG_PROCESS=api`
qiling. `all` rejim kichik/o‘rta yuklama uchun yetarli.

## Production darvozalari

- `https://<domain>/api/v1/health/live` — API process;
- `https://<domain>/api/v1/health/ready` — PostgreSQL readiness;
- root/director bilan `/api/v1/health/system` — worker heartbeat, inbox/outbox backlog va bot holati;
- `TEST_DATABASE_URL` bilan migratsiya qilingan Railway PostgreSQLga qarshi pytest integration;
- staging test bot bilan invite → approval → login va patient registration smoke;
- Railway backup yoqilganligi va alohida test databasega restore mashqi;
- 390/768/1024/1440 responsive hamda klaviatura smoke.

Rollbackda oldingi app deployment qaytariladi. Migratsiya downgrade avtomatik bajarilmaydi;
forward-compatible tuzatish tanlanadi, ma’lumotni yo‘qotadigan downgrade operator tasdig‘isiz
ishga tushirilmaydi. Batafsil incident va restore ketma-ketligi `docs/operations/runbook.md`da.
