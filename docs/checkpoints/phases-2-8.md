# 2–8-bosqichlar checkpointi — RegUrolog V1

- Holat: V1 kodi yakunlandi; tashqi Railway/Telegram production gate’lari deploy vaqtida qoladi
- Sana: 2026-08-26
- Source of truth: `RegUrolog_Codex_Plan.md`

## Bosqichlar natijasi

| Bosqich | Yetkazilgan vertikal bo‘lak | Holat |
|---|---|---|
| 2. Xodim/bot | encrypted bot token, `getMe`/webhook, inbox, QR invite + approval, browser-bound Telegram login, revoke/deactivate | Kod tayyor |
| 3. Registratsiya | consent FSM, draft/restart, ism/telefon, atomic patient+inquiry, optional sabab, repeat inquiry, UTM snapshot, dedup/outbox | Kod tayyor |
| 4. CRM | real patient/inquiry filter, masked contact, assignment conflict, attempt/lease/outcome, append-only note, daily sheet va A4 print | Kod va responsive UI tayyor |
| 5. Kalendar | versionli ish jadvali, override/block, 15 daqiqalik availability, doctor lock, create/reschedule, GiST overlap constraint | Kod tayyor; real PostgreSQL parallel test CI/Railwayda |
| 6. Tashrif | check-in/completed/cancel/no-show, grace, correction event, follow-up, versionli reminder/outbox | Kod va UI tayyor |
| 7. Analitika | registration cohort va activity mode, first-contact median/p90, UTM/operator breakdown, dinamika va no-show drill-down | Kod va dashboard tayyor |
| 8. Hardening | RBAC/CSRF/session, secret fail-fast, queue health, PII payload retention, 390/768/1024/1440 UI, Railway IaC va runbook | Lokal gate tayyor; external gate’lar quyida |

## Muhim kafolatlar

- Barcha bemor, CRM, kalendar va sozlama ekranlari real API server state bilan ishlaydi; demo bemor
  arraylari yo‘q.
- ADMINga Sozlamalar va global marketing ko‘rinmaydi, lekin asosiy himoya backend RBACda.
- Mobile’da jadval siqilmaydi: bemorlar card, kalendar agenda, navigatsiya drawer ko‘rinishiga o‘tadi.
- Appointment uchun 15 daqiqalik DB check, inquiry active partial unique va doctor/tstzrange GiST
  exclusion bor.
- Webhook DB inbox commitidan keyin javob beradi; worker retry/lease qiladi va stale reminderlarni
  yubormaydi.
- Raw Telegram inbox payloadi final holatdan 24 soat o‘tgach tozalanadi; dedup row qoladi.

## Lokal tekshiruv dalili

| Tekshiruv | Natija |
|---|---|
| Backend pytest | 11 passed, 2 PostgreSQL integration skipped |
| Ruff format/check | passed |
| strict mypy | passed |
| Alembic PostgreSQL offline SQL | passed; `btree_gist`, GiST exclusion va unique nomlar ko‘rildi |
| Frontend TypeScript | passed |
| Vitest | 4 passed |
| Vite production build | passed |
| Playwright responsive E2E | 390/768/1024/1440 loyihalari konfiguratsiyada; 8 ta smoke |

Skipped testlar muvaffaqiyatsizlik deb yashirilmaydi: foydalanuvchi talabi bo‘yicha lokal PostgreSQL
yoki Docker o‘rnatilmadi. Ular `TEST_DATABASE_URL` bilan migratsiya qilingan PostgreSQLda root auth
va parallel slot constraintini bajaradi; GitHub CI PostgreSQL 17 service bilan shu gate’ni ishga
tushiradi.

## Productionga chiqishdan oldin qoladigan tashqi gate’lar

1. Railway project/database credentials bilan Alembic upgrade va ikkala PostgreSQL integration
   testini real managed DBda o‘tkazish.
2. Staging test bot tokeni bilan invite → approval → login, patient registration va reminder retry
   smoke’ini bajarish.
3. Klinikadan haqiqiy doctor nomi, manzil, aloqa telefoni, ish jadvali, consent/privacy matni va
   notification template tasdig‘ini olish. Productionga soxta jadval seed qilinmaydi.
4. Railway backupni yoqish va productiondan alohida databasega restore drill o‘tkazish.
5. Tibbiy/huquqiy data retention va kirish siyosatini klinika mas’uli bilan tasdiqlash.

Bu gate’lar koddagi TODO emas; ular tashqi hisob, haqiqiy bot/DB va operator tasdig‘ini talab qiladi.
Aniq ketma-ketlik `docs/deployment/railway.md` va `docs/operations/runbook.md`da.
