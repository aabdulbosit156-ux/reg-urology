# Railway deploy kontrakti

RegUrolog lokal Docker yoki Docker Compose talab qilmaydi. Production to‘rtta Railway resursidan
iborat: ochiq `web`, private `api`, private `worker` va Railway boshqaradigan `postgres`.

## Servislar

| Servis | Build | Start | Healthcheck |
|---|---|---|---|
| `web` | `npm ci --include=dev && npm run build --workspace @regurolog/web` | `npm run start --workspace @regurolog/web` | `/healthz` |
| `api` | `uv sync --frozen` | `uv run --no-sync uvicorn regurolog_api.main:app --app-dir apps/api/src --host 0.0.0.0 --port $PORT` | `/api/v1/health/ready` |
| `worker` | `uv sync --frozen` | `uv run --no-sync python -m regurolog_api.worker` | admin paneldagi `/api/v1/health/system` heartbeat |
| `postgres` | Railway managed PostgreSQL | Railway boshqaradi | Railway boshqaradi |

`web` `/api/*` so‘rovlarini `http://${{api.RAILWAY_PRIVATE_DOMAIN}}:${{api.PORT}}`ga uzatadi.
Brauzer cookie’lari same-origin bo‘lib qoladi; `api` va `worker`ga public domain berilmaydi. Telegram
webhook ham public `web` orqali private `api`ga boradi.

## Birinchi deploy

1. Railway project yarating va Railway CLI bilan project/environmentga link qiling.
2. Amaldagi IaC rejasini ko‘rib, resurslarni yarating:

   ```bash
   railway config plan
   railway config apply
   ```

3. Bir xil GitHub repositoriyani `api`, `worker` va `web` servislariga source sifatida ulang. Root
   directory `/` bo‘lib qolsin: rootdagi `uv.lock` va `package-lock.json` build uchun kerak.
4. Faqat `web` servisida public domain yarating. `api` va `worker` public domainlarini o‘chirilgan
   holda qoldiring.
5. `api` va `worker`da bir xil sealed qiymatlarni kiriting:

   - `ADMIN_TOKEN`: kamida 32 random byte;
   - `SESSION_SECRET`: undan mustaqil kamida 32 random byte;
   - `APP_ENCRYPTION_KEY`: bot tokenini shifrlash uchun mustaqil kamida 32 random byte;
   - `WEBHOOK_SECRET`: mustaqil kamida 32 random byte;
   - `PUBLIC_BASE_URL`: `web` servisining path/querysiz to‘liq `https://...` origini;
   - `ALLOWED_ORIGINS`: xuddi shu web origin;
   - `COOKIE_SECURE=true`, `TRUST_PROXY_HEADERS=true`;
   - `INBOX_PAYLOAD_RETENTION_HOURS=24`.

   Secretlar servislar orasida Railway shared/reference variable orqali berilishi mumkin. Ularni
   Git, frontend environment yoki build logiga yozmang.
6. Faqat `api` servisining **Pre-deploy Command** maydoniga kiriting:

   ```bash
   uv run --no-sync alembic -c apps/api/alembic.ini upgrade head
   ```

7. Migratsiya muvaffaqiyatli tugagach `api`, bitta replica `worker`, so‘ng `web`ni deploy qiling.
8. Root orqali botni ulang. Backend `getMe` bilan tekshiradi, tokenni encrypted saqlaydi va webhook
   URL/header secretni Telegramga o‘zi o‘rnatadi.

Railway IaC hali pre-deploy commandni TypeScript authoring API orqali ifodalamaydi; shu bitta maydon
dashboardda qo‘yiladi. Repositoryda eski `railway.json`/`railway.toml` ishlatilmaydi.

## Production darvozalari

- `https://<web-domain>/healthz` — web process;
- `https://<web-domain>/api/v1/health/live` — API process;
- `https://<web-domain>/api/v1/health/ready` — PostgreSQL readiness;
- root/director bilan `/api/v1/health/system` — worker heartbeat, inbox/outbox backlog va bot holati;
- `TEST_DATABASE_URL` bilan migratsiya qilingan Railway PostgreSQLga qarshi pytest integration;
- staging test bot bilan invite → approval → login va patient registration smoke;
- Railway backup yoqilganligi va alohida test databasega restore mashqi;
- 390/768/1024/1440 responsive hamda klaviatura smoke.

Rollbackda oldingi app deployment qaytariladi. Migratsiya downgrade avtomatik bajarilmaydi;
forward-compatible tuzatish tanlanadi, ma’lumotni yo‘qotadigan downgrade operator tasdig‘isiz
ishga tushirilmaydi. Batafsil incident va restore ketma-ketligi `docs/operations/runbook.md`da.
