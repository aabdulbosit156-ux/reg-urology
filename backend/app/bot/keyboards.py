from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

from app.config import get_settings

STATUS_BTN = "Status"
DOCUMENTS_BTN = "Hujjatlar"
CLINIC_BTN = "Klinika haqida"
SKIP_GOAL_CALLBACK = "skip_goal"


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
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
            [InlineKeyboardButton(text="O'tkazib yuborish", callback_data=SKIP_GOAL_CALLBACK)]
        ]
    )


def staff_menu_kb() -> ReplyKeyboardMarkup | None:
    settings = get_settings()
    if not settings.webapp_url:
        return None
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Asosiy menyu", web_app=WebAppInfo(url=settings.webapp_url))]],
        resize_keyboard=True,
    )
