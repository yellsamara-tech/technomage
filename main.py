import os
import asyncio
from datetime import date
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pytz import timezone
from db import (
    init_db, add_user, get_user, update_status, get_all_users,
    get_status_history, find_user_by_name, get_admins
)
from aiogram.dispatcher.middlewares.error import BaseErrorMiddleware

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден в переменных окружения")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Горячие кнопки статусов
status_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✅ Работаю"), KeyboardButton(text="🤒 Болею")],
        [KeyboardButton(text="🏖 Отпуск"), KeyboardButton(text="✍️ Свой вариант")],
        [KeyboardButton(text="ℹ️ Проверить последний статус"), KeyboardButton(text="✏️ Изменить статус")]
    ],
    resize_keyboard=True
)

# Глобальный middleware для отлова ошибок
class MyErrorMiddleware(BaseErrorMiddleware):
    async def __call__(self, handler, event, data):
        try:
            return await handler(event, data)
        except Exception as e:
            print(f"Ошибка в хэндлере: {e}")
            return None

dp.message.middleware(MyErrorMiddleware())

# Команда /start
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    try:
        user = await get_user(message.from_user.id)
        if user:
            # Дублируем статус на новый день
            today = date.today()
            history = await get_status_history(user['id'])
            if history and history[-1]['status_date'] != today:
                await update_status(user['id'], user['status'])
            await message.answer(
                f"Ты уже зарегистрирован как: {user['full_name']}\n\nВыбери свой статус:",
                reply_markup=status_kb
            )
        else:
            await message.answer("Привет! Введи своё ФИО для регистрации.")
    except Exception as e:
        print(f"Ошибка в /start: {e}")

# Обработка сообщений
@dp.message()
async def process_message(message: types.Message):
    try:
        user = await get_user(message.from_user.id)
        if not user:
            full_name = message.text.strip()
            await add_user(message.from_user.id, full_name)
            await message.answer(
                f"✅ Зарегистрировал тебя как: {full_name}\n\nТеперь выбери свой статус:",
                reply_markup=status_kb
            )
            return

        text = message.text.strip()

        # Проверка последнего статуса
        if text == "ℹ️ Проверить последний статус":
            last_status = user['status'] if user['status'] else "ещё не выбран"
            await message.answer(f"📌 Твой последний статус: {last_status}")
            return

        # Изменить статус
        if text == "✏️ Изменить статус":
            await message.answer("Выбери новый статус или напиши свой текстом 👇", reply_markup=status_kb)
            return

        # Свой вариант
        if text == "✍️ Свой вариант":
            await message.answer("Напиши свой статус сообщением 👇")
            return

        # Обновление статуса
        await update_status(user['id'], text)
        await message.answer(f"📌 Статус обновлён: {text}")

    except Exception as e:
        print(f"Ошибка в process_message: {e}")

# Админ: список всех пользователей
@dp.message(Command("list"))
async def list_users(message: types.Message):
    try:
        admins = await get_admins()
        if message.from_user.id not in [a['id'] for a in admins]:
            await message.answer("⛔ У тебя нет прав для этой команды.")
            return
        users = await get_all_users()
        text = "\n".join([f"{u['id']} — {u['full_name']} — {u['status'] or 'не выбран'}" for u in users])
        await message.answer(f"👥 Все пользователи:\n{text}")
    except Exception as e:
        print(f"Ошибка в /list: {e}")

# Админ: поиск по ФИО
@dp.message(Command("find"))
async def find_user(message: types.Message):
    try:
        admins = await get_admins()
        if message.from_user.id not in [a['id'] for a in admins]:
            await message.answer("⛔ У тебя нет прав для этой команды.")
            return
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.answer("Используй: /find <ФИО>")
            return
        name = args[1]
        users = await find_user_by_name(name)
        if not users:
            await message.answer("❌ Пользователь не найден")
            return
        text = "\n".join([f"{u['id']} — {u['full_name']} — {u['status'] or 'не выбран'}" for u in users])
        await message.answer(f"Результаты поиска:\n{text}")
    except Exception as e:
        print(f"Ошибка в /find: {e}")

# История статусов
@dp.message(Command("history"))
async def status_history(message: types.Message):
    try:
        user = await get_user(message.from_user.id)
        if not user:
            await message.answer("Ты ещё не зарегистрирован.")
            return
        history = await get_status_history(user['id'])
        if not history:
            await message.answer("История статусов пуста.")
            return
        text = "\n".join([f"{h['status_date']}: {h['status']}" for h in history])
        await message.answer(f"📜 История твоих статусов:\n{text}")
    except Exception as e:
        print(f"Ошибка в /history: {e}")

# Напоминание всем пользователям в 18:00 по Самарскому времени
async def send_daily_reminder():
    try:
        users = await get_all_users()
        for user in users:
            try:
                await bot.send_message(
                    user['id'],
                    "⏰ Пожалуйста, обнови свой статус на сегодня!",
                    reply_markup=status_kb
                )
            except Exception as e:
                print(f"Не удалось отправить сообщение {user['id']}: {e}")
    except Exception as e:
        print(f"Ошибка в send_daily_reminder: {e}")

# Главная функция
async def main():
    await init_db()

    # Планировщик
    scheduler = AsyncIOScheduler(timezone=timezone("Asia/Samarkand"))
    scheduler.add_job(send_daily_reminder, 'cron', hour=18, minute=0)
    scheduler.start()

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
