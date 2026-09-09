import mimetypes
import os
import uuid

from aiogram import F, Router
from aiogram.types import FSInputFile, Message
from sqlalchemy import select

from app.bot.keyboards import main_menu_kb
from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models.analysis import Analysis, AnalysisUploadedBy
from app.models.patient import Patient, PatientStatus

router = Router(name="analysis_upload")
settings = get_settings()


@router.message(F.photo | F.document)
async def handle_analysis_file(message: Message) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Patient).where(Patient.telegram_user_id == message.from_user.id)
        )
        patient = result.scalar_one_or_none()

    if patient is None:
        return
    if patient.status != PatientStatus.analysis_ordered:
        await message.answer(
            "Hozircha sizdan analiz fayli kutilmayapti. Savollaringiz bo'lsa, mutaxassislarimiz "
            "bilan bog'lanamiz.",
            reply_markup=main_menu_kb(),
        )
        return

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
        db.add(
            Analysis(
                patient_id=patient.id,
                uploaded_by=AnalysisUploadedBy.patient,
                telegram_file_id=stored_file_id,
                telegram_file_unique_id=stored_file_unique_id,
                file_name=file_name,
                mime_type=mime_type,
                ordered=True,
            )
        )
        await db.commit()

    await message.answer("Analiz muvaffaqiyatli yuklandi. Rahmat! Mutaxassislarimiz tez orada ko'rib chiqadi.")
