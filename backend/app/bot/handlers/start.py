import httpx
from aiogram import Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import select

from app.bot.keyboards import main_menu_kb, staff_menu_kb
from app.bot.states import Registration
from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models.patient import Patient
from app.models.staff import StaffRole

router = Router(name="start")
settings = get_settings()

ROLE_LABELS = {
    StaffRole.dev: "Dev",
    StaffRole.director: "Direktor",
    StaffRole.admin: "Admin",
    StaffRole.analyst: "Analizchi mutaxassis",
}


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

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Patient).where(Patient.telegram_user_id == message.from_user.id)
        )
        patient = result.scalar_one_or_none()

    if patient is not None:
        await message.answer(f"Xush kelibsiz, {patient.full_name}!", reply_markup=main_menu_kb())
        return

    await state.set_state(Registration.full_name)
    await message.answer("Assalomu alaykum! Ism-familiyangizni to'liq kiriting.")


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
        f"Xush kelibsiz! Siz {ROLE_LABELS[role]} sifatida ro'yxatdan o'tdingiz.",
        reply_markup=staff_menu_kb(),
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
