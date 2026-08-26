# RegUrolog V1 domain kontrakti

Bu hujjat kodga yaqin qisqa kontrakt. Tafsilot va istisnolar uchun `RegUrolog_Codex_Plan.md` source of truth hisoblanadi.

## Principal va ruxsatlar

- `DEV`: ENV root principal; barcha sozlama va tuzatishlar, sabab va audit bilan.
- `DIRECTOR`: bemor/CRM/kalendar, to‘liq dashboard, admin taklifi, sozlamalar va audit.
- `ADMIN`: bemor/CRM/kalendar hamda o‘z ko‘rsatkichlari; global sozlamalar va marketing hisoboti yo‘q.

API har endpoint va obyekt scope’ida ruxsatni tekshiradi. UI elementini yashirish xavfsizlik chegarasi emas.

## Holatlar

- Inquiry: `open -> closed`; qayta ochish faqat director/dev va sabab bilan.
- Contact attempt: `in_progress`, `answered`, `no_answer`, `busy`, `unreachable`, `wrong_number`, `aborted`, `interrupted`.
- Appointment: `scheduled -> checked_in -> completed`; `scheduled -> cancelled | no_show`.
- Vaqti o‘tgan, natijasi belgilanmagan appointment derived `outcome_pending`; avtomatik `no_show` emas.

## Vaqt

- Event/appointment instantlari UTC `timestamptz`.
- Biznes sana va kalendar `Asia/Tashkent`.
- Qabul davomiyligi 15 daqiqa va slotlar `[start, end)`.
- UI brauzer vaqt zonasidan qat’i nazar Toshkent vaqtini ko‘rsatadi.

## HTTP xato kontrakti

```json
{
  "code": "SLOT_TAKEN",
  "message": "Bu vaqt hozirgina band qilindi.",
  "field_errors": [],
  "request_id": "opaque-request-id"
}
```

`401`, `403`, `404`, `409`, `422`, `429` alohida. State-changing so‘rovlarda `Idempotency-Key`; versiyali mutatsiyada `If-Match`. GET biznes holatini o‘zgartirmaydi.

## Root sessiya

- `POST /api/v1/auth/root` tokenni faqat JSON bodyda qabul qiladi; URL, log, frontend bundle yoki
  browser storagega yozmaydi.
- `ADMIN_TOKEN` fixed-length SHA-256 digestlar orqali constant-time taqqoslanadi va kamida 32 byte.
- Xato urinishlar source hash bo‘yicha PostgreSQLda lock bilan rate-limit qilinadi.
- Muvaffaqiyatli kirishda 1 soatlik opaque `HttpOnly`, `Secure`, `SameSite=Lax` cookie beriladi;
  bazada faqat keyed hash saqlanadi.
- `ADMIN_TOKEN` rotatsiyasi auth epochni o‘zgartiradi va oldingi root sessiyani keyingi so‘rovda bekor
  qiladi.
- Mutatsiya cookie sessiyasi bilan birga `Origin` va `X-CSRF-Token`ni tekshiradi.
- Login, xato login, rate-limit va logout maxfiy qiymatlarsiz audit event bo‘ladi.

## Telegram, xodim va worker

- Bot tokeni `getMe` bilan tekshiriladi, faqat backendda encrypted saqlanadi; oldingi botni
  almashtirish explicit tasdiq talab qiladi.
- Webhook opaque path va `X-Telegram-Bot-Api-Secret-Token`ni tekshiradi; update unique inboxga
  commit bo‘lmaguncha `204` bermaydi.
- Invite va panel login tokenlari hash ko‘rinishida, muddatli va bir martalik. Staff login browser
  binding va Telegramdagi alohida approve/reject bosqichiga ega.
- Staff deactivate sessiya/challengelarni bekor qiladi va ochiq assignmentlarni navbatga qaytaradi.
- Bitta worker inbox/outboxni lease + `SKIP LOCKED` bilan ishlaydi. Final inbox raw payloadi default
  24 soatdan keyin tozalanadi, dedup metadata qoladi.

## Registratsiya va CRM invariantlari

- Ism va `+998` telefon valid bo‘lgach patient, inquiry, consent, attribution va outbox bitta
  tranzaksiyada yaratiladi; optional sabab buni bloklamaydi.
- Telegram user ID patient uchun unique; telefon unique emas. Bir xil telefon auto-merge qilinmaydi,
  `possible_duplicate` flag qo‘yiladi.
- Bir patient/doctor uchun faqat bitta open inquiry. Inbox va outbox idempotency takror update/xabarni
  dublikat qilmaydi.
- Ro‘yxatda telefon maskalangan. To‘liq kontakt faqat "Qayta aloqa" oqimida, assignment tekshiruvi va
  audit bilan ochiladi.
- Bir inquiryda bitta `in_progress` attempt. 30 daqiqada tugamagan urinish `interrupted`; bu
  `no_answer` degani emas.
- Qabul varaqasi inquiry va Toshkent biznes sanasi bo‘yicha bitta; urinish va izohlar append-only
  tarix sifatida bog‘lanadi.

## Kalendar va tashrif invariantlari

- Availability faqat joriy ko‘rinish; create/reschedule serverda jadval, override, block, horizon va
  doctor lockni qayta tekshiradi.
- PostgreSQL `btree_gist` exclusion bir doctorning `scheduled/checked_in` qabullarini overlap
  qildirmaydi. Bir inquiryda bitta faol appointment.
- Slot to‘qnashuvi `409 SLOT_TAKEN`; jadvalni mavjud qabul ustiga toraytirish `409
  SCHEDULE_CONFLICT` va conflict IDlarini beradi.
- Reschedule o‘sha appointment IDni saqlab, versiyani oshiradi; eski reminder workerda stale deb
  bekor qilinadi.
- `no_show` faqat grace vaqtidan keyin staff amali bilan. `completed` inquiry’ni `attended` sababi
  bilan yopadi; correction faqat DEV/DIRECTOR va majburiy sabab bilan append-only event yaratadi.

## API yo‘nalishlari

- Auth/staff: `/auth/*`, `/staff`, `/staff/invites*`, `/staff/{id}/deactivate`.
- Bot/webhook: `/bot*`, `/telegram/webhook/{opaque_path}`.
- CRM: `/patients*`, `/inquiries*`, `/contact-attempts*`, `/reception-sheets*`.
- Kalendar: `/doctors*`, `/schedule/*`, `/calendar/availability`, `/appointments*`.
- Boshqaruv: `/campaigns*`, `/settings*`, `/analytics/cohort`, `/analytics/activity`,
  `/reports/no-shows`, `/health/system`.

Mutatsiya ruxsati backend principal va obyekt assignmentiga qarab tekshiriladi. Root/DIRECTOR global
sozlamalar va correctionga ega; ADMIN global settings/marketing/correction APIlarida `403` oladi.
