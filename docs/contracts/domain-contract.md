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
