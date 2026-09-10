import httpx
from aiogram import Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardRemove
from sqlalchemy import select

from app.bot.keyboards import main_menu_kb, staff_menu_kb
from app.bot.states import Registration
from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models.patient import Patient
from app.models.staff import Staff, StaffRole
from app.services.bot_texts import resolve_bot_texts

router = Router(name="start")
settings = get_settings()

ROLE_LABELS = {
    StaffRole.dev: "Dev",
    StaffRole.director: "Direktor",
    StaffRole.admin: "Admin",
    StaffRole.analyst: "Analizchi mutaxassis",
}


async def _get_active_staff(telegram_user_id: int) -> Staff | None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Staff).where(
                Staff.telegram_user_id == telegram_user_id, Staff.is_active.is_(True)
            )
        )
        return result.scalar_one_or_none()


async def _greet_staff(message: Message, staff: Staff) -> None:
    # Staff must never land on the patient keyboard — show the admin panel keyboard (or clear it).
    await message.answer(
        f"👋 Xush kelibsiz, {staff.full_name}!\nSiz {ROLE_LABELS[staff.role]} sifatida tizimdasiz.",
        reply_markup=staff_menu_kb() or ReplyKeyboardRemove(),
    )


@router.message(CommandStart())
async def handle_start(message: Message, command: CommandObject, state: FSMContext) -> None:
    payload = command.args

    if payload and payload.startswith("staff_"):
        await _handle_staff_onboarding(message, payload.removeprefix("staff_"))
        return

    if payload and payload.startswith("invite_"):
        linked = await _handle_invite(message, payload.removeprefix("invite_"))
        if linked:
            return

    # Staff (director/admin/analyst) are recognised first so they get the admin keyboard,
    # not the patient registration flow.
    staff = await _get_active_staff(message.from_user.id)
    if staff is not None:
        await _greet_staff(message, staff)
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Patient).where(Patient.telegram_user_id == message.from_user.id)
        )
        patient = result.scalar_one_or_none()
        texts = await resolve_bot_texts(db)

    if patient is not None:
        await message.answer(
            texts["welcome_returning"].format(full_name=patient.full_name), reply_markup=main_menu_kb()
        )
        return

    await state.set_state(Registration.full_name)
    await message.answer(texts["welcome_new"])


async def _handle_staff_onboarding(message: Message, token: str) -> None:
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            response = await client.post(
                f"{settings.api_base_url}/api/auth/staff/confirm",
                json={
                    "token": token,
                    "telegram_user_id": message.from_user.id,
                    "full_name": message.from_user.full_name,
                    "telegram_username": message.from_user.username,
                },
                headers={"X-Bot-Secret": settings.bot_internal_secret},
            )
        except httpx.HTTPError:
            await message.answer("Server bilan bog'lanib bo'lmadi. Birozdan so'ng qayta urinib ko'ring.")
            return

    if response.status_code != 200:
        await message.answer(
            "Taklif havolasi yaroqsiz yoki muddati o'tgan. Administratordan yangi havola so'rang."
        )
        return

    role = StaffRole(response.json()["role"])
    await message.answer(
        f"✅ Xush kelibsiz! Siz {ROLE_LABELS[role]} sifatida ro'yxatdan o'tdingiz.",
        reply_markup=staff_menu_kb() or ReplyKeyboardRemove(),
    )


async def _handle_invite(message: Message, token: str) -> bool:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Patient).where(Patient.invite_token == token))
        patient = result.scalar_one_or_none()
        if patient is None:
            return False
        if patient.telegram_user_id is None:
            patient.telegram_user_id = message.from_user.id
            patient.telegram_username = message.from_user.username
            await db.commit()
        full_name = patient.full_name

    await message.answer(
        f"Xush kelibsiz, {full_name}! Ma'lumotlaringiz allaqachon ro'yxatga olingan.",
        reply_markup=main_menu_kb(),
    )
    return True
