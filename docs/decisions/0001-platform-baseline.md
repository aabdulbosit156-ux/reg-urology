# ADR-0001: platforma va UI baseline

- Holat: qabul qilindi
- Sana: 2026-08-26
- Biznes vaqt zonasi: `Asia/Tashkent`

## Qaror

RegUrolog V1 modulli monolit bo‘ladi. Backend FastAPI va async SQLAlchemy, frontend React/Vite/TypeScript, UI Flowbite React va Tailwind CSS, ma’lumotlar bazasi PostgreSQL. Telegram update’lari PostgreSQL inbox orqali, tashqi xabarlar outbox orqali qayta ishlanadi.

Frontend baseline:

| Paket | Versiya |
|---|---:|
| React / React DOM | 19.2.8 |
| Flowbite React | 0.12.17 |
| Tailwind CSS | 4.3.3 |
| Vite | 8.2.2 |
| TypeScript | 7.0.2 |
| TanStack Query | 5.102.5 |
| Lucide React | 1.34.0 |

Backendning bevosita bazaviy paketlari:

| Paket | Versiya |
|---|---:|
| FastAPI | 0.141.1 |
| SQLAlchemy | 2.0.52 |
| Alembic | 1.19.1 |
| aiogram | 3.30.0 |

To‘liq tranzitiv versiyalar `package-lock.json` va `uv.lock`da saqlanadi. Flowbite React pre-1.0 bo‘lgani sabab yangilashdan oldin ishlatilgan komponent API’lari qayta tekshiriladi.

`flowbite-react@0.12.17`ning `deepmerge-ts@7.1.5` dependency’si uchun e’lon qilingan stack-exhaustion advisory sabab root override `deepmerge-ts@8.0.0`ga o‘rnatildi. Ushbu override typecheck, component test va production build bilan release gate’da qayta tekshiriladi. `jsdom@29.0.1` lokal Node 24 baseline bilan mosligi uchun tanlandi.

Package manager `npm@10.9.8`ga mahkamlandi: npm 11 workspace linklari orqali root override’larni ayrim holatlarda qo‘llamasligi sabab xavfsizlik override’i npm 10 bilan deterministik lock qilinadi.

## UI qarori

Teal asosiy rang, oq content va slate fon ishlatiladi. UI mobile-first: 390pxda off-canvas navigatsiya, murakkab jadvallar uchun labeled card-list, kalendar uchun agenda va kamida 44px touch target. 768, 1024 va 1440px alohida acceptance o‘lchamlari.

## Manbalar

- https://flowbite-react.com/docs/guides/vite
- https://flowbite-react.com/docs/getting-started/compatibility
- https://flowbite-react.com/docs/customize/theme
- https://www.npmjs.com/package/react
- https://www.npmjs.com/package/flowbite-react
- https://www.npmjs.com/package/tailwindcss
- https://www.npmjs.com/package/vite
- https://pypi.org/project/fastapi/
- https://pypi.org/project/SQLAlchemy/
- https://pypi.org/project/alembic/
- https://pypi.org/project/aiogram/
