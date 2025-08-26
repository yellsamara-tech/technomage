import os
import asyncio
from datetime import date
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pytz import timezone
from db import init_db, add_user, get_user, update_status, get_all_users, get_status_history, find_user_by_name, get_admins, set_user_status

import nest_asyncio
nest_asyncio.apply()  # важно для Render

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
    user = await get_user(message.from_user.id)
    today = date.today()
    if user:
        if user.get("status") and str(user.get("last_update")) != str(today):
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

    # Регистрация
    if not user:
        await add_user(message.from_user.id, text)
        await message.answer(f"✅ Зарегистрировал тебя как: {text}\nТеперь выбери свой статус:", reply_markup=status_kb)
        return

    # Проверка статуса
    if text == "ℹ️ Проверить последний статус":
        last_status = user.get("status") or "ещё не выбран"
        await message.answer(f"📌 Твой последний статус: {last_status}")
        return

    # Изменение статуса
    if text == "✏️ Изменить статус":
        await message.answer("Выбери новый статус или напиши свой текстом 👇", reply_markup=status_kb)
        return

    if text == "✍️ Свой вариант":
        await message.answer("Напиши свой статус сообщением 👇")
        return

    # Обновление статуса
    await update_status(user["id"], text)
    await message.answer(f"📌 Статус обновлён: {text}")

# ----- Команды админа -----
@dp.message(Command("history"))
async def history_handler(message: types.Message):
    admins = await get_admins()
    if not any(a["id"] == message.from_user.id for a in admins):
        await message.answer("❌ У вас нет прав для этой команды.")
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Использование: /history <ФИО>")
        return
    name = args[1]
    users = await find_user_by_name(name)
    if not users:
        await message.answer("Пользователь не найден.")
        return
    text = ""
    for u in users:
        history = await get_status_history(u["id"])
        text += f"Статусы {u['full_name']}:\n"
        for h in history:
            text += f"{h['status_date']}: {h['status']}\n"
        text += "\n"
    await message.answer(text)

@dp.message(Command("users"))
async def users_handler(message: types.Message):
    admins = await get_admins()
    if not any(a["id"] == message.from_user.id for a in admins):
        await message.answer("❌ У вас нет прав для этой команды.")
        return
    users = await get_all_users()
    text = "Список пользователей:\n"
    for u in users:
        text += f"{u['full_name']} — {u['status'] or 'нет статуса'}\n"
    await message.answer(text)

# ----- Ежедневное напоминание -----
async def send_daily_reminder():
    users = await get_all_users()
    for user in users:
        try:
            await bot.send_message(user["id"], "⏰ Пожалуйста, обнови свой статус на сегодня!", reply_markup=status_kb)
        except:
            continue

# ----- Webhook -----
async def handle(request):
    data = await request.json()
    update = types.Update(**data)
    # ⚡ Важное изменение: feed_update вызываем как classmethod
    await Dispatcher.feed_update(dp, update)
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
    loop = asyncio.get_event_loop()
    loop.create_task(main())
    print("Бот запущен. Webhook сервер работает...")
    loop.run_forever()
