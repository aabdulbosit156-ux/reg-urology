from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from app.bot.keyboards import goal_skip_kb, main_menu_kb, phone_request_kb
from app.bot.states import Registration
from app.database import AsyncSessionLocal
from app.models.patient import Patient, PatientSource, PatientStatus
from app.models.status_history import StatusHistory
from app.services.telegram import notify_web_of_change

router = Router(name="registration")


@router.message(Registration.full_name, F.text)
async def handle_full_name(message: Message, state: FSMContext) -> None:
    full_name = message.text.strip()
    if len(full_name) < 3:
        await message.answer("Iltimos, to'liq ism-familiyangizni kiriting.")
        return
    await state.update_data(full_name=full_name)
    await state.set_state(Registration.phone)
    await message.answer("📱 Rahmat! Endi telefon raqamingizni yuboring.", reply_markup=phone_request_kb())


@router.message(Registration.phone, F.contact)
async def handle_phone_contact(message: Message, state: FSMContext) -> None:
    if message.contact.user_id != message.from_user.id:
        await message.answer("Iltimos, faqat o'zingizning raqamingizni yuboring.")
        return
    await _ask_goal(message, state, message.contact.phone_number)


@router.message(Registration.phone, F.text)
async def handle_phone_text(message: Message, state: FSMContext) -> None:
    digits = "".join(ch for ch in message.text if ch.isdigit())
    if len(digits) < 7:
        await message.answer("Telefon raqam noto'g'ri. Qaytadan urinib ko'ring yoki tugmadan foydalaning.")
        return
    await _ask_goal(message, state, message.text.strip())


async def _ask_goal(message: Message, state: FSMContext, phone: str) -> None:
    await state.update_data(phone=phone)
    await state.set_state(Registration.goal)
    await message.answer(
        "📝 Konsultatsiya maqsadini qisqacha yozing (ixtiyoriy).", reply_markup=goal_skip_kb()
    )


@router.message(Registration.goal, F.text)
async def handle_goal(message: Message, state: FSMContext) -> None:
    await _finish_registration(
        message,
        state,
        goal=message.text.strip(),
        telegram_user_id=message.from_user.id,
        telegram_username=message.from_user.username,
    )


@router.callback_query(Registration.goal, F.data == "skip_goal")
async def handle_goal_skip(callback: CallbackQuery, state: FSMContext) -> None:
    await _finish_registration(
        callback.message,
        state,
        goal=None,
        telegram_user_id=callback.from_user.id,
        telegram_username=callback.from_user.username,
    )
    await callback.answer()


async def _finish_registration(
    answer_target: Message,
    state: FSMContext,
    *,
    goal: str | None,
    telegram_user_id: int,
    telegram_username: str | None,
) -> None:
    data = await state.get_data()

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Patient).where(Patient.telegram_user_id == telegram_user_id))
        patient = result.scalar_one_or_none()
        if patient is None:
            patient = Patient(
                full_name=data["full_name"],
                phone=data["phone"],
                telegram_user_id=telegram_user_id,
                telegram_username=telegram_username,
                consultation_goal=goal,
                source=PatientSource.bot,
                status=PatientStatus.new,
            )
            db.add(patient)
            await db.flush()
            db.add(
                StatusHistory(
                    patient_id=patient.id,
                    from_status=None,
                    to_status=PatientStatus.new,
                    note="Bot orqali ro'yxatdan o'tdi",
                )
            )
        else:
            patient.full_name = data["full_name"]
            patient.phone = data["phone"]
            patient.consultation_goal = goal
        await db.commit()

    await notify_web_of_change()
    await state.clear()
    await answer_target.answer(
        "🎉 Muvaffaqiyatli ro'yxatdan o'tdingiz! Tez orada mutaxassislarimiz siz bilan bog'lanadi.",
        reply_markup=main_menu_kb(),
    )
