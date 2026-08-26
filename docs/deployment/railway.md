# Railway deploy kontrakti

RegUrolog lokal Docker yoki Docker Compose talab qilmaydi. Production image’lari Railway va CI’da
repository Dockerfile’laridan quriladi. Topologiya to‘rtta Railway resursidan iborat: ochiq `web`,
private `api`, private `worker` va Railway boshqaradigan `postgres`.

## Servislar

| Servis | Dockerfile | Image entrypoint | Healthcheck |
|---|---|---|---|
| `web` | `/Dockerfile` | `node apps/web/server.mjs` | `/healthz` |
| `api` | `/Dockerfile.backend` | `REGUROLOG_PROCESS=api` | `/api/v1/health/ready` |
| `worker` | `/Dockerfile.backend` | `REGUROLOG_PROCESS=worker` | admin paneldagi `/api/v1/health/system` heartbeat |
| `postgres` | Railway managed PostgreSQL | Railway boshqaradi | Railway boshqaradi |

`Dockerfile` frontendni alohida build stage’da yig‘ib, runtime image’ga faqat `dist` va Node serverni
oladi. `Dockerfile.backend` locked production dependencylardan bitta non-root image yaratadi; o‘sha
image API va workerda `REGUROLOG_PROCESS` orqali ikki xil process sifatida ishlaydi. Railway **Build
Command** va **Custom Start Command** bo‘sh bo‘lishi kerak: build Dockerfile’dan, start esa image
`CMD`idan olinadi.

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
4. Har uch servisning **Build Command** va **Custom Start Command** maydonlaridagi eski qiymatlarni
   tozalang. Variable mapping quyidagicha bo‘lsin:

   - `web`: `RAILWAY_DOCKERFILE_PATH=/Dockerfile`;
   - `api`: `RAILWAY_DOCKERFILE_PATH=/Dockerfile.backend`, `REGUROLOG_PROCESS=api`;
   - `worker`: `RAILWAY_DOCKERFILE_PATH=/Dockerfile.backend`, `REGUROLOG_PROCESS=worker`.

   `.railway/railway.ts` ham shu qiymatlarni source of truth sifatida saqlaydi. Oldingi Railpack
   deploymentidan o‘tayotganda bir marta **Clear build cache** bilan redeploy qiling.
5. Faqat `web` servisida public domain yarating. `api` va `worker` public domainlarini o‘chirilgan
   holda qoldiring.
6. `api` va `worker`da bir xil sealed qiymatlarni kiriting:

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
7. Faqat `api` servisining **Pre-deploy Command** maydoniga kiriting:

   ```bash
   alembic -c apps/api/alembic.ini upgrade head
   ```

8. Migratsiya muvaffaqiyatli tugagach `api`, bitta replica `worker`, so‘ng `web`ni deploy qiling.
9. Root orqali botni ulang. Backend `getMe` bilan tekshiradi, tokenni encrypted saqlaydi va webhook
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
