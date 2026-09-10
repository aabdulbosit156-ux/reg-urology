import html
import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from app.bot.keyboards import (
    CLINIC_BTN,
    DOCUMENTS_BTN,
    EXTRA_UPLOAD_CALLBACK,
    STATUS_BTN,
    ai_analyze_kb,
    extra_upload_kb,
)
from app.bot.states import ExtraUpload
from app.database import AsyncSessionLocal
from app.models.analysis import Analysis
from app.models.appointment import Appointment, AppointmentStatus
from app.models.clinic_settings import ClinicSettings
from app.models.patient import Patient, PatientStatus
from app.services.bot_texts import resolve_bot_texts

router = Router(name="menu")
logger = logging.getLogger(__name__)

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
                await message.answer(f"🗓 Qabulingiz band qilingan: <b>{when}</b>.")
                return

    text_key = STATUS_TEXT_KEYS.get(patient.status)
    await message.answer(texts.get(text_key, "Holatingiz yangilanmoqda.") if text_key else "Holatingiz yangilanmoqda.")


async def _send_analysis_file(message: Message, file_id: str, caption: str, is_image: bool) -> bool:
    """Sends a stored analysis file, tolerating the fact that images re-uploaded through the
    storage chat carry a *document* file_id — so a plain answer_photo would fail. Falls back to
    answer_document, then reports failure instead of silently swallowing the error."""
    if is_image:
        try:
            await message.answer_photo(file_id, caption=caption)
            return True
        except TelegramBadRequest:
            pass
    try:
        await message.answer_document(file_id, caption=caption)
        return True
    except TelegramBadRequest:
        logger.warning("Could not send analysis file %s to patient", file_id)
        return False


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

    upload_prompt = "🩺 Sizda davolanish bo'yicha yangi hujjat yoki namunalar bormi?"

    if not analyses:
        await message.answer("📭 Hozircha hujjatlaringiz mavjud emas.")
        await message.answer(upload_prompt, reply_markup=extra_upload_kb())
        return

    await message.answer(f"📋 Sizda {len(analyses)} ta analiz hujjati bor:")

    failed = 0
    for analysis in analyses:
        caption = f"📄 {analysis.file_name or 'Analiz'} · {analysis.created_at.strftime('%d.%m.%Y')}"
        is_image = bool(analysis.mime_type and analysis.mime_type.startswith("image/"))
        sent = await _send_analysis_file(message, analysis.telegram_file_id, caption, is_image)
        if not sent:
            failed += 1
        if analysis.ai_report:
            await message.answer(f"✨ <b>AI tahlili:</b>\n\n{html.escape(analysis.ai_report)}")
        else:
            await message.answer("✨ Ushbu hujjatni tahlil qilish:", reply_markup=ai_analyze_kb(analysis.id))

    if failed:
        await message.answer("⚠️ Ba'zi fayllarni yuborib bo'lmadi. Klinika bilan bog'laning.")

    await message.answer(upload_prompt, reply_markup=extra_upload_kb())


@router.callback_query(F.data == EXTRA_UPLOAD_CALLBACK)
async def handle_extra_upload_request(callback: CallbackQuery, state: FSMContext) -> None:
    patient = await _get_patient(callback.from_user.id)
    if patient is None:
        await callback.answer("Avval ro'yxatdan o'ting.", show_alert=True)
        return
    await state.set_state(ExtraUpload.waiting)
    await callback.answer()
    await callback.message.answer("📎 Hujjat yoki rasmni yuboring (bir nechta bo'lsa ketma-ket yuboring).")


@router.message(F.text == CLINIC_BTN)
async def handle_clinic_info(message: Message) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(ClinicSettings).where(ClinicSettings.id == 1))
        clinic = result.scalar_one_or_none()

    if clinic is None or not clinic.clinic_name:
        await message.answer("ℹ️ Klinika ma'lumotlari hali sozlanmagan.")
        return

    lines = [f"🏥 <b>{html.escape(clinic.clinic_name)}</b>", ""]
    for label, value in (clinic.clinic_contacts or {}).items():
        lines.append(f"📞 {html.escape(str(label))}: {html.escape(str(value))}")
    await message.answer("\n".join(lines))

    if clinic.clinic_lat is not None and clinic.clinic_lng is not None:
        await message.answer_location(clinic.clinic_lat, clinic.clinic_lng)
