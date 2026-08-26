from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from regurolog_api.models import SettingsVersion

DEFAULT_BOT_MESSAGES = {
    "welcome": "Assalomu alaykum. Urolog konsultatsiyasiga murojaat qoldirish uchun davom eting.",
    "consent": (
        "Ma’lumotlaringiz klinika xodimlari siz bilan bog‘lanishi va qabulni tashkil qilishi uchun "
        "ishlatiladi. Rozimisiz?"
    ),
    "full_name_prompt": "Ism-familiyangizni yozing.",
    "phone_prompt": "Telefon raqamingizni +998XXXXXXXXX formatida yuboring.",
    "phone_error": "Telefon raqami noto‘g‘ri. Masalan: +998 99 000 11 22.",
    "registered": "Ro‘yxatdan o‘tdingiz.",
    "reason_prompt": ("Konsultatsiya olish maqsadingizni qisqacha yozing. Bu ixtiyoriy."),
    "skip_reason": "Shart emas",
    "finished": "Ma’lumotlaringizni oldik. Mutaxassislarimiz siz bilan tez orada bog‘lanadi.",
    "already_registered": "Murojaatingiz qabul qilingan. Mutaxassislarimiz siz bilan bog‘lanadi.",
    "new_inquiry_confirm": "Oldingi murojaatingiz yakunlangan. Yangi murojaat ochilsinmi?",
    "appointment_confirmation": (
        "{full_name}, qabulingiz {date} kuni {time}ga belgilandi. Manzil: {clinic_address}."
    ),
    "rescheduled": "Qabulingiz {date} kuni {time}ga ko‘chirildi.",
    "cancelled": "Qabulingiz bekor qilindi.",
    "reminder": "Eslatma: qabulingiz {date} kuni {time}da. Manzil: {clinic_address}.",
    "generic_error": "Hozir texnik xato yuz berdi. Birozdan keyin qayta urinib ko‘ring.",
}


async def bot_messages(
    db_session: AsyncSession, pinned_version: int | None = None
) -> tuple[dict[str, str], int]:
    statement = select(SettingsVersion).where(SettingsVersion.namespace == "bot_messages")
    if pinned_version is None:
        statement = statement.where(SettingsVersion.state == "published").order_by(
            SettingsVersion.version.desc()
        )
    else:
        statement = statement.where(SettingsVersion.version == pinned_version)
    version = await db_session.scalar(statement.limit(1))
    if version is None:
        return DEFAULT_BOT_MESSAGES.copy(), 0
    merged = DEFAULT_BOT_MESSAGES | {
        key: str(value)
        for key, value in version.payload.items()
        if key in DEFAULT_BOT_MESSAGES and isinstance(value, str)
    }
    return merged, version.version
