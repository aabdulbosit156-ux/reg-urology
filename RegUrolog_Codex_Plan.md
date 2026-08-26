# RegUrolog — Codex uchun texnik va amalga oshirish rejasi

Versiya: 1.0 · 26.08.2026 · Til: o‘zbekcha · Vaqt zonasi: Asia/Tashkent

**Maqsad:** Urolog Doktor Sardor uchun Telegram orqali murojaatlarni yig‘ish, xodimlar orqali qayta aloqa, 15 daqiqalik konsultatsiyaga yozish, qabul varaqasi va boshqaruv hisobotlarini bir tizimda yuritish.

Bu hujjat implementatsiya spetsifikatsiyasi. Dastur yoki Flowbite skill hali yaratilgan deb hisoblanmaydi. Quyidagi standart qarorlar foydalanuvchi talabidagi ochiq joylarni to‘ldiradi; konfiguratsiya orqali o‘zgaradiganlari alohida ko‘rsatilgan.

## 1. Chegaralar va asosiy qarorlar

| Masala | V1 qarori |
|---|---|
| Klinika va shifokor | Bitta klinika, bitta urolog; jadval doctor_id bilan bog‘lanadi |
| Asosiy menyu | 3 bo‘lim: Boshqaruv, Bemorlar, Sozlamalar; kalendar Bemorlar ichida |
| Ro‘yxatdan o‘tish | Rozilik, ism familiya va yaroqli telefon olingach darhol DB commit |
| Konsultatsiya sababi | Registratsiyadan keyingi ixtiyoriy ma’lumot; ro‘yxatga olishni bloklamaydi |
| Telefon | V1 O‘zbekiston: E.164 +998XXXXXXXXX; xalqaro raqamlar alohida keyingi talab |
| Qabul | Aynan 15 daqiqa; ish oraliqlari va istisnolar ichida |
| Bemor o‘zi vaqt tanlaydimi? | V1 yo‘q, vaqtni xodim belgilaydi |
| Qayta murojaat | Bir bemorda bitta ochiq murojaat; yopilgach yangi murojaat ochish mumkin |
| Bemor identifikatori | Patient UUID; Telegram user ID unique, telefon unique emas |
| Xodim login | Telegram orqali bir martalik, brauzerga bog‘langan tasdiqlash |
| Dev login | Backend ENVdagi ADMIN_TOKEN orqali alohida root session |
| Kelmagan holati | Vaqt o‘tdi deb avtomatik yakunlanmaydi; xodim tasdiqlaydi |
| Qabul varaqasi | Har murojaatning qayta aloqa boshlangan har Toshkent kuniga bitta varaqa |
| Qabulga kelganlik | Admin belgilaydi, o‘zgarish auditga tushadi |
| Til va dizayn | O‘zbekcha UI, Flowbite React, Lucide, oq/neytral + bitta asosiy rang, gradientsiz |

**V1ga kirmaydi:** tibbiy tashxis, davolash tavsiyasi, retsept, to‘lov/kassa, avtomatik telefon qo‘ng‘irog‘i, SMS, ommaviy reklama yuborish, ko‘p klinikali SaaS, bemorning o‘ziga vaqt bron qilish. “Qabul varaqasi” bu tashkiliy yozuv, to‘liq elektron tibbiy karta emas.

## 2. Arxitektura

| Qatlam | Texnologiya va vazifa |
|---|---|
| Telegram | aiogram 3.x, routerlar va registratsiya oqimi |
| API | FastAPI, Pydantic, async SQLAlchemy, Alembic |
| Ma’lumotlar | PostgreSQL — bemor, murojaat, sessiya, registratsiya drafti, jadval, audit |
| Frontend | React + TypeScript + Vite + Tailwind CSS + Flowbite React + lucide-react |
| Server holati | TanStack Query, validatsiyali formalar, OpenAPI asosida tiplangan klient |
| Navbat | PostgreSQL inbox/outbox + alohida worker; V1da Redis majburiy emas |
| Infra | Railway native: public web/proxy, private api/worker, managed PostgreSQL; lokal Docker talab qilinmaydi |
| Test | pytest + haqiqiy PostgreSQL integration; Vitest/Testing Library; Playwright E2E |

Modulli monolit tanlansin. API va bot bitta domain service qatlamidan foydalanadi; biznes qoidalar handler va React ichida takrorlanmaydi. Webhook API orqali keladi, aiogram dispatcher worker ichida ishlaydi. POST webhook 2xx javobini **faqat update PostgreSQL inboxga yozilgandan keyin** beradi. DB ishlamasa 5xx, Telegram qayta yetkazishiga imkon beriladi. Inboxdagi har update `(bot_id, update_id)` bo‘yicha unique.

Worker bir Telegram foydalanuvchisining update’larini ketma-ket qayta ishlaydi; DBdagi draft saqlangani sabab restart registratsiyani yo‘qotmaydi. V1ning bitta inbox consumer cheklovi hujjatlashtirilsin. Outbox joblari lease va `FOR UPDATE SKIP LOCKED` bilan olinadi; process o‘lsa lease muddati tugab qayta olinadi.

Kutubxonalarning o‘zaro mos stable versiyalari ish boshida tekshirilib lockfilega mahkamlanadi. Ushbu reja aniq patch versiyani majburlamaydi. Flowbite React React + Tailwind komponent kutubxonasi sifatida ishlatiladi: [rasmiy hujjat](https://flowbite-react.com/docs/getting-started/introduction).

## 3. Rollar va ruxsatlar

| Amal | DEV / root | DIRECTOR | ADMIN |
|---|---|---|---|
| Bemor va kalendarni ko‘rish | Ha | Ha | Ha |
| Qayta aloqa, izoh, bron, ko‘chirish | Ha | Ha | Ha |
| O‘ziga biriktirilgan bemor bilan ishlash | Ha | Ha | Ha |
| Boshqa xodimdan majburan olib berish | Ha | Ha | Yo‘q |
| Tashrifni yakunlash / kelmadi belgilash | Ha | Ha | Ha, biriktirilgan murojaatda |
| Yakunlangan tashrifni tuzatish | Ha, sabab bilan | Ha, sabab bilan | Yo‘q |
| To‘liq dashboard va UTM hisobot | Ha | Ha | Yo‘q |
| O‘z ish ko‘rsatkichlari | Ha | Ha | Ha |
| Bot tokeni, matn, ish vaqti, klinika | Ha | Ha | Yo‘q |
| UTM link yaratish/arxivlash | Ha | Ha | Yo‘q |
| ADMIN taklif qilish/bloklash | Ha | Ha | Yo‘q |
| DIRECTOR taklif qilish/bloklash | Ha | Yo‘q | Yo‘q |
| Ommaviy eksport, audit | Ha | Ha | Yo‘q |
| Root tokenini o‘zgartirish | Faqat ENV/operator | Yo‘q | Yo‘q |

Ruxsatlar har bir API endpoint va obyekt uchun backendda tekshiriladi. UI tugmasini yashirish xavfsizlik hisoblanmaydi. Role qiymati frontend yuborgan ma’lumotdan ishonchli olinmaydi. Xodim bloklansa barcha sessiyalari bekor qilinadi, pending loginlar ishlamaydi. Uning ochiq murojaatlari navbatga qaytariladi; tarixdagi actor_id saqlanadi.

Xodim telefonni ko‘rish uchun “Qayta aloqa”ni bosishi shart: ro‘yxatda telefon maskalanadi. Kartochkada mavjud operator mas’ulligi tekshiriladi; director/dev zaruratda ko‘ra oladi. Kontakt ochilganligi audit qilinadi. Bemorlar umumiy ro‘yxati adminlarga ko‘rinadi, ammo boshqa admin biriktirilgan bemorning ish holatini yashirin o‘zgartira olmaydi.

## 4. Xodim taklifi va login — ikkita mustaqil oqim

### 4.1. Dastlabki sozlash

1. Dev HTTPS paneldagi root login formasiga ENVdagi `ADMIN_TOKEN`ni kiritadi.
2. Backend constant-time taqqoslash va rate limitdan keyin qisqa muddatli root session yaratadi.
3. Token URL, query string, frontend bundle, localStorage yoki logga yozilmaydi.
4. Dev bot tokenini kiritadi, `getMe` orqali tekshiradi, bot identity va username ko‘rsatiladi.
5. Bot ulangach dev director uchun taklif yaratadi. Bot ishlamasa root login ishlashda davom etadi.

`ADMIN_TOKEN` kamida 32 random byte kuchiga ega bo‘lsin; root session tavsiya etilgan muddati 1 soat. Token rotatsiyasida oldingi root sessiyalar ham bekor qilinadi. Normal ish uchun har bir xodim alohida hisobdan foydalansin.

### 4.2. QR orqali xodim registratsiyasi

1. Dev director/admin, director faqat admin roliga taklif yaratadi.
2. Backend kriptografik random token yaratadi; DBda hash, rol, yaratuvchi, expiry saqlanadi.
3. QR: `https://t.me/<bot_username>?start=invite_<opaque_token>`.
4. Taklif 24 soat amal qiladi; bir marta ishlatiladi; bekor qilish va qayta yaratish mumkin.
5. Telegram bot `from.id`ni oladi, ism familiyani tasdiqlatadi, so‘rovni `pending_approval`ga o‘tkazadi.
6. Taklif yaratuvchi panelda aynan qaysi Telegram ID/ism kelganini ko‘rib tasdiqlaydi. QR boshqa odamga tarqalsa avtomatik xodim bo‘lib qolmasin.
7. Tasdiqlangach staff active bo‘ladi. Active bo‘lmagan xodim login qila olmaydi.

Taklifni egallash/consume atomik bo‘ladi. Bir token bilan ikki hisob ochilmaydi. Telegram username identifikator emas, o‘zgarishi mumkin. Staff onboarding bemor registratsiyasiga tushmaydi va UTM analitikaga qo‘shilmaydi.

### 4.3. Panelga login

1. Brauzer login challenge so‘raydi. Backend 2 daqiqalik token va brauzerga bog‘liq alohida HttpOnly cookie yaratadi.
2. QR/deeplink: `...start=login_<opaque_token>`; unda root token ham, tayyor session ham yo‘q.
3. Bot active xodimga qurilma/vaqt va moslashtirish kodi bilan “Panelga kirishni tasdiqlaysizmi?” beradi.
4. Xodim tasdiqlaydi. “Men boshlamaganman” orqali rad qilish mumkin; kutilmagan kirishni tasdiqlamaslik ogohlantiriladi.
5. Faqat challenge yaratilgan brauzer o‘z cookie isboti bilan natijani oladi; bir marta atomik exchange orqali login session yaratiladi.
6. Boshqa brauzerning faqat QR tokenini bilishi sessiya olish uchun yetarli emas. Takror exchange, expiry va bekor qilingan token rad etiladi.

Cookie: Secure, HttpOnly, SameSite, mutatsiyalarda CSRF/Origin nazorati. Xodim session default 8 soat, idle timeout 30 daqiqa. Har API so‘rovida session revoke va staff active holati tekshirilsin. Root, invite, login, UTM tokenlari alohida namespace va jadvallarda.

Telegram start parametri 64 belgigacha: uzun UTM JSONni linkka joylash o‘rniga qisqa opaque kod ishlatilsin. [Telegram deep linking](https://core.telegram.org/bots/features#deep-linking).

## 5. Bemor bot oqimi

### 5.1. FSM va registratsiya tranzaksiyasi

`START → CONSENT → WAIT_FULL_NAME → WAIT_PHONE → REGISTERED → OPTIONAL_REASON → FINISHED`

1. Bot faqat private chatda registratsiya qiladi.
2. `/start`da attribution kodini tekshiradi, registratsiya draftini ochadi yoki mavjudini davom ettiradi.
3. Qisqa maxfiylik/ma’lumotdan foydalanish matni va “Roziman, davom etish” beriladi. Rad etsa registratsiya ochilmaydi.
4. Ism familiya bitta string sifatida olinadi, trim va ortiqcha bo‘shliqlar normalizatsiyasi. 2–120 belgi; lotin/kirill/apostrof/defisni qabul qilish; aynan ikki so‘z sharti bo‘lmasin.
5. Telefon “Telefon raqamimni yuborish” contact tugmasi yoki matn orqali olinadi.
6. Ism+telefon valid bo‘lgach bitta DB tranzaksiyasida patient upsert, inquiry yaratish, consent qaydi, attribution snapshot va notification outbox yoziladi. `registered_at` shu vaqt.
7. Commit muvaffaqiyatidan keyin: “Ro‘yxatdan o‘tdingiz. Konsultatsiya olish maqsadingizni qisqacha yozing. Bu ixtiyoriy.” Tugma: **Shart emas**.
8. Sabab 1–1000 belgili plain text; kiritsa o‘sha inquiryga qo‘shiladi, skip bossa bo‘sh qoladi.
9. Yakun: **“Ma’lumotlaringizni oldik. Mutaxassislarimiz siz bilan tez orada bog‘lanadi.”**

Muhim: 7-qadamdan keyin foydalanuvchi chiqib ketsa ham bazada to‘liq registratsiya va yangi murojaat mavjud. Optional bosqich 24 soatda avtomatik yopiladi; ma’lumot o‘chmaydi. Yakun xabari skip/izohdan keyin yoki timeout job orqali yuboriladi; timeoutdagi Telegram xabari yetkazilmasa ham registratsiya saqlanadi. Timeoutdan keyin bemor menyudagi “Izoh qo‘shish”dan foydalanishi mumkin.

### 5.2. Telefon normalizatsiyasi

| Kirish | Bazadagi qiymat |
|---|---|
| `99 000 11 22` | `+998990001122` |
| `990001122` | `+998990001122` |
| `998 99 000 11 22` | `+998990001122` |
| `+998 (99) 000-11-22` | `+998990001122` |
| Yetishmayotgan raqam, harf, boshqa davlat kodi | Xato xabari; qayta kiritish |

Faqat belgilangan separatorlarni tozalash; harflarni shunchaki olib tashlab “valid” qilib yubormaslik. 9 raqam bo‘lsa 998 prefiksi, 12 raqam bo‘lsa 998dan boshlanishi shart. Strukturaviy validatsiya raqamning haqiqatan bemorniki ekanini isbotlamaydi. Manual raqam `phone_source=manual`, `verified=false`; SMS OTP V1ga kirmaydi. Contact `user_id == from.id` bo‘lsagina “o‘z Telegram kontakti” deb belgilanadi, bu ham klinik shaxs tasdig‘i emas. Begona kontakt yuborilsa rad etib o‘z kontaktini yoki qo‘lda raqam kiritishni so‘rash.

### 5.3. Qayta start, dublikatlar va yangilash

- Patient uchun `telegram_user_id` unique. Telefon shared bo‘lishi mumkin; unga qarab bemorlarni avtomatik birlashtirmang.
- Bir xil telefonli turli Telegram hisoblar “Ehtimoliy dublikat” sifatida director ko‘rib chiqishi uchun belgilanadi.
- Bir patient + doctor uchun bittadan ortiq ochiq inquiry yo‘q, DB partial unique bilan himoyalanadi.
- Ochiq murojaatda qayta `/start` yangi registratsiya yaratmaydi. “Murojaatingiz qabul qilingan” va ma’lumotni yangilash menyusi chiqadi.
- Oldingi murojaat yopilgan bo‘lsa “Yangi konsultatsiya uchun murojaat” tasdig‘i bilan yangi inquiry ochiladi; avvalgi qabul tarixi saqlanadi.
- Birinchi ro‘yxatdan o‘tish sanasi va har bir yangi inquiry sanasi alohida. Sababni o‘zgartirish tarixda yoziladi.
- Patientdagi telefon/ism yangilanishi eski inquiry va qabul varaqasi snapshotlarini yashirin o‘zgartirmaydi; ochiq murojaat kontaktini alohida tasdiq bilan yangilash mumkin.
- `/cancel` draftni bekor qiladi, commit qilingan murojaatni o‘chirmaydi. Ishlamay qolgan draftlar 24 soat saqlanadi; undan so‘ng minimal texnik event qolib draft PII tozalanadi.
- Foto/audio o‘rniga matn so‘raladi. Limit va noto‘g‘ri formatda foydalanuvchiga tushunarli xabar beriladi.

## 6. Murojaat, qayta aloqa va tashrif holatlari

**Bitta statusga hamma ma’noni yuklamang.** Inquiry lifecycle, contact natijasi, operator mas’ulligi va appointment holati alohida.

### 6.1. Murojaat lifecycle

`open → closed`, `closed → open` faqat director/dev sabab bilan. Yopish sabablari: `attended`, `declined`, `unreachable`, `duplicate`, `cancelled`, `other`. `unreachable` kamida 3 ta javobsiz urinishdan keyin taklif qilinadi, avtomatik yopilmaydi. Director sabab bilan istisno qilishi mumkin.

### 6.2. Qayta aloqa urinishlari

Har bir urinish alohida `contact_attempt`:

| Holat | Ma’nosi |
|---|---|
| `in_progress` | Tugma bosildi, natija hali kiritilmagan |
| `answered` | Xodim bemor javob berganini belgiladi |
| `no_answer` | Javob bermadi |
| `busy` | Band |
| `unreachable` | Aloqa qilib bo‘lmadi |
| `wrong_number` | Noto‘g‘ri raqam |
| `aborted` | Xodim urinishni boshladi, lekin qo‘ng‘iroq qilmaganini bildirdi |
| `interrupted` | Tugallanmagan urinish lease/time limitdan keyin tiklashga muhtoj |

“Qayta aloqa” bosilishi real telefon tarmog‘i qo‘ng‘irog‘ini tasdiqlamaydi. `started_at` tugma vaqti; `answered_at` faqat xodim answered tanlaganda; avtomatik qo‘ng‘iroq integratsiyasi yo‘q. Xodim yakunlashda suhbat izohi yozadi; answered uchun izoh talab qilinadi, javobsiz natija uchun qisqa izoh ixtiyoriy.

Answered bo‘lib vaqt belgilanmasa “Javob berdi — qabul belgilanmagan” filtri. Keyingi qo‘ng‘iroq javobsiz bo‘lsa avval javob berganlik tarixi yo‘qolmaydi. `ever_answered`, `last_contact_outcome`, `last_attempt_at` alohida hisoblanadi.

### 6.3. Xodimlar to‘qnashuvini oldini olish

1. “Qayta aloqa” bitta tranzaksiyada `assigned_to`, attempt va shu kunning varaqasini yaratadi.
2. Murojaat biriktirilmagan yoki o‘ziniki bo‘lsagina admin boshlay oladi. Boshqa admin 409 conflict va mas’ul xodim nomini oladi.
3. Bitta inquiryda faqat bitta `in_progress` attempt bo‘lsin; ikki marta bosish idempotency key bilan bitta attemptga qaytsin.
4. Mas’ul xodim biriktirilishi doimiy; urinishning 30 daqiqalik lease’i tugashi mas’ulni avtomatik almashtirmaydi.
5. Lease tugasa attempt `interrupted`; foydalanuvchi natijani aniqlashtiradi. Tizim uni javobsiz deb taxmin qilmaydi.
6. Director/dev reassign qiladi; admin o‘zinikini sabab bilan navbatga qaytarishi mumkin. Har biri auditda.
7. Qayta qo‘ng‘iroq vaqti `next_followup_at`; band/javobsiz/vaqt belgilanmagan uchun xodim tanlaydi. Muddati o‘tganlari alohida navbat.

### 6.4. Appointment holatlari

`scheduled → checked_in → completed`

`scheduled → cancelled` yoki `scheduled → no_show`.

- `checked_in` — keldi; `completed` — qabul tugadi.
- `no_show` faqat scheduled boshlanishi + default 30 daqiqa o‘tgach xodim tasdiqlaydi. Ungacha “Natija kutilmoqda”.
- Vaqti o‘tgan, ammo belgilab chiqilmagan scheduled tashriflar `outcome_pending` ko‘rinishi orqali chiqariladi; bu alohida persistent status bo‘lishi shart emas.
- Xodim xato belgilasa director/dev sabab bilan correction event qiladi. Tarix o‘chirilmaydi.
- `completed`da inquiry `closed/attended`; bitta tranzaksiya.
- `cancelled/no_show`da inquiry avtomatik yopilmaydi; qayta yozish yoki aloqa navbatiga qaytadi. Admin “Boshqa qabul kerak emas” bo‘lsa alohida yopadi.
- Slot vaqtini ko‘chirish scheduled appointmentning IDsi saqlangan holda bajariladi va reschedule event yoziladi. No-showdan keyingi bron yangi appointment, eski no-show hisoboti saqlanadi.
- Bitta inquiryda bittadan ortiq faol `scheduled/checked_in` appointment mumkin emas.

## 7. Ish vaqti va 15 daqiqalik kalendar

### 7.1. Sozlamalar

Director/dev haftaning har kuni uchun bir yoki bir nechta interval belgilaydi: masalan 09:00–13:00 va 14:00–18:00. Intervaldan tashqari vaqt tanaffus hisoblanadi. Sana bo‘yicha istisnolar: dam olish, maxsus ish vaqti, qisman band blok.

- Haftalik jadvalga `effective_from` bilan yangi versiya beriladi; tarix qayta yozilmaydi.
- Sana istisnosi shu kunning haftalik jadvalini almashtiradi, ustiga qo‘shib yubormaydi.
- Start/end 15 daqiqa gridda: 00, 15, 30, 45; end > start; kunlararo interval V1da yo‘q.
- Slot `[start, end)` ko‘rinishida: 09:00–09:15 va 09:15–09:30 yonma-yon bo‘lishi mumkin.
- 09:00–13:00 — 16 slot. 09:00–13:00 va 14:00–18:00 — 32 slot. 31 band va 1 bloklangan bo‘lsa 0 bo‘sh.
- O‘tgan vaqtga yangi bron yo‘q; default bron ufqi 90 kun, director/dev sozlaydi.
- Klinik manzil, yo‘l ko‘rsatma, aloqa raqami va doktor nomi konfiguratsiyada.
- Ish vaqti kiritilmaguncha kalendar “Jadval sozlanmagan”, bron o‘chirilgan. Soxta jadval productionga seed qilinmaydi.

### 7.2. Bron tranzaksiyasi va baza kafolati

1. Klient bo‘sh slotlarni serverdan oladi, bu faqat joriy ko‘rinish.
2. Save/reschedule paytida backend actor, inquiry, jadval, exception, block, kelajak va durationni qaytadan tekshiradi.
3. Bron, ko‘chirish, bekor qilish va jadval/block o‘zgarishlari doctor row lockni bir xil tartibda oladi. V1 bitta shifokor uchun bu sodda va yetarli; keyin doctor/day lockka o‘tkazish mumkin.
4. PostgreSQLda `tstzrange(start_at,end_at,'[)')` + GiST exclusion orqali bir doctorning bekor qilinmagan appointmentlari overlap qilmasin. `btree_gist` migratsiya/prerequisite sifatida.
5. `end_at = start_at + interval '15 minutes'` constraint; inquiry bo‘yicha active appointment partial unique.
6. DB overlap xatosi 500 emas, `409 SLOT_TAKEN`; UI yangi slotlarni olib “Bu vaqt hozirgina band qilindi” deydi.
7. Appointment, event, varaqaga bog‘lanish va notification outbox bitta tranzaksiyada commit qilinadi.

Faqat frontenddagi “bo‘shmi?” tekshiruvi yetarli emas. PostgreSQL range exclusion qo‘llashi mumkin: [rasmiy range constraints](https://www.postgresql.org/docs/current/rangetypes.html#RANGETYPES-CONSTRAINT).

### 7.3. Ish vaqti o‘zgarganda

Yangi jadval/block mavjud kelajak qabullariga zid kelsa backend `409 SCHEDULE_CONFLICT` va to‘qnashgan qabullar ro‘yxatini beradi. Avval ularni ko‘chirish/bekor qilish kerak; admin ularni saqlagan holda jadvalni yashirin toraytira olmaydi. Tarixdagi qabul va completed/no-show yozuvlari o‘zgarmaydi. “Kun to‘liq band”ni director/root ham overbooking bilan chetlab o‘tolmaydi; zarur bo‘lsa ish vaqti qonuniy kengaytiriladi.

### 7.4. UI

Kun, hafta, oy va mobil agenda ko‘rinishi. Oy katagida jami yozilgan, bo‘sh, kelgan, kelmagan sonlar. Kundagi 15 daqiqalik gridda bo‘sh slotga bosib joylash; bemor kartasidan vaqt tanlash ham mavjud. Drag-and-drop ikkilamchi qulaylik: ko‘chirish dialogida eski/yangi vaqt ko‘rinadi, tasdiqdan keyingina save. Klaviatura/mobil uchun dialog alternativasi majburiy. Optimistic move xatoda rollback qilinadi.

## 8. Qabul varaqasi va tarix

Varaqani appointment yaratilguncha kutmang: birinchi “Qayta aloqa” shu kun varaqasini yaratadi.

Unique: `(inquiry_id, local_contact_date)`. Bir kunda uchta urinish — bitta varaqa ichida uchta qator. Ertasi kuni qayta aloqa — yangi varaqa; hammasi bitta bemor timeline’ida.

Varaqada quyidagilar:

- Barqaror raqam: `RU-YYYYMMDD-<unique suffix>`, inquiry va patient ID.
- Ism familiya, telefon, Telegram ID/username — kontakt snapshot.
- Registratsiya sanasi, sabab, shu murojaatning UTM manbasi.
- Har urinish boshlangan, natija yozilgan va javob qayd etilgan vaqt; xodim va natija.
- Suhbat izohi, keyingi aloqa vaqti, appointment va ko‘chirish tarixi.
- Qabul sanasi/soati, kelgan/kelmagan/yakunlangan holati.
- Varaqani yaratgan xodim, yaratilgan va so‘nggi tahrir vaqti.

Izohlar append-only; xato izoh o‘rniga yangi revision va sabab; oldingi versiya auditdan o‘chmasin. Varaqada original snapshot va yangilangan kontakt aniq ajratiladi. Appointment boshqa kuni, yangi qo‘ng‘iroqsiz yaratilsa shu inquiryning oxirgi varaqasiga bog‘lanadi; varaqa hali bo‘lmasa avval contact workflow bajariladi. `answered` urinish bo‘lmaguncha bron qo‘yilmaydi; noto‘g‘ri raqam/no-answer turib qabul yozish yo‘q.

UIda o‘qish va A4 print stylesheet bo‘lsin; brauzerdan PDFga chiqarish mumkin. Server PDF renderer V1 uchun shart emas. Print ham ruxsat va auditdan o‘tadi; umumiy ochiq PDF URL yaratilmaydi. Bosma chiqishda vaqt zonasi yoziladi.

## 9. UTM va direktor dashboardi

### 9.1. Linklar va attribution

Director/dev kampaniya nomi, `utm_source`, `utm_medium`, `utm_campaign`, ixtiyoriy `utm_content`, `utm_term` kiritadi. Backend qisqa kod beradi: `...start=src_<code>`; copy va QR mavjud.

- Telegram bot link bosilganini emas, `/start` update kelganini biladi. Dashboard “Botni boshlashlar” deydi, “kliklar” demaydi.
- Link clicks zarur bo‘lsa alohida HTTP redirect tracking keyingi bosqich; V1ga qo‘shilmaydi.
- Draft boshlangan source shu inquiry uchun muzlatiladi. Draft davomida boshqa kampaniyadan kirish touch event bo‘lib saqlanadi, attributionni almashtirmaydi.
- Patient lifetime `first_source` va `last_touch_source`, inquiry `registration_source` alohida.
- UTM bo‘lmasa `organic`, tanilmagan kod `unknown`; ikkalasi bitta emas.
- Qayta `/start`dan registratsiya ko‘paymaydi. Keyingi yopilgan murojaatdan so‘ng yangi inquiry o‘z source snapshotiga ega.
- Kampaniyani arxivlash eski linkni organikka aylantirmaydi; mavjud kod attributionni saqlaydi, yangi kampaniya sifatida tanlashdan olib tashlanadi. Butunlay revoke qilingan kod fallback oqim va alohida revoked source belgisiga ega.
- Kampaniya nomini tahrirlash tarixiy UTM snapshotni o‘zgartirmaydi.

### 9.2. Metrikalarning aniq ta’rifi

| Ko‘rsatkich | Hisoblash |
|---|---|
| Yangi bemorlar | Patient first_registered_at tanlangan oraliqda |
| Registratsiyalar / murojaatlar | Inquiry registered_at tanlangan oraliqda; repeat alohida |
| Botni boshlaganlar | UTM start event; jami va unique Telegram user alohida |
| Hali aloqa boshlanmagan | Shu cohortda hech qanday attempt yo‘q va inquiry open |
| Aloqa boshlangan | Shu cohortda kamida bitta attempt bor |
| Javob bergan | Shu cohortda kamida bitta answered attempt bor |
| Javob berdi, yozilmadi | Ever answered, active appointment yo‘q, inquiry open |
| Qabulga yozilgan | Shu cohortda kamida bitta appointment yaratilgan; distinct inquiry |
| Hozir qabul kutilmoqda | Scheduled/checked_in active appointment mavjud |
| Qayta aloqa kutilmoqda | Open, followup_at kelgan/o‘tgan, active appointment yo‘q |
| Birinchi aloqa tezligi | First attempt.started_at − inquiry.registered_at; median va p90 |
| Kelmaganlar | Appointment start sanasi intervalda va status no_show |
| No-show foizi | no_show / (completed + checked_in + no_show); denominator 0 bo‘lsa “—” |

“Javob berildi” o‘rniga **“Bemor javob berdi”** va **“Aloqa boshlandi”** alohida yozilsin. Tugma bosilgani answeredga kirmaydi. Funnel kartalari bir-birini qoplaydi, ularni qo‘shib jami sifatida ko‘rsatmaslik.

Ikkita hisobot rejimi:

1. **Registratsiya cohorti:** davrda registratsiya qilingan inquirylarning bugungacha natijalari. UTM konversiyasi shu cohort bo‘yicha; o‘tgan davr natijalari keyingi aloqalardan yangilanishi mumkinligi yoziladi.
2. **Operatsion faoliyat:** tanlangan davrda bosilgan qo‘ng‘iroqlar, answered natijalar, appointment sanasidagi tashriflar. Cohort bilan aralashtirilmaydi.

Bugun, kecha, oxirgi 7 kun, joriy hafta, oy va custom filter. Haftaning boshi dushanba. Dinamika kunlik; ma’lumotsiz kunlar 0. UTM jadvali, operator samaradorligi, no-show va muddati o‘tgan follow-up drill-down. Joriy qisman kun/hafta/oyni oldingi to‘liq davr bilan teng deb ko‘rsatmaslik; bir xil elapsed period yoki taqqoslash izohi.

No-show hisobotida bemor, telefon, operator, qabul vaqti, UTM, qayta aloqa holati, qayta yozilganmi va sabab. Cancelled va natijasi kiritilmaganlar no-showga kirmaydi; alohida son ko‘rsatiladi.

## 10. Vaqt zonasi

- DB event va appointment instantlari `timestamptz`; server va joblar UTC instantlar bilan ishlaydi.
- Biznes zona doim `Asia/Tashkent`; browser yoki OS zonasi boshqacha bo‘lsa ham kalendar Toshkent vaqtida.
- UI sanadan vaqt yaratishda timezone-aware konvertatsiya, qo‘lda `+5 soat` hisoblash yo‘q.
- Ish jadvali `weekday + local time`, istisno `local date`; appointment UTC instant.
- Sana filteri `[Toshkent 00:00, keyingi kun 00:00)`dan UTCga o‘giriladi. Misol: 2026-08-26 kuni UTCda 2026-08-25 19:00 dan 2026-08-26 19:00 gacha.
- Varaqaning local_contact_date qiymati attempt.started_atdan Asia/Tashkentda olinadi, browser yuborgan sana emas.
- Yarim tundan oldin boshlangan, keyin yakunlangan attempt boshlanish kunining varaqasida qoladi.
- API ISO 8601 `Z`/offset format, kalendar headerida “Toshkent vaqti · UTC+5”.

## 11. Sozlamalar va bot tokeni

Sozlanadiganlar: klinika/doktor ma’lumotlari, ish haftasi/istisno, matnlar va tugma label’lari, UTM, xodimlar, bildirishnoma va reminder, bron ufqi, no-show grace, maxfiylik matni.

**Barcha funksional matnlar uchun kalitli katalog:** welcome, consent, full_name_prompt, phone_prompt, phone_error, registered, reason_prompt, skip_reason, finished, already_registered, appointment_confirmation, rescheduled, cancelled, reminder, generic_error. Bot komandalarining protokol nomi va xavfsizlik/DB invariantlari erkin matn emas.

Editor: draft → preview/test → publish; version, kim o‘zgartirgani va rollback. Faqat allowlist placeholderlar: `{full_name}`, `{doctor_name}`, `{date}`, `{time}`, `{clinic_address}`. Python/Jinja kabi erkin kod ishlatish yo‘q; HTML escape, Telegram uzunlik cheklovi va bo‘sh matn validatsiyasi. Label o‘zgarishi callback action IDni buzmasin. Registratsiya drafti boshlanganda template version pin qilinadi.

Token oqimi:

1. Backend getMe bilan tekshiradi, foydalanuvchiga bot username va IDni ko‘rsatadi.
2. Token app encryption key bilan shifrlanib DBga yoziladi; key faqat secret ENVda. Panel tokenni qayta to‘liq o‘qiy olmaydi.
3. Webhook uchun alohida random path va `secret_token`; Telegram header tekshiriladi. Token URLga kiritilmaydi. [aiogram webhook hujjati](https://docs.aiogram.dev/en/latest/dispatcher/webhook.html).
4. Holatlar: not_configured, connecting, connected, error, reconnect_required. So‘nggi update, webhook health va tozalangan xato.
5. Bir botning token rotatsiyasi va boshqa botga o‘tish alohida. Boshqa bot ID bo‘lsa oddiy “Save” bilan almashtirmaslik; maxsus tasdiq/reconnect oqimi.
6. Boshqa botga o‘tganda eski deeplinklar yangilanadi; foydalanuvchi yangi botni boshlamaguncha unga xabar yuborib bo‘lmasligi ko‘rsatiladi. Tarixiy bot_id saqlanadi.
7. Ulanish muvaffaqiyatsiz bo‘lsa oldingi konfiguratsiya sababsiz yo‘qotilmaydi; token allaqachon revoked bo‘lsa bu ochiq error sifatida ko‘rsatiladi. Eski/new bot clientlari va webhook almashuvi boshqariladigan supervisor orqali.

## 12. Bildirishnomalar

Admin panel yangi murojaatlarni 15 soniyalik polling bilan oladi; V1 WebSocket majburiy emas. Director/adminning Telegram xabarida default faqat “Yangi murojaat #ID” va himoyalangan panel havolasi — konsultatsiya sababi va to‘liq kontakt guruhlarga yuborilmaydi.

Bemor uchun: bron tasdig‘i, ko‘chirish, bekor qilish; 24 soat va 2 soat oldingi reminder konfiguratsiya orqali, default yoqilgan. Belgilangan paytda reminder vaqti o‘tgan bo‘lsa yuborilmaydi. Worker kechikib kelsa qabul boshlanganidan keyin reminder tashlamaydi.

Outbox key `(appointment_id, schedule_version, notification_type)`; rescheduled/cancelled bo‘lsa eski joblar invalid qilinadi, yuborishdan oldin joriy versiya/status tekshiriladi. Telegram 429da retry_after, network xatoda exponential backoff; blocked userda delivery_failed va panel belgisi. Telegram tashqi side effectlarida mutlaq exactly-once va’da qilinmaydi: yuborishdan keyin process o‘lsa kamdan-kam dublikat xabar bo‘lishi mumkin, ammo registratsiya yoki bron dublikat bo‘lmasligi shart.

## 13. Ma’lumotlar modeli

Har jadvalda zarur created_at/updated_at, FK va indekslar; PII kerak bo‘lmagan joyga ko‘chirilmaydi.

| Jadval | Asosiy ustunlar |
|---|---|
| staff_users | id, telegram_user_id unique, full_name, role, state, invited_by |
| staff_invites | token_hash unique, role, issuer_id, claimed_by, expires_at, approved_at, revoked_at |
| auth_challenges | token_hash, browser_binding_hash, telegram_user_id, state, expires_at, consumed_at |
| sessions | token_hash, staff_id yoki root principal, auth_epoch, expires_at, last_seen_at, revoked_at |
| patients | id, telegram_user_id unique bigint, full_name, phone_e164, phone_source, first_registered_at |
| registration_drafts | bot_id, telegram_user_id, step, data, attribution_id, template_version, expires_at |
| consents | patient_id/draft_reference, version, accepted_at, purpose |
| inquiries | patient_id, doctor_id, status, close_reason, assigned_to, reason, contact_snapshot, registered_at, source_snapshot, next_followup_at, version |
| contact_attempts | inquiry_id, actor_id, outcome, started_at, answered_at, ended_at, lease_until |
| contact_notes | attempt_id, author_id, text, previous_revision_id, created_at |
| reception_sheets | inquiry_id, local_contact_date, number unique, contact_snapshot, created_by |
| sheet_attempts | sheet_id, attempt_id unique |
| doctors | id, name, timezone, active |
| work_schedule_versions | doctor_id, effective_from, weekly_intervals, created_by |
| day_overrides | doctor_id, local_date, intervals yoki closed |
| schedule_blocks | doctor_id, start_at, end_at, reason |
| appointments | inquiry_id, doctor_id, sheet_id, start_at, end_at, status, created_by, schedule_version, version |
| appointment_events | appointment_id, action, old/new time/status, reason, actor_id, created_at |
| campaigns | code unique, name, utm_fields, archived_at, revoked_at |
| attribution_events | bot_id, telegram_user_id, campaign_id, event_type, occurred_at |
| bot_connections | bot_id, username, encrypted_token, config_version, status |
| bot_chat_bindings | bot_id, telegram_user_id, chat_id, reachable, last_seen_at |
| settings_versions | namespace, payload, version, published_at, actor_id |
| telegram_inbox | bot_id, update_id unique per bot, payload, state, attempts, lease_until |
| outbox_jobs | idempotency_key unique, kind, entity_id, version, due_at, state, lease_until, attempts |
| idempotency_records | actor, route, key, request_hash, response_reference, expires_at |
| audit_events | actor principal, action, entity, redacted diff, request_id, occurred_at |

Indekslar: inquiry status/registered_at, assigned_to/status, next_followup_at; contact inquiry/started_at; appointment doctor/start_at/status; normalized phone search; campaign/date; inbox/outbox state/due_at. Offset pagination kichik hajm uchun mumkin, katta ro‘yxatlarda cursor; server pagination default 25, max 100. Telefon va ism qidiruvi serverda, injectiondan himoyalangan.

Qabulga qo‘yilgan vaqt va ish jadvali mosligi cross-table bo‘lgani uchun SQL CHECKning o‘zi yetmaydi: domain service + bir xil locking protokoli majburiy. Overlap esa qo‘shimcha DB exclusion bilan himoyalanadi.

## 14. API kontraktlari

| Guruh | Endpointlar namunasi |
|---|---|
| Auth | POST /auth/root, POST /auth/challenges, GET /auth/challenges/current, POST /auth/exchange, POST /auth/logout, GET /auth/me |
| Staff | GET /staff, POST /staff/invites, POST /staff/invites/{id}/approve, POST /staff/{id}/deactivate |
| Patients | GET /patients, GET /patients/{id}, PATCH /patients/{id} |
| Inquiries | GET /inquiries, GET /inquiries/{id}, POST /inquiries/{id}/assign, POST /inquiries/{id}/close |
| Contact | POST /inquiries/{id}/contact-attempts, POST /contact-attempts/{id}/finish, POST /contact-attempts/{id}/notes |
| Calendar | GET /calendar/availability, GET /appointments, POST /appointments, POST /appointments/{id}/reschedule, POST /appointments/{id}/transition |
| Sheets | GET /reception-sheets/{id}, GET /reception-sheets/{id}/print-data |
| Dashboard | GET /analytics/cohort, GET /analytics/activity, GET /reports/no-shows |
| Settings | GET/PATCH /settings, POST /settings/publish, POST /bot-connection/validate, POST /bot-connection/connect |
| Schedule | GET/POST /schedule/versions, PUT /schedule/day-overrides/{date}, POST /schedule/blocks |
| Campaign | GET/POST /campaigns, POST /campaigns/{id}/archive |
| Telegram | POST /telegram/webhook/{opaque_path} |

Auth kerakli endpointlarda session + role/object scope. State-changing so‘rovlarda Idempotency-Key; bir key boshqa payload bilan ishlatilsa 409. PATCH va transitionlarda version/If-Match; stale edit 409 VERSION_CONFLICT. Standart xato `{code, message, field_errors, request_id}`; 401/403/404/409/422/429 farqlansin. Hech bir GET biznes holatini o‘zgartirmasin. Client validation backend validation o‘rnini bosmaydi.

## 15. UI tuzilishi va Flowbite bo‘yicha Codex talabi

### 15.1. Uch bo‘lim

**Boshqaruv:** director/dev uchun KPI, funnel, UTM, dinamika, operatorlar, no-show. Admin uchun bugungi qabullar va o‘z vazifalari; global marketing ko‘rsatkichlari ko‘rsatilmaydi.

**Bemorlar:** Registratsiyalar / Kalendar / Qabul varaqalari tablari. Registratsiya jadvali + filterlar + detail drawer. Kartochkada kontakt, sabab, status, mas’ul, timeline, qayta aloqa, bron va tarix. Loading, empty, error, forbidden va conflict holatlari to‘liq.

**Sozlamalar:** Bot va matnlar / Ish jadvali / Xodimlar / UTM / Klinika / Audit. Admin uchun bu bo‘lim yashiriladi; profil va logout headerda qoladi.

### 15.2. Dizayn kontrakti

- Oq content, och neytral fon, to‘q matn, bitta ko‘k yoki teal accent. Rang tanlovi boshlanishda bir marta belgilanib theme tokenlarda saqlanadi.
- Gradient, neon, glassmorphism, katta dekorativ soyalar va aralash icon pack yo‘q.
- Duotone talqini: asosiy rang va uning och tusi; status ranglari kam miqdorda semantik ishlatilishi mumkin, har doim yozuv/icon bilan.
- Bir xil sans-serif: Inter yoki litsenziyasi tekshirilgan lokal muqobil; 14–16px asosiy matn, aniq heading hierarchy.
- 8px spacing ritmi; ixcham table, 8–12px radius, 1px border, kamtar shadow.
- Faqat lucide-react icon; icon-only tugmada accessible label va tooltip.
- Flowbite komponentlari yagona theme va shared wrappers orqali: Button, Modal, Drawer, Table, Badge, Tabs, Select, TextInput, Toast, Pagination va boshqalar.
- Flowbite’da yo‘q to‘liq scheduling grid alohida React komponent bo‘ladi; mavjud bo‘lmagan Calendar API invent qilinmaydi.
- 1440/1024/768/390px ekranlarda tekshirish. Mobil kalendar agenda; keng table kontrolli horizontal scroll.
- Keyboard navigatsiya, focus ring, modal focus restore, kontrast, tushunarli form error va save/loading feedback majburiy.
- Demo UI bilan to‘xtamaslik: har ekranning real API, permissions va conflict holati bo‘lsin.

### 15.3. Flowbite skill deliverable rejasi

Implementatsiya boshlanishida `regurolog-flowbite-ui` nomli loyiha UI skillini tayyorlash alohida birinchi vazifa bo‘lsin. Bu hujjat skillning o‘zi yoki o‘rnatilganini bildirmaydi.

Skill tarkibi: qisqa SKILL.md (qachon qo‘llash, workflow, qat’iy cheklovlar); `references/design-tokens.md`, `references/component-patterns.md`, `references/states-and-accessibility.md`; kerak bo‘lsa tekshirilgan TSX namunalar. Hujjatga butun Flowbite docsni ko‘chirish o‘rniga loyiha versiyasi, ishlatiladigan API va lokal patternlarni saqlash.

Skill ish tartibi: mavjud theme/componentsni tekshirish → mos Flowbite komponentni tanlash → Lucide bilan ulash → server/form state → accessibility → breakpoint va real screenshot tekshiruvi. Theme chetlab o‘tilgan ranglar, gradientsiz talab, xato komponent API va loading/error yo‘qligini tekshiruvchi checklist. Skillni yaratish/o‘rnatish o‘sha Codex muhitining skill-creator va saqlash qoidalari orqali bajariladi; oddiy markdown fayl yozishning o‘zi “skill o‘rnatildi” degani emas.

## 16. Xavfsizlik, maxfiylik va ekspluatatsiya

- Konsultatsiya sababi sezgir: minimal yig‘ish, oddiy matn, ommaviy log/analytics/URLlarga chiqarmaslik. Botda hujjat/tahlil yuborishni so‘ramaslik.
- HTTPS, CORS allowlist, cookie/CSRF, endpoint rate limits, secret rotation, XSS escaping va parametrli query.
- Production request-body logging o‘chiriladi yoki PII maskalanadi; bot update raw payloadlari faqat qisqa operatsion TTL bilan. Takror update dedup markerlari payload tozalansa ham qoladi.
- Auditda token yoki to‘liq tibbiy izoh emas, obyekt/revision reference va redacted diff. Export/print/kontakt ochish ham auditlanadi.
- Eksport default faqat director/dev, imkon qadar minimal ustunlar, CSV formula injection himoyasi.
- Ma’lumotni saqlash muddati, o‘chirish/anonimlashtirish va rozilik matni klinika bilan tasdiqlanadigan release gate. Umumiy “abadiy saqlash” defaulti yo‘q.
- Productiondan oldin O‘zbekiston bo‘yicha hosting, shaxsiy/sezgir ma’lumot va Telegramdan foydalanishga oid amaldagi talablar alohida huquqiy tekshiruvdan o‘tsin. Ushbu texnik reja huquqiy muvofiqlikni tasdiqlamaydi.
- Xodimlar yozuvini hard delete qilish yo‘q, deactivate; bemor ma’lumotini o‘chirish maxsus tekshirilgan retention workflow orqali, audit/backup siyosati bilan birga.
- Har kuni shifrlangan backup; retention va egasi belgilansin; ishga tushirishdan oldin restore testi. Taklif etilgan maqsad: RPO 24 soat, RTO 4 soat; klinika tasdiqlaydi.
- Health/readiness: DB ulanishi, worker heartbeat, inbox/outbox kechikishi, bot webhook holati. Alertsda PII yo‘q.
- Migratsiya alohida deploy bosqichi; APIlarning har biri bir paytning o‘zida migration ishga tushirmaydi.
- `.env.example` faqat bo‘sh/soxta qiymatlar: DATABASE_URL, ADMIN_TOKEN, APP_ENCRYPTION_KEY, SESSION_SECRET, WEBHOOK_SECRET, PUBLIC_BASE_URL, timezone. Haqiqiy sirlar gitga kirmaydi.
- Seed faqat aniq synthetic bemorlar; productionda demo ma’lumot avtomatik yaratilmaydi.

## 17. Amalga oshirish bosqichlari

| Bosqich | Ish | Chiqish mezoni |
|---|---|---|
| 0. Kontrakt | Shu reja, qarorlar, API skeleton, Flowbite skill va design tokens | Status/role/timezone qoidalari yozilgan, skill alohida validatsiyalangan |
| 1. Poydevor | Monorepo, Railway native infra, DB, Alembic, CI, settings, root session | Noldan run, migration, root auth va health testlari o‘tgan |
| 2. Xodim/bot | Bot token config, webhook inbox, invite, approval, login/session revoke | QR bilan admin yaratiladi, o‘z brauzeriga kiradi, bloklash darhol ishlaydi |
| 3. Registratsiya | Consent, draft/FSM, phone, optional reason, UTM, dedup | Izohsiz ham inquiry mavjud, restart/takror update dublikat yaratmaydi |
| 4. CRM | Ro‘yxat/filter, assignment, contact attempts, notes, daily sheet, print | Ikki admin conflict, javobsiz/answered va varaqa senariylari o‘tgan |
| 5. Kalendar | Jadval, istisno, blocks, 15min availability, bron/reschedule | Parallel bron faqat bir marta, jadval conflict xavfsiz qaytadi |
| 6. Tashrif | Check-in, completed/no-show, correction, follow-up, reminders | Kelmagan hisobot, ko‘chirishda eski reminder bekor |
| 7. Analitika | Cohort/activity, UTM, dinamika, operator/no-show drill-down | Fixturelar bo‘yicha qo‘lda hisob bilan aniq mos |
| 8. Hardening | Security, responsive/accessibility, stress, backup/restore, runbook | Acceptance testlar o‘tgan, production gate tasdiqlangan |

Har bosqichda: kichik vertikal funksional bo‘lak → test → ishlaydigan UI/API → commit/checkpoint → bajarilgan/bajarilmagan ro‘yxat. Faqat backend yoki faqat bezak UI bilan yakunlangan deb belgilamaslik. Vaqt smetasini repo va deployment muhiti aniqlanmaguncha aniq va’da sifatida bermaslik.

## 18. Majburiy acceptance testlar

| ID | Senariy | Kutiladigan natija |
|---|---|---|
| REG-01 | Ism va `99 000 11 22`, keyin botdan chiqish | +998990001122 va bitta open inquiry saqlangan |
| REG-02 | Optional “Shart emas” | Registratsiya saqlanadi, yakun xabari chiqadi |
| REG-03 | Bir update 3 marta keladi | Bitta inquiry va bitta domain event |
| REG-04 | Ismdan keyin restart | Draftdan davom etadi |
| REG-05 | Ikki Telegram hisob bir telefon beradi | Ikki patient, dublikat flag; auto merge yo‘q |
| REG-06 | Ochiq inquiryga qayta /start | Yangi registratsiya soni oshmaydi |
| REG-07 | Yopilgan inquiry, yangi tasdiqlangan murojaat | Bitta patient, ikkita inquiry tarixi |
| AUTH-01 | Admin direct URLdan settings API chaqiradi | 403 |
| AUTH-02 | Director director invite yaratadi | 403 |
| AUTH-03 | QR taklifni ikki kishi consume qiladi | Faqat bir claim, approvalgacha hech kim active emas |
| AUTH-04 | Login QR boshqa brauzerga ko‘chiriladi | Browser binding yo‘qligi sabab session berilmaydi |
| AUTH-05 | Xodim bloklanadi | Oldingi session va pending challenge ishlamaydi |
| AUTH-06 | Expired/replayed invite yoki login | Rad etiladi, role escalation yo‘q |
| CALL-01 | Ikki admin bir inquiryga bir vaqtda bosadi | Bitta owner, bitta in_progress; ikkinchisiga 409 |
| CALL-02 | Tugma bosildi, natija kiritilmadi | Answered hisobiga kirmaydi |
| CALL-03 | No-answer, keyin answered | Ikkala urinish tarixda, ever_answered true |
| CALL-04 | Bir kunda 3, ertasi kuni 1 urinish | 2 varaqa, 4 urinish |
| CALL-05 | Lease tugashi | Interrupted, avtomatik no-answer emas |
| CAL-01 | Bir slotga 20 parallel real DB tranzaksiya | Aynan bitta bron; qolganlari 409 |
| CAL-02 | 09:00–09:15 va 09:15–09:30 | Ikkalasi mumkin |
| CAL-03 | 09:07 yoki tanaffusga bron | Validation xatosi |
| CAL-04 | Kun to‘la | Bo‘sh slot 0, dev ham overbook qilolmaydi |
| CAL-05 | Band slotga reschedule | Eski bron o‘z joyida, hech narsa yo‘qolmaydi |
| CAL-06 | Mavjud bron ustiga dam olish qo‘yish | 409 va conflict ro‘yxati |
| CAL-07 | Cancel va boshqa bron parallel | Yakuniy holat izchil, overlap yo‘q |
| CAL-08 | Jadval tahriri va bron parallel | Bir xil locking bilan conflict xavfsiz |
| TIME-01 | Toshkentda 23:59 va 00:01 registratsiya | Turli kun statistikasiga tushadi |
| TIME-02 | Brauzer New York zonasida | UI hamon Toshkent vaqtini ko‘rsatadi |
| VISIT-01 | Vaqt o‘tdi, hech kim status belgilamadi | Outcome pending, no-show hisobiga kirmaydi |
| VISIT-02 | No-showdan keyin qayta bron | Eski no-show saqlanadi, yangi appointment |
| MSG-01 | Bron commit, Telegram ishlamaydi | Bron saqlanadi, outbox retry |
| MSG-02 | Reschedule, eski reminder job qolgan | Eski versiya yuborilmaydi |
| UTM-01 | Bitta source orqali 3 /start, 1 registratsiya | Starts 3, unique 1, registratsiya 1 |
| UTM-02 | Linkni arxivlash/nomini almashtirish | Tarixiy attribution buzilmaydi |
| KPI-01 | Turli registratsiya va aloqa sanalari | Cohort/activity bir-biriga aralashmaydi |
| SEC-01 | Token yoki reasonni loglarda qidirish | Sir va sezgir matn yo‘q |
| OPS-01 | Toza DBga migratsiya va backup restore | Hisoblar va appointmentlar izchil tiklanadi |
| UI-01 | 390px va klaviatura bilan asosiy workflow | Registratsiya kartasi, aloqa, bron ishlaydi |

Integration testlar SQLite’da emas, PostgreSQLda bajariladi. Telegram tashqi API unit/integrationda mock qilinadi, stagingda test bot bilan real smoke test; production bemorlariga test xabar yuborilmaydi.

## 19. Codex uchun yakuniy ijro ko‘rsatmasi

Ushbu hujjatni RegUrolog uchun source of truth deb ol. Avval repo va mavjud AGENTS.mdni tekshir, keyin 0-bosqichdan bajar. Talablar bilan zid qaror chiqarma; xavfsizlik va biznes invariantlarini soddalashtirib tashlama. Muhitga bog‘liq versiyalarni rasmiy manbadan tekshir, lockfile yarat. Har bosqichda migratsiya, backend, frontend va meaningful testlarni birga yetkaz.

Mock ma’lumot bilan ishlaydigan maketni tayyor CRM deb ko‘rsatma. Test ishlatilmagan bo‘lsa “o‘tdi” dema. Ochiq savol chiqsa, foydalanuvchidan faqat scope/xavfsizlikka ta’sir qiladigan qarorni so‘ra; qolgan texnik qarorlarni ushbu rejaning defaultlari bilan bajar va decision logga yoz. Haqiqiy token, hosting, klinika ish jadvali, retention/consent tasdig‘i bo‘lmasa production launchni blokla, ammo lokal/staging implementatsiyani davom ettir.

Tayyorlik: ishlaydigan bot + RBAC panel + conflict-safe kalendar + qabul varaqalari + tekshirilgan hisobotlar + deployment/runbook + backup restore dalili. Hozirgi hujjat faqat reja; bu natijalar implementatsiya davomida isbotlanishi kerak.
