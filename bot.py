from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from datetime import datetime
import asyncio
import os

from config import BOT_TOKEN, ADMIN_EMAIL, TIMEZONE
from database import init_db, add_user, get_user_by_id, update_status, get_status_matrix
from scheduler import start_scheduler
from utils import send_email_report, get_day_column, generate_status_keyboard

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

# FSM для регистрации
class RegisterState(StatesGroup):
    full_name = State()
    tab_number = State()

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message, state: FSMContext):
    user = get_user_by_id(message.from_user.id)
    if user:
        await message.answer(f"Вы уже зарегистрированы, {user[2]}!\nНапишите свой статус на сегодня:", reply_markup=generate_status_keyboard())
    else:
        await state.set_state(RegisterState.full_name.state)
        await message.answer("Добро пожаловать!\nВведите ваше ФИО:")

@dp.message_handler(state=RegisterState.full_name)
async def process_full_name(message: types.Message, state: FSMContext):
    await state.update_data(full_name=message.text)
    await message.answer("Теперь введите ваш табельный номер:")
    await state.set_state(RegisterState.tab_number.state)

@dp.message_handler(state=RegisterState.tab_number)
async def process_tab_number(message: types.Message, state: FSMContext):
    data = await state.get_data()
    full_name = data['full_name']
    tab_number = message.text.strip()
    add_user(user_id=message.from_user.id, tab_number=tab_number, full_name=full_name)
    await message.answer("Регистрация завершена!\nТеперь укажите статус на сегодня:", reply_markup=generate_status_keyboard())
    await state.finish()

@dp.message_handler(lambda msg: msg.text.lower() in ['на месте', 'отпуск', 'больничный', 'командировка'])
async def quick_status(message: types.Message):
    now = datetime.now().astimezone(TIMEZONE)
    update_status(message.from_user.id, now.day, message.text)
    await message.answer(f"Статус '{message.text}' записан на {now.strftime('%d.%m.%Y')}.")

@dp.message_handler(commands=['статус'])
async def show_status(message: types.Message):
    now = datetime.now().astimezone(TIMEZONE)
    user = get_user_by_id(message.from_user.id)
    if not user:
        await message.answer("Вы ещё не зарегистрированы. Введите /start.")
        return
    col = get_day_column(now.day)
    await message.answer(f"Ваш статус на сегодня ({now.day}): {user[col] or 'не установлен'}")

@dp.message_handler()
async def custom_status(message: types.Message):
    now = datetime.now().astimezone(TIMEZONE)
    update_status(message.from_user.id, now.day, message.text)
    await message.answer(f"Установлен пользовательский статус: {message.text}")

if __name__ == '__main__':
    init_db()
    loop = asyncio.get_event_loop()
    loop.create_task(start_scheduler(bot))
    executor.start_polling(dp, skip_updates=True)
