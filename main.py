# main.py
import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from db import init_db, get_user, add_user, set_status

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN") or "ВАШ_ТОКЕН"  # можно вставить сразу токен
WEBHOOK_URL = os.getenv("WEBHOOK_URL") or "https://dia-804u.onrender.com/webhook"

bot = Bot(token=TOKEN)
dp = Dispatcher()


# === Меню статусов ===
def get_status_menu():
    buttons = [
        [KeyboardButton(text="✅ Работаю")],
        [KeyboardButton(text="🏠 Отпуск"), KeyboardButton(text="🤒 Больничный")],
        [KeyboardButton(text="🚗 Командировка"), KeyboardButton(text="❌ Выходной")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


# === Старт ===
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user = await get_user(message.from_user.id)
    if user:
        await message.answer(
            f"Привет, {user['full_name']}!\nВыберите статус:",
            reply_markup=get_status_menu()
        )
    else:
        await message.answer("Добро пожаловать! Введите своё ФИО:")


# === Регистрация по шагам ===
@dp.message(F.text.regexp(r"^[А-Яа-яЁё\s-]+$"))
async def reg_fullname(message: types.Message):
    user = await get_user(message.from_user.id)
    if not user:
        # сохраняем временно ФИО в память (state можно прикрутить позже)
        message.bot["reg"] = {"full_name": message.text}
        await message.answer("Теперь введите табельный номер:")
    elif not user["full_name"]:
        await message.answer("ФИО обновлено.")
    else:
        # если юзер есть и уже регистрировался
        pass


@dp.message(F.text.regexp(r"^\d{3,6}$"))
async def reg_tab_number(message: types.Message):
    reg = message.bot.get("reg")
    if reg and "full_name" in reg:
        reg["tab_number"] = message.text
        await message.answer("Введите номер телефона (+7...):")


@dp.message(F.text.regexp(r"^\+7\d{10}$"))
async def reg_phone(message: types.Message):
    reg = message.bot.get("reg")
    if reg and "tab_number" in reg:
        await add_user(
            message.from_user.id,
            reg["tab_number"],
            reg["full_name"],
            message.text
        )
        await message.answer("Регистрация завершена ✅\nТеперь выберите статус:",
                             reply_markup=get_status_menu())
        message.bot["reg"] = {}  # очищаем временные данные


# === Выбор статуса ===
@dp.message(F.text.in_(["✅ Работаю", "🏠 Отпуск", "🤒 Больничный", "🚗 Командировка", "❌ Выходной"]))
async def status_chosen(message: types.Message):
    status = message.text
    await set_status(message.from_user.id, status)
    await message.answer(f"Статус сохранён: {status}")


# === Запуск ===
async def main():
    await init_db()
    await bot.set_webhook(WEBHOOK_URL)
    logging.info("Бот запущен с вебхуком %s", WEBHOOK_URL)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
