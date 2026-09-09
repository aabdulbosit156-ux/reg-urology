"""Sends a patient's analysis file to OpenAI's vision model for a plain-language lab report
interpretation.

Uses the clinic's own OpenAI API key (ClinicSettings.ai_token, set via Sozlamalar) — this is
a bring-your-own-token feature, not billed through the platform.

The model only accepts images. A PDF upload is rasterized to page images (via PyMuPDF, which
ships its own PDF renderer — no system-level poppler/ghostscript dependency) before being sent.
"""

import base64

import openai
import pymupdf
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import Analysis
from app.models.clinic_settings import ClinicSettings
from app.services import telegram

MODEL = "gpt-4o"
MAX_PDF_PAGES = 5

SYSTEM_PROMPT = """Siz — urologik klinika uchun laborator analiz natijalarini sharhlovchi yordamchisiz. \
Sizga bemorning analiz hujjati rasm(lar) shaklida beriladi.

Vazifangiz:
1. Hujjatdagi barcha laborator ko'rsatkichlarni aniqlang (nomi, qiymati, o'lchov birligi).
2. Har bir ko'rsatkichni normal (etalon) qiymatlar oralig'i bilan solishtiring.
3. Me'yordan chetga chiqqan ko'rsatkichlarni aniq belgilang (oshgan yoki pasaygan).
4. Oddiy, tushunarli tilda umumiy tushuntirish bering — bu ko'rsatkich nima uchun muhim, \
nima sababdan o'zgargan bo'lishi mumkin.
5. Javob oxirida albatta quyidagi ogohlantirishni qo'shing: bu sun'iy intellekt tomonidan \
berilgan umumiy ma'lumot, aniq tashxis va davolash uchun albatta klinika mutaxassisi bilan \
bog'laning.

Javobni faqat o'zbek tilida, aniq va tuzilgan (sarlavhalar, ro'yxatlar) shaklda bering. \
Agar hujjatda laborator ma'lumot topilmasa, buni ochiq ayting."""

IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}


class AIAnalysisError(Exception):
    pass


async def resolve_ai_token(db: AsyncSession) -> str | None:
    result = await db.execute(select(ClinicSettings).where(ClinicSettings.id == 1))
    clinic = result.scalar_one_or_none()
    return clinic.ai_token if clinic and clinic.ai_token else None


def _pdf_to_png_pages(pdf_bytes: bytes, max_pages: int = MAX_PDF_PAGES) -> list[bytes]:
    pages: list[bytes] = []
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc[:max_pages]:
            pixmap = page.get_pixmap(dpi=200)
            pages.append(pixmap.tobytes("png"))
    return pages


async def analyze_lab_report(db: AsyncSession, analysis: Analysis) -> str:
    ai_token = await resolve_ai_token(db)
    if not ai_token:
        raise AIAnalysisError("AI tokeni sozlanmagan")

    content = await telegram.download_file(db, analysis.telegram_file_id)
    if content is None:
        raise AIAnalysisError("Fayl yuklab olinmadi (bot tokeni sozlanmaganmi?)")

    mime_type = analysis.mime_type or "image/jpeg"

    if mime_type == "application/pdf":
        try:
            pages = _pdf_to_png_pages(content)
        except Exception as exc:  # PyMuPDF raises its own exception types per failure mode
            raise AIAnalysisError("PDF faylni o'qib bo'lmadi") from exc
        if not pages:
            raise AIAnalysisError("PDF faylda sahifa topilmadi")
        images = [(page, "image/png") for page in pages]
    elif mime_type in IMAGE_MIME_TYPES:
        images = [(content, mime_type)]
    else:
        raise AIAnalysisError(f"Fayl turi qo'llab-quvvatlanmaydi: {mime_type}")

    image_blocks = [
        {
            "type": "image_url",
            "image_url": {"url": f"data:{img_mime};base64,{base64.standard_b64encode(img).decode()}"},
        }
        for img, img_mime in images
    ]

    client = openai.AsyncOpenAI(api_key=ai_token)
    try:
        response = await client.chat.completions.create(
            model=MODEL,
            max_completion_tokens=2048,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Ushbu analiz natijalarini tahlil qiling."},
                        *image_blocks,
                    ],
                },
            ],
        )
    except openai.APIError as exc:
        raise AIAnalysisError(f"AI xizmati bilan bog'lanishda xatolik: {exc}") from exc

    report = response.choices[0].message.content if response.choices else None
    if not report:
        raise AIAnalysisError("AI javob bermadi")
    return report
