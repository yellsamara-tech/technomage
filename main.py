import os
import asyncio
from datetime import date
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pytz import timezone
from db import init_db, add_user, get_user, update_status, get_all_users

# ----- Переменные окружения -----
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"{os.getenv('RENDER_EXTERNAL_URL')}{WEBHOOK_PATH}"
PORT = int(os.getenv("PORT", 5000))

# ----- Горячие кнопки -----
status_kb = types.ReplyKeyboardMarkup(
    keyboard=[
        [types.KeyboardButton(text="✅ Работаю"), types.KeyboardButton(text="🤒 Болею")],
        [types.KeyboardButton(text="🏖 Отпуск"), types.KeyboardButton(text="✍️ Свой вариант")],
        [types.KeyboardButton(text="ℹ️ Проверить последний статус"), types.KeyboardButton(text="✏️ Изменить статус")]
    ],
    resize_keyboard=True
)

# ----- Хэндлеры -----
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    try:
        user = await get_user(message.from_user.id)
        if user:
            today = date.today()
            if user.get("status") and user.get("last_update") != today:
                await update_status(user["id"], user["status"])
            await message.answer(f"Ты уже зарегистрирован как: {user['full_name']}\nВыбери свой статус:", reply_markup=status_kb)
        else:
            await message.answer("Привет! Введи своё ФИО для регистрации.")
    except Exception as e:
        print(f"Ошибка в /start: {e}")

@dp.message()
async def process_message(message: types.Message):
    try:
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

    except Exception as e:
        print(f"Ошибка в process_message: {e}")

# ----- Ежедневное напоминание -----
async def send_daily_reminder():
    try:
        users = await get_all_users()
        for user in users:
            try:
                await bot.send_message(user["id"], "⏰ Пожалуйста, обнови свой статус на сегодня!", reply_markup=status_kb)
            except Exception as e:
                print(f"Не удалось отправить сообщение {user['id']}: {e}")
    except Exception as e:
        print(f"Ошибка в send_daily_reminder: {e}")

# ----- Webhook сервер -----
async def handle(request):
    update = types.Update(**await request.json())
    await dp.process_update(update)
    return web.Response()

async def on_startup(app):
    await bot.set_webhook(WEBHOOK_URL)
    print(f"Webhook установлен: {WEBHOOK_URL}")

async def on_cleanup(app):
    await bot.delete_webhook()

# ----- Запуск aiohttp без web.run_app -----
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

    # Планировщик APScheduler
    scheduler = AsyncIOScheduler(timezone=timezone("Asia/Samarkand"))
    scheduler.add_job(send_daily_reminder, 'cron', hour=18, minute=0)
    scheduler.start()

    # Запуск webhook + бот
    await asyncio.gather(
        start_webhook(),
        dp.start_polling(bot)  # polling на время разработки; можно оставить или заменить webhook полностью
    )

# ----- Запуск -----
if __name__ == "__main__":
    asyncio.run(main())
