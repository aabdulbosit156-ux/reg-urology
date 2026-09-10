import html
import uuid

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy import func, select

from app.bot.keyboards import AI_ANALYZE_CALLBACK_PREFIX
from app.database import AsyncSessionLocal
from app.models.analysis import Analysis
from app.services import ai_analysis

router = Router(name="ai_report")

MAX_AI_ANALYSES_PER_PATIENT = 3


@router.callback_query(F.data.startswith(AI_ANALYZE_CALLBACK_PREFIX))
async def handle_ai_analyze(callback: CallbackQuery) -> None:
    analysis_id = uuid.UUID(callback.data.removeprefix(AI_ANALYZE_CALLBACK_PREFIX))

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Analysis).where(Analysis.id == analysis_id))
        analysis = result.scalar_one_or_none()
        if analysis is None:
            await callback.answer("Fayl topilmadi.", show_alert=True)
            return

        if analysis.ai_report:
            await callback.answer()
            await callback.message.answer(f"✨ <b>AI tahlili:</b>\n\n{html.escape(analysis.ai_report)}")
            return

        analyzed_count = await db.scalar(
            select(func.count())
            .select_from(Analysis)
            .where(Analysis.patient_id == analysis.patient_id, Analysis.ai_report.is_not(None))
        )
        if analyzed_count >= MAX_AI_ANALYSES_PER_PATIENT:
            await callback.answer(
                f"⚠️ Tahlil limiti tugadi (maksimal {MAX_AI_ANALYSES_PER_PATIENT} ta hujjat). "
                "Qo'shimcha maslahat uchun klinika bilan bog'laning.",
                show_alert=True,
            )
            return

        await callback.answer("⏳ Tahlil qilinmoqda...")
        try:
            report = await ai_analysis.analyze_lab_report(db, analysis)
        except ai_analysis.AIAnalysisError as exc:
            await callback.message.answer(f"⚠️ Tahlil qilishda xatolik yuz berdi: {exc}")
            return

        analysis.ai_report = report
        await db.commit()

    await callback.message.answer(f"✨ <b>AI tahlili:</b>\n\n{html.escape(report)}")
