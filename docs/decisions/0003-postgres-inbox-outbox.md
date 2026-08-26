# ADR-0003: PostgreSQL inbox/outbox va bitta worker

- Holat: qabul qilindi
- Sana: 2026-08-26

## Kontekst

Telegram webhook tez 2xx qaytarishi, tashqi API nosozligi bron yoki registratsiya tranzaksiyasini
bekor qilmasligi va lokal/production infrasi Redisni majburiy qilmasligi kerak.

## Qaror

- Webhook faqat `(bot_id, update_id)` unique inbox yozuvi commit qilingach `204` qaytaradi.
- Bitta worker inboxni kelish tartibida, outboxni `due_at` tartibida `FOR UPDATE SKIP LOCKED` va
  60 soniyalik lease bilan oladi.
- Xabar yuborish xatosi exponential backoff bilan qayta uriniladi; Telegram bloklagan chat
  `reachable=false` qilinadi.
- Appointment notification jobida appointment versiyasi tekshiriladi; rescheduled/cancelled eski
  reminder yuborilmaydi.
- Dedup yozuvi saqlanadi, ammo final inbox raw payloadi default 24 soatdan keyin `{}`ga tozalanadi.
- V1da worker replica soni bitta. Horizontal scale uchun per-chat partition/order dizayni alohida
  ADRsiz yoqilmaydi.

## Oqibatlar

DB commit va Telegram delivery mustaqil, retry kuzatiladigan bo‘ladi. PostgreSQL queue katta
hajmdagi universal broker o‘rnini bosmaydi; backlog va worker heartbeat `/health/system`da
kuzatiladi.
