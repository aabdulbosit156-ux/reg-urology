# RegUrolog production runbook

## Deploy oldidan

1. CI’da backend lint/type/test, Alembic upgrade, frontend type/test/build va responsive E2E yashil
   bo‘lsin.
2. `.railway/railway.ts` planini ko‘rib chiqing; `worker` replicasini V1da `1` saqlang.
3. Railway secret/reference variablelari `api` va `worker`da bir xil ekanini tekshiring.
4. `api` pre-deploy Alembic commandi muvaffaqiyatli bo‘lmasa app deployini davom ettirmang.

## Deploydan keyingi smoke

1. `/healthz`, `/api/v1/health/live` va `/api/v1/health/ready` `200` qaytarsin.
2. Root login qiling; `/api/v1/health/system`da `worker=ok`, backlog normal va bot connected
   ekanini tekshiring.
3. Staging test botida bitta staff login va bitta bemor registratsiyasini bajaring. Productionda
   test bemorlarga xabar yubormang.
4. 390px telefonda bemor kartasi → qayta aloqa → kalendarga o‘tish, desktopda jadval va print
   preview’ni tekshiring.

## Worker yoki queue muammosi

- `worker=stale`: Railway worker logi/restart holatini tekshiring; ayni paytda ikkinchi replica
  qo‘shmang. Processni restart qilish xavfsiz: lease tugagach job qayta olinadi.
- Inbox `failed`: `last_error` klassini ko‘ring, bot token/webhook va DB invariantini tuzating.
  Payload retention tugashidan oldin kerakli, maxfiy bo‘lmagan diagnostikani yozib oling.
- Outbox backlog: Telegram 429 bo‘lsa retry vaqtini kuting; forbidden chat avtomatik unreachable.
  Appointment versiyasi eskirgan joblar cancelled bo‘ladi.
- Queue yozuvini qo‘lda `sent/completed` deb belgilamang; sababni tuzatib worker retry oqimidan
  foydalaning.

## Bot tokeni va secret rotatsiyasi

- Bot tokenini Sozlamalar orqali almashtirish oldidan replacement tasdig‘ini bering. Yangi token
  encrypted saqlanadi va yangi webhook o‘rnatiladi; eski webhook best-effort o‘chiriladi.
- `/health/system`dagi `bot_cleanup_required > 0` bo‘lsa eski bot tokeni Telegram tomonidan
  bekor qilingan yoki cleanup ishlamagan. Eski botni BotFather orqali revoke qiling; inactive
  RegUrolog endpoint baribir `404` qaytaradi.
- `ADMIN_TOKEN` rotatsiyasi oldingi root sessiyalarni bekor qiladi.
- `SESSION_SECRET` rotatsiyasi barcha cookie sessiyalarni amalda bekor qiladi; maintenance oynasida
  bajaring.
- `APP_ENCRYPTION_KEY`ni shunchaki almashtirmang: avval bot tokenini yangi kalit bilan qayta
  shifrlaydigan nazoratli migratsiya kerak.
- `WEBHOOK_SECRET` rotatsiyasida `api` va `worker` qiymatlarini birga yangilang, keyin botni qayta
  connect qilib Telegram webhook headerini yangilang.

## Backup va restore mashqi

1. Railway PostgreSQL backup siyosatini productionda yoqing va oxirgi muvaffaqiyatli backup vaqtini
   qayd eting.
2. Restore’ni hech qachon production database ustiga sinamang. Yangi vaqtinchalik Railway Postgres
   yarating va backupni unga tiklang.
3. Restore databasega `alembic current` va read-only tekshiruvlarni bajaring: staff/patient/inquiry/
   appointment sonlari, faol appointment overlap yo‘qligi, oxirgi audit va settings versionlari.
4. `TEST_DATABASE_URL`ni vaqtinchalik restore databasega berib integration testlarni bajaring.
5. Natija, RPO/RTO va operatorni incident jurnalida qayd eting; keyin vaqtinchalik resursni Railway
   orqali o‘chiring.

## Incident va rollback

- Yangi app regressiyasida oldingi `api/worker/web` deploymentga qayting; ma’lumotlar bazasini
  avtomatik downgrade qilmang.
- Schema muammosida avval forward-fix migratsiya tanlang. Destructive SQL yoki restore alohida
  operator tasdig‘i va tekshirilgan backupni talab qiladi.
- Loglarda token, telefon, bemor sababi yoki raw Telegram update bo‘lmasin. Incident yozuvida request
  ID, entity ID, vaqt va maxfiy bo‘lmagan error klassidan foydalaning.
