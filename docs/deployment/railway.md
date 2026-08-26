# Railway deploy kontrakti

RegUrolog lokal Docker yoki Docker Compose talab qilmaydi. Production uchta Railway resursidan
iborat: ochiq `web`, faqat private networkdagi `api` va Railway boshqaradigan `postgres`.

## Servislar

| Servis | Build | Start | Healthcheck |
|---|---|---|---|
| `web` | `npm ci --include=dev && npm run build --workspace @regurolog/web` | `npm run start --workspace @regurolog/web` | `/healthz` |
| `api` | `uv sync --frozen` | `uv run --no-sync uvicorn regurolog_api.main:app --app-dir apps/api/src --host 0.0.0.0 --port $PORT` | `/api/v1/health/ready` |
| `postgres` | Railway managed PostgreSQL | Railway boshqaradi | Railway boshqaradi |

`web` `/api/*` so‘rovlarini `http://${{api.RAILWAY_PRIVATE_DOMAIN}}:${{api.PORT}}`ga uzatadi.
Shuning uchun cookie same-origin bo‘lib qoladi va `api`ga public domain berish shart emas.

## Birinchi deploy

1. Railway project yarating va Railway CLI bilan project/environmentga link qiling.
2. Amaldagi IaC rejasini ko‘rib, resurslarni yarating:

   ```bash
   railway config plan
   railway config apply
   ```

3. Bir xil GitHub repositoriyani `api` va `web` servislariga source sifatida ulang. Har ikkala servis
   root directorysi `/` bo‘lib qolsin: rootdagi `uv.lock` va `package-lock.json` build uchun kerak.
4. Faqat `web` servisida public domain yarating. `api` public domainini o‘chirilgan holda qoldiring.
5. `api` servisida quyidagi sealed qiymatlarni kiriting:

   - `ADMIN_TOKEN`: kamida 32 random byte;
   - `SESSION_SECRET`: `ADMIN_TOKEN`dan mustaqil kamida 32 random byte;
   - `PUBLIC_BASE_URL`: web servisning to‘liq `https://...` manzili;
   - `ALLOWED_ORIGINS`: xuddi shu web origin (bir nechta bo‘lsa vergul bilan).

6. `api` servisining **Pre-deploy Command** maydoniga quyidagini kiriting:

   ```bash
   uv run --no-sync alembic -c apps/api/alembic.ini upgrade head
   ```

7. Pre-deploy migratsiya muvaffaqiyatli tugagach `api`, so‘ng `web`ni deploy qiling.

Railway IaC hali pre-deploy commandni TypeScript authoring API orqali ifodalamaydi; shu bitta maydon
dashboardda qo‘yiladi. Eski `railway.json`/`railway.toml` qo‘shilmagan, chunki Config as Code formati
eskirgan va Railway tomonidan yopilmoqda.

## Production tekshiruvi

- `https://<web-domain>/healthz` — web process;
- `https://<web-domain>/api/v1/health/live` — API process;
- `https://<web-domain>/api/v1/health/ready` — PostgreSQL bilan birga readiness;
- root login xato tokenni log, URL yoki `localStorage`ga yozmasligi;
- `api` servisida public domain yo‘qligi;
- backup va restore mashqi Railway PostgreSQL sozlamalarida alohida yoqilganligi.

Rollbackda oldingi app deployment qaytariladi. Migratsiya downgrade avtomatik bajarilmaydi; avval
forward-compatible tuzatish tanlanadi, ma’lumotni yo‘qotadigan downgrade esa operator tasdig‘isiz
ishga tushirilmaydi.
