# ADR-0002: Docker-free lokal ish va Railway native deployment

- Holat: qabul qilindi
- Sana: 2026-08-26

## Kontekst

Operator lokal kompyuterga Docker o‘rnatmaslikni va productionni Railway’da joylashni tanladi.
Repositorydagi Python va Node lockfilelar deterministik build beradi; ma’lumotlar bazasi productionda
Railway PostgreSQL bo‘ladi.

## Qaror

- Lokal Dockerfile va Docker Compose majburiy emas va 1-bosqichda yaratilmaydi.
- Railway’da `web`, private `api`, private `worker` va managed `postgres` alohida servislar bo‘ladi.
- Brauzer faqat `web`ga ulanadi; Node runtime `/api/*`ni Railway private network orqali `api`ga proxy
  qiladi. Natijada auth cookie same-origin va API internetga bevosita ochilmaydi.
- Railway `DATABASE_URL` SQLAlchemy uchun runtime ichida `postgresql+psycopg://`ga normalizatsiya
  qilinadi.
- Alembic upgrade API pre-deploy commandda bajariladi; xato bo‘lsa yangi deployment ishga tushmaydi.
- Telegram inbox va outboxni bitta `worker` replica ketma-ket iste’mol qiladi; ko‘paytirishdan oldin
  bir Telegram foydalanuvchisining update tartibi uchun alohida partitionlash qarori talab qilinadi.
- Eski `railway.json`/`railway.toml` Config as Code o‘rniga amaldagi `.railway/railway.ts` IaC ishlatiladi.

## Oqibatlar

Lokal unit, contract, offline migration va browser testlari PostgreSQL o‘rnatmasdan ishlaydi. Haqiqiy
PostgreSQL integration testi `TEST_DATABASE_URL` bo‘lgan muhitda ishlaydi; lokal bazasiz u aniq
`skipped` bo‘ladi. Birinchi Railway deploydan oldin/vaqtida shu test managed PostgreSQLga qarshi
o‘tkaziladi.
