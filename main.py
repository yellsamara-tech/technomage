import os
import asyncio
from datetime import date
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pytz import timezone
from db import init_db, add_user, get_user, update_status, get_all_users, get_status_history, find_user_by_name, get_admins, set_user_status

import nest_asyncio
nest_asyncio.apply()  # для Render

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

# ----- Клавиатура -----
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
            await message.answer(
                f"Ты уже зарегистрирован как: {user['full_name']}\nВыбери свой статус:", 
                reply_markup=status_kb
            )
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

# ----- Админ команды -----
@dp.message(Command("history"))
async def history_handler(message: types.Message):
    try:
        user = await get_user(message.from_user.id)
        if not user or not user.get("is_admin"):
            await message.answer("❌ Только для админов")
            return
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.answer("Использование: /history <ФИО пользователя>")
            return
        name = parts[1]
        rows = await find_user_by_name(name)
        if not rows:
            await message.answer("Пользователь не найден")
            return
        for u in rows:
            history = await get_status_history(u["id"])
            text = "\n".join([f"{r['status_date']}: {r['status']}" for r in history]) or "Нет статусов"
            await message.answer(f"История статусов {u['full_name']}:\n{text}")
    except Exception as e:
        print(f"Ошибка в /history: {e}")

@dp.message(Command("admins"))
async def admins_handler(message: types.Message):
    try:
        admins = await get_admins()
        text = "\n".join([f"{a['full_name']} (ID: {a['id']})" for a in admins]) or "Нет админов"
        await message.answer(f"Список админов:\n{text}")
    except Exception as e:
        print(f"Ошибка в /admins: {e}")

@dp.message(Command("find"))
async def find_handler(message: types.Message):
    try:
        user = await get_user(message.from_user.id)
        if not user or not user.get("is_admin"):
            await message.answer("❌ Только для админов")
            return
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.answer("Использование: /find <ФИО>")
            return
        name = parts[1]
        rows = await find_user_by_name(name)
        if not rows:
            await message.answer("Пользователь не найден")
            return
        for u in rows:
            await message.answer(f"Найден пользователь: {u['full_name']} (ID: {u['id']}) Статус: {u.get('status')}")
    except Exception as e:
        print(f"Ошибка в /find: {e}")

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
    data = await request.json()
    update = types.Update(**data)
    # для aiogram 3.x используем feed_update
    await dp.feed_update(update)
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

    # Планировщик APScheduler
    scheduler = AsyncIOScheduler(timezone=timezone("Asia/Samarkand"))
    scheduler.add_job(send_daily_reminder, 'cron', hour=18, minute=0)
    scheduler.start()

    # Запуск webhook
    await start_webhook()

    # Держим цикл живым
    while True:
        await asyncio.sleep(3600)

# ----- Запуск -----
if __name__ == "__main__":
    asyncio.run(main())
