import os
import asyncio
from datetime import date
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pytz import timezone
from db import init_db, add_user, get_user, update_status, get_all_users, get_status_history, find_user_by_name, set_user_status, get_admins

import nest_asyncio
nest_asyncio.apply()  # нужно для Render

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

        # Регистрация нового пользователя
        if not user:
            await add_user(message.from_user.id, text)
            await message.answer(f"✅ Зарегистрировал тебя как: {text}\nТеперь выбери свой статус:", reply_markup=status_kb)
            return

        # Проверка последнего статуса
        if text == "ℹ️ Проверить последний статус":
            last_status = user.get("status") or "ещё не выбран"
            await message.answer(f"📌 Твой последний статус: {last_status}")
            return

        # Изменение статуса
        if text == "✏️ Изменить статус":
            await message.answer("Выбери новый статус или напиши свой текстом 👇", reply_markup=status_kb)
            return

        # Свой вариант статуса
        if text == "✍️ Свой вариант":
            await message.answer("Напиши свой статус сообщением 👇")
            return

        # Обновление статуса
        await update_status(user["id"], text)
        await message.answer(f"📌 Статус обновлён: {text}")

        # ----- Админ команды -----
        if user.get("is_admin"):
            if text.startswith("/история"):
                parts = text.split(maxsplit=1)
                if len(parts) == 2:
                    target_name = parts[1]
                    found_users = await find_user_by_name(target_name)
                    if not found_users:
                        await message.answer("Пользователь не найден")
                        return
                    for u in found_users:
                        history = await get_status_history(u["id"])
                        msg = f"История статусов {u['full_name']}:\n"
                        for h in history:
                            msg += f"{h['status_date']}: {h['status']}\n"
                        await message.answer(msg)
                else:
                    await message.answer("Использование: /история ФИО")
            elif text.startswith("/статус"):
                parts = text.split(maxsplit=2)
                if len(parts) == 3:
                    target_name, new_status = parts[1], parts[2]
                    found_users = await find_user_by_name(target_name)
                    if not found_users:
                        await message.answer("Пользователь не найден")
                        return
                    for u in found_users:
                        await set_user_status(u["id"], new_status)
                    await message.answer(f"Статус обновлён для {target_name} на '{new_status}'")
                else:
                    await message.answer("Использование: /статус ФИО НовыйСтатус")

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
    try:
        data = await request.json()
        update = types.Update(**data)
        await dp.update(bot, update)  # правильный метод для aiogram 3.x
        return web.Response()
    except Exception as e:
        print(f"Ошибка в webhook handle: {e}")
        return web.Response(status=500, text=str(e))

async def on_startup(app):
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(WEBHOOK_URL)
    print(f"Webhook установлен: {WEBHOOK_URL}")

async def on_cleanup(app):
    await bot.delete_webhook()
    await bot.session.close()  # закрываем сессию

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
