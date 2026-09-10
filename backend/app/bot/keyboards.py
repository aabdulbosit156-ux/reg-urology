import uuid

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

from app.config import get_settings

STATUS_BTN = "📊 Holatim"
DOCUMENTS_BTN = "📁 Hujjatlar"
CLINIC_BTN = "🏥 Klinika haqida"
ANALYZE_BTN = "✨ Analizni tahlil qilish"
SKIP_GOAL_CALLBACK = "skip_goal"
AI_ANALYZE_CALLBACK_PREFIX = "ai_analyze:"
EXTRA_UPLOAD_CALLBACK = "extra_upload"


def extra_upload_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📎 Yana hujjat yuklash", callback_data=EXTRA_UPLOAD_CALLBACK)]
        ]
    )


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=ANALYZE_BTN)],
            [KeyboardButton(text=STATUS_BTN)],
            [KeyboardButton(text=DOCUMENTS_BTN), KeyboardButton(text=CLINIC_BTN)],
        ],
        resize_keyboard=True,
    )


def phone_request_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="\U0001f4de Telefon raqamni yuborish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def goal_skip_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏭ O'tkazib yuborish", callback_data=SKIP_GOAL_CALLBACK)]
        ]
    )


def ai_analyze_kb(analysis_id: uuid.UUID) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✨ Analizni tahlil qilish",
                    callback_data=f"{AI_ANALYZE_CALLBACK_PREFIX}{analysis_id}",
                )
            ]
        ]
    )


def staff_menu_kb() -> ReplyKeyboardMarkup | None:
    settings = get_settings()
    if not settings.webapp_url:
        return None
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🖥 Admin panel", web_app=WebAppInfo(url=settings.webapp_url))]],
        resize_keyboard=True,
    )
