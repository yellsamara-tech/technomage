import os
import asyncio
from datetime import date
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup
from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pytz import timezone
from db import (
    init_db, add_user, get_user, update_status, get_all_users,
    get_status_history, find_user_by_name, set_user_status, get_admins
)
import nest_asyncio
nest_asyncio.apply()  # Для Render

# ----- Переменные окружения -----
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден")

RENDER_URL = os.getenv("RENDER_EXTERNAL_URL")
if not RENDER_URL:
    raise ValueError("❌ RENDER_EXTERNAL_URL не найден")

PORT = int(os.getenv("PORT", 5000))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"{RENDER_URL}{WEBHOOK_PATH}"

# ----- Горячие кнопки -----
status_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton("✅ Работаю"), KeyboardButton("🤒 Болею")],
        [KeyboardButton("🏖 Отпуск"), KeyboardButton("✍️ Свой вариант")],
        [KeyboardButton("ℹ️ Проверить последний статус"), KeyboardButton("✏️ Изменить статус")]
    ],
    resize_keyboard=True
)

# ----- Хэндлеры ----- #
@dp.message(Command("start"))
async def start_handler(message: Message):
    user = await get_user(message.from_user.id)
    today = date.today()
    if user:
        if user.get("status") and user.get("last_update") != today:
            await update_status(user["id"], user["status"])
        await message.answer(
            f"Ты уже зарегистрирован как: {user['full_name']}\nВыбери свой статус:", 
            reply_markup=status_kb
        )
    else:
        await message.answer("Привет! Введи своё ФИО для регистрации.")

@dp.message()
async def process_message(message: Message):
    user = await get_user(message.from_user.id)
    text = message.text.strip()

    if not user:
        await add_user(message.from_user.id, text)
        await message.answer(f"✅ Зарегистрировал тебя как: {text}\nТеперь выбери свой статус:", reply_markup=status_kb)
        return

    # Проверка последнего статуса
    if text == "ℹ️ Проверить последний статус":
        last_status = user.get("status") or "ещё не выбран"
        await message.answer(f"📌 Твой последний статус: {last_status}")
        return

    if text == "✏️ Изменить статус":
        await message.answer("Выбери новый статус или напиши свой текстом 👇", reply_markup=status_kb)
        return

    if text == "✍️ Свой вариант":
        await message.answer("Напиши свой статус сообщением 👇")
        return

    # Обновление статуса
    await update_status(user["id"], text)
    await message.answer(f"📌 Статус обновлён: {text}")

# ----- Команды админа ----- #
@dp.message(Command("users"))
async def list_users(message: Message):
    user = await get_user(message.from_user.id)
    if not user or not user.get("is_admin"):
        await message.answer("❌ Доступ запрещён")
        return
    users = await get_all_users()
    text = "\n".join([f"{u['full_name']} — {u.get('status', 'нет статуса')}" for u in users])
    await message.answer(f"Список пользователей:\n{text}")

@dp.message(Command("history"))
async def history_command(message: Message):
    user = await get_user(message.from_user.id)
    if not user or not user.get("is_admin"):
        await message.answer("❌ Доступ запрещён")
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: /history <имя>")
        return
    name = parts[1]
    rows = await find_user_by_name(name)
    if not rows:
        await message.answer("Пользователь не найден")
        return
    for u in rows:
        history = await get_status_history(u["id"])
        text = "\n".join([f"{r['status_date']}: {r['status']}" for r in history])
        await message.answer(f"История {u['full_name']}:\n{text}")

@dp.message(Command("set"))
async def set_status_command(message: Message):
    user = await get_user(message.from_user.id)
    if not user or not user.get("is_admin"):
        await message.answer("❌ Доступ запрещён")
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Использование: /set <имя> <статус>")
        return
    name = parts[1]
    status = parts[2]
    rows = await find_user_by_name(name)
    if not rows:
        await message.answer("Пользователь не найден")
        return
    for u in rows:
        await set_user_status(u["id"], status)
    await message.answer(f"✅ Статус обновлён для {name}")

# ----- Ежедневное напоминание ----- #
async def send_daily_reminder():
    users = await get_all_users()
    for user in users:
        try:
            await bot.send_message(user["id"], "⏰ Пожалуйста, обнови свой статус на сегодня!", reply_markup=status_kb)
        except Exception as e:
            print(f"Не удалось отправить сообщение {user['id']}: {e}")

# ----- Webhook сервер ----- #
async def handle(request):
    data = await request.json()
    update = types.Update(**data)
    await dp.feed_update(update)  # aiogram 3.x
    return web.Response()

async def on_startup(app):
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(WEBHOOK_URL)
    print(f"Webhook установлен: {WEBHOOK_URL}")

async def on_cleanup(app):
    await bot.delete_webhook()
    await bot.session.close()

# ----- Запуск webhook ----- #
async def start_webhook():
    app = web.Application()
    app.router.add_post(WEBHOOK_PATH, handle)
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=PORT)
    await site.start()
    print(f"Webhook сервер запущен на порту {PORT}")

# ----- Главная функция ----- #
async def main():
    await init_db()

    scheduler = AsyncIOScheduler(timezone=timezone("Asia/Samarkand"))
    scheduler.add_job(send_daily_reminder, 'cron', hour=18, minute=0)
    scheduler.start()

    await start_webhook()
    while True:
        await asyncio.sleep(3600)

# ----- Запуск ----- #
if __name__ == "__main__":
    asyncio.run(main())
