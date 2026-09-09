from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy import select

from app.bot.keyboards import CLINIC_BTN, DOCUMENTS_BTN, STATUS_BTN
from app.database import AsyncSessionLocal
from app.models.analysis import Analysis
from app.models.appointment import Appointment, AppointmentStatus
from app.models.clinic_settings import ClinicSettings
from app.models.patient import Patient, PatientStatus
from app.services.bot_texts import resolve_bot_texts

router = Router(name="menu")

STATUS_TEXT_KEYS = {
    PatientStatus.new: "status_new",
    PatientStatus.unreachable: "status_unreachable",
    PatientStatus.advised: "status_advised",
    PatientStatus.no_show: "status_no_show",
    PatientStatus.arrived: "status_arrived",
    PatientStatus.analysis_ordered: "status_analysis_ordered",
    PatientStatus.analysis_ready: "status_analysis_ready",
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

    async with AsyncSessionLocal() as db:
        texts = await resolve_bot_texts(db)
        if patient.status == PatientStatus.scheduled:
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

    text_key = STATUS_TEXT_KEYS.get(patient.status)
    await message.answer(texts.get(text_key, "Holatingiz yangilanmoqda.") if text_key else "Holatingiz yangilanmoqda.")


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
