# 0-bosqich checkpointi — Kontrakt

- Holat: bajarildi
- Sana: 2026-08-26
- Source of truth: `RegUrolog_Codex_Plan.md`

## Yetkazilganlar

- `regurolog-flowbite-ui` Codex skilli discoverable skill katalogida yaratildi va `quick_validate.py` bilan validatsiya qilindi.
- Skill references: design tokenlar, Flowbite component patternlari, server state/accessibility va 390/768/1024/1440px acceptance qoidalari.
- React + Flowbite + Tailwind mobile-first app shell: 390pxda surilma navigatsiya, desktopda sidebar, kamida 44px menyu tugmalari.
- Asosiy navigatsiya source-of-truthga mos uch bo‘lim: Boshqaruv, Bemorlar, Sozlamalar. Kalendar keyingi fazada Bemorlar ichidagi tab bo‘ladi.
- FastAPI skeleti, `/api/v1/health/live`, `/api/v1/openapi.json` va domain enum/constantlari.
- `StaffRole`, inquiry/contact/appointment statuslari, `Asia/Tashkent` va 15 daqiqalik qabul kontrakti kod va hujjatda.
- npm va uv lockfile’lar. Flowbite tranzitiv advisory’si `deepmerge-ts@8.0.0` override bilan yopildi; audit 0 vulnerability.
- Playwright’da real Microsoft Edge bilan mobile 390px va desktop 1440px render/overflow/navigatsiya smoke testi.

## Tekshiruv dalili

| Tekshiruv | Natija |
|---|---|
| Skill validator | `Skill is valid!` |
| Backend pytest | 2 passed |
| Ruff | passed |
| strict mypy | passed |
| Frontend TypeScript | passed |
| Vitest | 2 passed |
| Vite production build | passed |
| Playwright responsive E2E | 2 passed: mobile-390, desktop-1440 |
| npm audit | 0 vulnerability |

## Qaror va cheklovlar

- Flowbite 0.12.17 pre-1.0; har dependency upgrade’da ishlatilgan API’lar typecheck/build bilan qayta tasdiqlanadi.
- npm 11 workspace override regressiyasi sabab package manager `npm@10.9.8`ga pin qilindi.
- Docker lokal muhitda o‘rnatilmagan. Keyingi operator qarori bilan Docker/Compose talabi bekor qilindi;
  Railway native yo‘l ADR-0002da qabul qilindi.
- Hozirgi ekran CRM demo ma’lumoti emas; faqat haqiqiy API health, theme va responsive shellni ko‘rsatadi.

## Keyingi checkpoint

1-bosqich natijasi `docs/checkpoints/phase-1.md`da.
