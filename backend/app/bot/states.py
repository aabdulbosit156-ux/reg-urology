from aiogram.fsm.state import State, StatesGroup


class Registration(StatesGroup):
    full_name = State()
    phone = State()
    goal = State()


class ExtraUpload(StatesGroup):
    waiting = State()


class AnalyzeNow(StatesGroup):
    waiting = State()
