# ADR-0004: Deterministik container deployment

- Holat: qabul qilindi
- Sana: 2026-08-26

## Kontekst

ADR-0002 lokal Docker majburiyatini rad etdi va dastlab Railway native/Railpack build tanlandi.
Amaliy deployda build va start command auto-detectioni workspace dependencylari bilan beqaror
chiqdi. Lokal kompyuterga Docker o‘rnatmaslik talabi o‘zgarishsiz qoladi.

## Qaror

- Railway buildlari Railpack auto-detection o‘rniga repositorydagi pinned multi-stage
  Dockerfile’lardan foydalanadi.
- `web` root `Dockerfile`dan quriladi; final image’da faqat statik build va Node reverse proxy bor.
- `api` va `worker` bitta `Dockerfile.backend` image’ini ishlatadi. `REGUROLOG_PROCESS` faqat `api`
  yoki `worker` qiymatini qabul qiladigan yagona runtime selector hisoblanadi.
- Final image’lar non-root user bilan ishlaydi; dependencylar lockfile orqali production-only
  o‘rnatiladi. Build tool’lari runtime image’ga ko‘chirilmaydi.
- Railway Build/Start override’lari ishlatilmaydi. Docker image `CMD`i yagona start kontrakti;
  migration API pre-deploy commandida image ichidagi `alembic` bilan bajariladi.
- CI ikkala Dockerfile’ni haqiqiy `docker build` bilan tekshiradi. Lokal Docker talab qilinmaydi.

## Oqibatlar

Railway, CI va rollback deploymentlari bir xil immutable build kontraktini ishlatadi; `npm`, `uv`
yoki source tree runtime’da bo‘lishiga tayanilmaydi. Base image va uv versiyalarini yangilash alohida
dependency maintenance vazifasi bo‘ladi. ADR-0002ning topologiya va lokal Dockersiz ishlash qarorlari
amalda qoladi; faqat Railway native build qismi shu ADR bilan almashtiriladi.
