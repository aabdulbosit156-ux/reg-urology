"""Resolves patient-facing bot copy, letting clinic staff override the defaults via Sozlamalar.

Each key falls back to a sensible Uzbek default if the clinic hasn't customized it yet.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.clinic_settings import ClinicSettings

DEFAULT_BOT_TEXTS: dict[str, str] = {
    "welcome_new": "👋 Assalomu alaykum! Ism-familiyangizni to'liq kiriting.",
    "welcome_returning": "👋 Xush kelibsiz, {full_name}!",
    "status_new": "✅ Arizangiz qabul qilindi. Mutaxassislarimiz tez orada siz bilan bog'lanadi.",
    "status_scheduled": "🗓 Sizning qabul vaqtingiz belgilandi: {when}.",
    "status_unreachable": (
        "📞 Siz bilan bog'lanishga urinib ko'rdik, ammo bog'lana olmadik. Tez orada qayta aloqaga chiqamiz."
    ),
    "status_advised": "💬 Sizga maslahat berildi. Savollaringiz bo'lsa, biz bilan bog'laning.",
    "status_no_show": "❗️ Siz belgilangan qabulga kelmadingiz. Qayta band qilish uchun tez orada bog'lanamiz.",
    "status_arrived": "🤝 Qabulga kelganingiz qayd etildi. Rahmat!",
    "status_analysis_ordered": (
        "🧪 Sizga analiz buyurildi. Namunani suratga olib botga yuboring yoki faylni yuklang "
        "— mutaxassislarimiz maslahat beradi."
    ),
    "status_analysis_ready": "📋 Analiz natijalaringiz tayyor.",
    "appointment_cancelled": "🚫 Sizning qabul vaqtingiz bekor qilindi. Tez orada siz bilan qayta bog'lanamiz.",
}


async def resolve_bot_texts(db: AsyncSession) -> dict[str, str]:
    result = await db.execute(select(ClinicSettings).where(ClinicSettings.id == 1))
    clinic = result.scalar_one_or_none()
    overrides = clinic.bot_texts if clinic and clinic.bot_texts else {}
    return {**DEFAULT_BOT_TEXTS, **overrides}
