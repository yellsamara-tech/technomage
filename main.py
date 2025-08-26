import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from db import init_db, add_user, get_user

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден в переменных окружения")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    user = await get_user(message.from_user.id)
    if user:
        await message.answer(f"Ты уже зарегистрирован как: {user[1]}")
    else:
        await message.answer("Привет! Введи своё ФИО для регистрации.")

@dp.message()
async def register_user(message: types.Message):
    user = await get_user(message.from_user.id)
    if user:
        await message.answer("Ты уже зарегистрирован 👍")
    else:
        full_name = message.text.strip()
        await add_user(message.from_user.id, full_name)
        await message.answer(f"✅ Зарегистрировал тебя как: {full_name}")

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
