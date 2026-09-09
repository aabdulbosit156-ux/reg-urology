from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy import select

from app.bot.keyboards import CLINIC_BTN, DOCUMENTS_BTN, STATUS_BTN
from app.database import AsyncSessionLocal
from app.models.analysis import Analysis
from app.models.appointment import Appointment, AppointmentStatus
from app.models.clinic_settings import ClinicSettings
from app.models.patient import Patient, PatientStatus

router = Router(name="menu")

STATUS_MESSAGES = {
    PatientStatus.new: "Arizangiz qabul qilindi. Mutaxassislarimiz tez orada siz bilan bog'lanadi.",
    PatientStatus.unreachable: (
        "Siz bilan bog'lanishga urinib ko'rdik, ammo bog'lana olmadik. Tez orada qayta aloqaga chiqamiz."
    ),
    PatientStatus.advised: "Sizga mutaxassis tomonidan maslahat berilgan.",
    PatientStatus.no_show: "Belgilangan qabulga kelmadingiz. Qayta band qilish uchun tez orada bog'lanamiz.",
    PatientStatus.arrived: "Qabulga kelganingiz qayd etildi.",
    PatientStatus.analysis_ordered: (
        "Sizga analiz buyurildi. Namunani suratga olib botga yuboring yoki faylni yuklang "
        "— mutaxassislarimiz maslahat beradi."
    ),
    PatientStatus.analysis_ready: "Analiz natijalaringiz tayyor.",
}


async def _get_patient(telegram_user_id: int) -> Patient | None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Patient).where(Patient.telegram_user_id == telegram_user_id))
        return result.scalar_one_or_none()


@router.message(F.text == STATUS_BTN)
async def handle_status(message: Message) -> None:
    patient = await _get_patient(message.from_user.id)
    if patient is None:
        await message.answer("Siz hali ro'yxatdan o'tmagansiz. /start buyrug'ini yuboring.")
        return

    if patient.status == PatientStatus.scheduled:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Appointment)
                .where(
                    Appointment.patient_id == patient.id,
                    Appointment.status == AppointmentStatus.scheduled,
                )
                .order_by(Appointment.start_at.desc())
            )
            appointment = result.scalars().first()
        if appointment is not None:
            when = appointment.start_at.strftime("%d.%m.%Y %H:%M")
            await message.answer(f"Qabulingiz band qilingan: {when}.")
            return

    await message.answer(STATUS_MESSAGES.get(patient.status, "Holatingiz yangilanmoqda."))


@router.message(F.text == DOCUMENTS_BTN)
async def handle_documents(message: Message) -> None:
    patient = await _get_patient(message.from_user.id)
    if patient is None:
        await message.answer("Siz hali ro'yxatdan o'tmagansiz. /start buyrug'ini yuboring.")
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Analysis).where(Analysis.patient_id == patient.id).order_by(Analysis.created_at)
        )
        analyses = result.scalars().all()

    if not analyses:
        await message.answer("Hozircha hujjatlaringiz mavjud emas.")
        return

    for analysis in analyses:
        caption = analysis.created_at.strftime("%d.%m.%Y")
        if analysis.mime_type and analysis.mime_type.startswith("image/"):
            await message.answer_photo(analysis.telegram_file_id, caption=caption)
        else:
            await message.answer_document(analysis.telegram_file_id, caption=caption)


@router.message(F.text == CLINIC_BTN)
async def handle_clinic_info(message: Message) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(ClinicSettings).where(ClinicSettings.id == 1))
        clinic = result.scalar_one_or_none()

    if clinic is None or not clinic.clinic_name:
        await message.answer("Klinika ma'lumotlari hali sozlanmagan.")
        return

    lines = [f"<b>{clinic.clinic_name}</b>"]
    for label, value in (clinic.clinic_contacts or {}).items():
        lines.append(f"{label}: {value}")
    await message.answer("\n".join(lines))

    if clinic.clinic_lat is not None and clinic.clinic_lng is not None:
        await message.answer_location(clinic.clinic_lat, clinic.clinic_lng)
