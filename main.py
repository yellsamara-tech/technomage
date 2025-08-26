import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from db import init_db, add_user, get_user, update_status

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден в переменных окружения")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Горячие кнопки статусов
status_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✅ Работаю"), KeyboardButton(text="🤒 Болею")],
        [KeyboardButton(text="🏖 Отпуск"), KeyboardButton(text="✍️ Свой вариант")]
    ],
    resize_keyboard=True
)

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    user = await get_user(message.from_user.id)
    if user:
        await message.answer(
            f"Ты уже зарегистрирован как: {user['full_name']}\n\nВыбери свой статус:",
            reply_markup=status_kb
        )
    else:
        await message.answer("Привет! Введи своё ФИО для регистрации.")

@dp.message()
async def process_message(message: types.Message):
    user = await get_user(message.from_user.id)

    # Если пользователь ещё не зарегистрирован → сохраняем ФИО
    if not user:
        full_name = message.text.strip()
        await add_user(message.from_user.id, full_name)
        await message.answer(
            f"✅ Зарегистрировал тебя как: {full_name}\n\nТеперь выбери свой статус:",
            reply_markup=status_kb
        )
        return

    # Если пользователь зарегистрирован → обновляем статус
    text = message.text.strip()
    if text == "✍️ Свой вариант":
        await message.answer("Напиши свой статус сообщением 👇")
    else:
        await update_status(message.from_user.id, text)
        await message.answer(f"📌 Статус обновлён: {text}")

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
