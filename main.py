import os
import asyncio
from datetime import date
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pytz import timezone
from db import init_db, add_user, get_user, update_status, get_all_users, get_admins, get_status_history

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
        [KeyboardButton(text="✅ Работаю"), KeyboardButton(text="🤒 Болею")],
        [KeyboardButton(text="🏖 Отпуск"), KeyboardButton(text="✍️ Свой вариант")],
        [KeyboardButton(text="ℹ️ Проверить последний статус"), KeyboardButton(text="✏️ Изменить статус")]
    ],
    resize_keyboard=True
)

# ----- Хэндлеры -----
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

    await update_status(user["id"], text)
    await message.answer(f"📌 Статус обновлён: {text}")

# ----- Админские команды -----
@dp.message(Command("history"))
async def admin_history(message: types.Message):
    admins = await get_admins()
    if message.from_user.id not in [a["id"] for a in admins]:
        await message.answer("❌ У вас нет прав")
        return

    users = await get_all_users()
    text = ""
    for u in users:
        history = await get_status_history(u["id"])
        hist_text = ", ".join([f"{h['status_date']}: {h['status']}" for h in history])
        text += f"{u['full_name']}: {hist_text}\n"
    await message.answer(text or "История пуста")

# ----- Ежедневное напоминание -----
async def send_daily_reminder():
    users = await get_all_users()
    for user in users:
        try:
            await bot.send_message(user["id"], "⏰ Пожалуйста, обнови свой статус на сегодня!", reply_markup=status_kb)
        except Exception as e:
            print(f"Не удалось отправить сообщение {user['id']}: {e}")

# ----- Webhook сервер -----
async def handle(request):
    data = await request.json()
    update = types.Update(**data)
    await dp.feed_update(bot, update)
  # <- используем метод Aiogram 3.x
    return web.Response()

async def on_startup(app):
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(WEBHOOK_URL)
    print(f"Webhook установлен: {WEBHOOK_URL}")

async def on_cleanup(app):
    await bot.delete_webhook()
    await bot.session.close()

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

# ----- Главная функция -----
async def main():
    await init_db()
    scheduler = AsyncIOScheduler(timezone=timezone("Asia/Samarkand"))
    scheduler.add_job(send_daily_reminder, 'cron', hour=18, minute=0)
    scheduler.start()
    await start_webhook()
    while True:
        await asyncio.sleep(3600)

# ----- Запуск -----
if __name__ == "__main__":
    asyncio.run(main())
