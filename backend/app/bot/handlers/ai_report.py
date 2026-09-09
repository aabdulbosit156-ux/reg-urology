import uuid

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy import select

from app.bot.keyboards import AI_ANALYZE_CALLBACK_PREFIX
from app.database import AsyncSessionLocal
from app.models.analysis import Analysis
from app.services import ai_analysis

router = Router(name="ai_report")


@router.callback_query(F.data.startswith(AI_ANALYZE_CALLBACK_PREFIX))
async def handle_ai_analyze(callback: CallbackQuery) -> None:
    analysis_id = uuid.UUID(callback.data.removeprefix(AI_ANALYZE_CALLBACK_PREFIX))
    await callback.answer("Tahlil qilinmoqda...")

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Analysis).where(Analysis.id == analysis_id))
        analysis = result.scalar_one_or_none()
        if analysis is None:
            await callback.message.answer("Fayl topilmadi.")
            return

        try:
            report = await ai_analysis.analyze_lab_report(db, analysis)
        except ai_analysis.AIAnalysisError as exc:
            await callback.message.answer(f"Tahlil qilishda xatolik yuz berdi: {exc}")
            return

        analysis.ai_report = report
        await db.commit()

    await callback.message.answer(f"\U0001f4cb Analiz tahlili:\n\n{report}")
