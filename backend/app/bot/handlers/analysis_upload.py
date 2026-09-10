import html
import mimetypes
import os
import uuid

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, Message
from sqlalchemy import select

from app.bot.keyboards import ai_analyze_kb, main_menu_kb
from app.bot.states import AnalyzeNow, ExtraUpload
from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models.analysis import Analysis, AnalysisUploadedBy
from app.models.patient import Patient, PatientStatus
from app.services import ai_analysis
from app.services.ai_analysis import MAX_AI_ANALYSES_PER_PATIENT, count_ai_analyses
from app.services.telegram import notify_web_of_change

router = Router(name="analysis_upload")
settings = get_settings()


async def _store_uploaded_file(message: Message, patient: Patient) -> Analysis:
    """Downloads the file, re-uploads it to the clinic's storage chat (so the patient can't
    delete the original out from under us), and records it. See PLAN.md section 9."""
    if message.document:
        file_id = message.document.file_id
        file_unique_id = message.document.file_unique_id
        file_name = message.document.file_name
        mime_type = message.document.mime_type
    else:
        file_id = message.photo[-1].file_id
        file_unique_id = message.photo[-1].file_unique_id
        file_name = None
        mime_type = "image/jpeg"

    os.makedirs(settings.analysis_tmp_dir, exist_ok=True)
    ext = mimetypes.guess_extension(mime_type or "") or ""
    tmp_path = os.path.join(settings.analysis_tmp_dir, f"{uuid.uuid4()}{ext}")
    await message.bot.download(file_id, destination=tmp_path)

    try:
        if settings.storage_chat_id:
            sent = await message.bot.send_document(
                settings.storage_chat_id,
                FSInputFile(tmp_path, filename=file_name or os.path.basename(tmp_path)),
                caption=f"Bemor: {patient.full_name} ({patient.phone})",
            )
            stored_file_id = sent.document.file_id
            stored_file_unique_id = sent.document.file_unique_id
        else:
            stored_file_id = file_id
            stored_file_unique_id = file_unique_id
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    async with AsyncSessionLocal() as db:
        analysis = Analysis(
            patient_id=patient.id,
            uploaded_by=AnalysisUploadedBy.patient,
            telegram_file_id=stored_file_id,
            telegram_file_unique_id=stored_file_unique_id,
            file_name=file_name,
            mime_type=mime_type,
            ordered=patient.status == PatientStatus.analysis_ordered,
        )
        db.add(analysis)
        await db.commit()
        await db.refresh(analysis)

    await notify_web_of_change()
    return analysis


async def _get_patient(telegram_user_id: int) -> Patient | None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Patient).where(Patient.telegram_user_id == telegram_user_id))
        return result.scalar_one_or_none()


# Opt-in upload started from the "📎 Yana hujjat yuklash" button — accepts a file regardless of status.
@router.message(ExtraUpload.waiting, F.photo | F.document)
async def handle_extra_upload(message: Message, state: FSMContext) -> None:
    patient = await _get_patient(message.from_user.id)
    if patient is None:
        await state.clear()
        return
    analysis = await _store_uploaded_file(message, patient)
    await message.answer(
        "✅ Hujjat qabul qilindi. Mutaxassis maslahatini olishni xohlaysizmi?",
        reply_markup=ai_analyze_kb(analysis.id),
    )
    # Stay in ExtraUpload.waiting so the patient can send several files in a row.


@router.message(ExtraUpload.waiting)
async def handle_extra_upload_other(message: Message, state: FSMContext) -> None:
    await message.answer(
        "📎 Iltimos, hujjat yoki rasm yuboring. Yakunlash uchun menyudagi tugmalardan foydalaning.",
        reply_markup=main_menu_kb(),
    )
    await state.clear()


# Started from the "✨ Analizni tahlil qilish" menu button — stores the file into the patient's
# documents and runs AI analysis immediately, saving the report to the DB.
@router.message(AnalyzeNow.waiting, F.photo | F.document)
async def handle_analyze_now(message: Message, state: FSMContext) -> None:
    patient = await _get_patient(message.from_user.id)
    if patient is None:
        await state.clear()
        return
    await state.clear()

    analysis = await _store_uploaded_file(message, patient)

    async with AsyncSessionLocal() as db:
        analyzed = await count_ai_analyses(db, patient.id)
        if analyzed >= MAX_AI_ANALYSES_PER_PATIENT:
            await message.answer(
                f"✅ Hujjat saqlandi.\n⚠️ AI tahlil limiti tugadi (maksimal {MAX_AI_ANALYSES_PER_PATIENT} ta). "
                "Qo'shimcha maslahat uchun klinika bilan bog'laning.",
                reply_markup=main_menu_kb(),
            )
            return

        result = await db.execute(select(Analysis).where(Analysis.id == analysis.id))
        analysis_row = result.scalar_one()
        await message.answer("⏳ Hujjat qabul qilindi, tahlil qilinmoqda...")
        try:
            report = await ai_analysis.analyze_lab_report(db, analysis_row)
        except ai_analysis.AIAnalysisError as exc:
            await message.answer(
                f"✅ Hujjat saqlandi.\n⚠️ Tahlil qilishda xatolik: {exc}",
                reply_markup=main_menu_kb(),
            )
            return
        analysis_row.ai_report = report
        await db.commit()

    await notify_web_of_change()
    await message.answer(f"✨ <b>AI tahlili:</b>\n\n{html.escape(report)}", reply_markup=main_menu_kb())


@router.message(AnalyzeNow.waiting)
async def handle_analyze_now_other(message: Message, state: FSMContext) -> None:
    await message.answer(
        "✨ Iltimos, tahlil qilinadigan hujjat yoki rasm yuboring.",
        reply_markup=main_menu_kb(),
    )
    await state.clear()


@router.message(F.photo | F.document)
async def handle_analysis_file(message: Message) -> None:
    patient = await _get_patient(message.from_user.id)
    if patient is None:
        return
    if patient.status != PatientStatus.analysis_ordered:
        await message.answer(
            "Hozircha sizdan analiz fayli kutilmayapti. Yangi hujjat qo'shish uchun "
            "«📁 Hujjatlar» bo'limidan foydalaning.",
            reply_markup=main_menu_kb(),
        )
        return

    analysis = await _store_uploaded_file(message, patient)
    await message.answer(
        "✅ Analiz muvaffaqiyatli yuklandi. Rahmat! Mutaxassislarimiz tez orada ko'rib chiqadi.\n\n"
        "✨ Mutaxassis maslahatini olishni xohlaysizmi?",
        reply_markup=ai_analyze_kb(analysis.id),
    )
