import os
import asyncio
from datetime import date
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pytz import timezone
from db import init_db, add_user, get_user, update_status, get_all_users

# ----- Переменные окружения -----
BOT_TOKEN = os.getenv("BOT_TOKEN")
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL")
PORT = int(os.getenv("PORT", 5000))

if not BOT_TOKEN or not RENDER_URL:
    raise ValueError("❌ BOT_TOKEN и RENDER_EXTERNAL_URL должны быть установлены")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"{RENDER_URL}{WEBHOOK_PATH}"

# ----- Горячие кнопки -----
status_kb = types.ReplyKeyboardMarkup(
    keyboard=[
        [types.KeyboardButton("✅ Работаю"), types.KeyboardButton("🤒 Болею")],
        [types.KeyboardButton("🏖 Отпуск"), types.KeyboardButton("✍️ Свой вариант")],
        [types.KeyboardButton("ℹ️ Проверить последний статус"), types.KeyboardButton("✏️ Изменить статус")]
    ],
    resize_keyboard=True
)

# ----- Админ ID -----
ADMIN_IDS = [12345678]  # сюда свои ID админов

# ----- Хэндлеры пользователей -----
@dp.message(Command("start"))
async def start_handler(message: types.Message):
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
async def process_message(message: types.Message):
    user = await get_user(message.from_user.id)
    text = message.text.strip()
    if not user:
        await add_user(message.from_user.id, text)
        await message.answer(f"✅ Зарегистрировал тебя как: {text}\nТеперь выбери свой статус:", reply_markup=status_kb)
        return

    # Проверка статуса
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

    # Сохраняем статус
    await update_status(user["id"], text)
    await message.answer(f"📌 Статус обновлён: {text}")

# ----- Админ команды -----
@dp.message(Command("history"))
async def admin_history(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    users = await get_all_users()
    msg = "\n".join([f"{u['full_name']}: {u.get('status','-')}" for u in users])
    await message.answer(msg or "Нет данных")

@dp.message(Command("users"))
async def admin_users(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    users = await get_all_users()
    msg = "\n".join([f"{u['id']} - {u['full_name']}" for u in users])
    await message.answer(msg or "Нет пользователей")

@dp.message(Command("status"))
async def admin_status(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Используй: /status [user_id]")
        return
    user_id = int(parts[1])
    user = await get_user(user_id)
    if not user:
        await message.answer("Пользователь не найден")
    else:
        await message.answer(f"{user['full_name']} - {user.get('status','-')}")

# ----- Ежедневное напоминание -----
async def send_daily_reminder():
    users = await get_all_users()
    for user in users:
        try:
            await bot.send_message(user["id"], "⏰ Пожалуйста, обнови свой статус на сегодня!", reply_markup=status_kb)
        except Exception:
            continue

# ----- Webhook -----
async def on_startup(app: web.Application):
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(WEBHOOK_URL)
    print(f"Webhook установлен: {WEBHOOK_URL}")

async def on_cleanup(app: web.Application):
    await bot.delete_webhook()
    await bot.session.close()

# ----- Главная функция -----
async def main():
    await init_db()

    # APScheduler
    scheduler = AsyncIOScheduler(timezone=timezone("Asia/Samarkand"))
    scheduler.add_job(send_daily_reminder, 'cron', hour=18, minute=0)
    scheduler.start()

    # Webhook через SimpleRequestHandler
    app = web.Application()
    SimpleRequestHandler(dp, bot=bot).register(app, path=WEBHOOK_PATH)
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"Webhook сервер запущен на порту {PORT}")

    # Держим цикл живым
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
