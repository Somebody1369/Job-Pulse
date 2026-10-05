from aiogram.fsm.state import State, StatesGroup


class SubscribeForm(StatesGroup):
    skills = State()
    remote = State()
    salary = State()
    experience = State()
