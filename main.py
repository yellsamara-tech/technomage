
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

# ----- Жестко прописанные админы -----
ADMINS = [452908347]

# ----- Горячие кнопки пользователей -----
status_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✅ Работаю"), KeyboardButton(text="🤒 Болею")],
        [KeyboardButton(text="🏖 Отпуск"), KeyboardButton(text="✍️ Свой вариант")],
        [KeyboardButton(text="ℹ️ Проверить последний статус"), KeyboardButton(text="✏️ Изменить статус")]
    ],
    resize_keyboard=True
)

# ----- Клавиатура для админа (включает кнопки пользователя + админские) -----
admin_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✅ Работаю"), KeyboardButton(text="🤒 Болею")],
        [KeyboardButton(text="🏖 Отпуск"), KeyboardButton(text="✍️ Свой вариант")],
        [KeyboardButton(text="ℹ️ Проверить последний статус"), KeyboardButton(text="✏️ Изменить статус")],
        [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="🗂 История статусов")],
        [KeyboardButton(text="👥 Список пользователей"), KeyboardButton(text="🔑 Список админов")],
        [KeyboardButton(text="📢 Рассылка")]
    ],
    resize_keyboard=True
)

# ----- Состояние админа для рассылки -----
broadcast_state = {}  # {user_id: True}, если админ пишет текст для рассылки

# ----- Хэндлеры -----
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    user = await get_user(message.from_user.id)
    today = date.today()

    if message.from_user.id in ADMINS:
        kb = admin_kb
        text = "👋 Привет, админ! У тебя есть доступ к расширенной панели."
    else:
        kb = status_kb
        text = "👋 Привет! Добро пожаловать в бот статусов."

    if user:
        if user.get("status") and user.get("last_update") != today:
            await update_status(user["id"], user["status"])
        text += f"\nТы уже зарегистрирован как: {user['full_name']}"
        await message.answer(text, reply_markup=kb)
    else:
        text += "\nВведи своё ФИО для регистрации."
        await message.answer(text, reply_markup=kb)

@dp.message()
async def process_message(message: types.Message):
    user = await get_user(message.from_user.id)
    text = message.text.strip()

    # --- Если пользователь не зарегистрирован ---
    if not user:
        await add_user(message.from_user.id, text)
        await message.answer(f"✅ Зарегистрировал тебя как: {text}\nТеперь выбери свой статус:", reply_markup=status_kb)
        return

    # --- Админ в режиме рассылки ---
    if broadcast_state.get(message.from_user.id):
        users = await get_all_users()
        sent, failed = 0, 0
        for u in users:
            try:
                await bot.send_message(u["id"], f"📢 Админ сообщает:\n{text}")
                sent += 1
            except:
                failed += 1
        await message.answer(f"✅ Сообщение отправлено {sent} пользователям, ошибок: {failed}")
        broadcast_state[message.from_user.id] = False
        return

    # --- Админские кнопки ---
    if message.from_user.id in ADMINS:
        if text == "📊 Статистика":
            await admin_stats(message)
            return
        if text == "🗂 История статусов":
            await admin_history(message)
            return
        if text == "👥 Список пользователей":
            await admin_users(message)
            return
        if text == "🔑 Список админов":
            await admin_list(message)
            return
        if text == "📢 Рассылка":
            broadcast_state[message.from_user.id] = True
            await message.answer("✍️ Напиши текст для рассылки всем пользователям.")
            return

    # --- Пользовательские команды ---
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

# ----- Админские функции -----
async def admin_history(message: types.Message):
    users = await get_all_users()
    text = ""
    for u in users:
        history = await get_status_history(u["id"])
        hist_text = ", ".join([f"{h['status_date']}: {h['status']}" for h in history])
        text += f"{u['full_name']}: {hist_text}\n"
    await message.answer(text or "История пуста")

async def admin_users(message: types.Message):
    users = await get_all_users()
    text = "👥 Зарегистрированные пользователи:\n"
    for u in users:
        text += f"- {u['full_name']} (ID: {u['id']})\n"
    await message.answer(text)

async def admin_list(message: types.Message):
    text = "🔑 Администраторы:\n"
    for admin_id in ADMINS:
        text += f"- {admin_id}\n"
    await message.answer(text)

async def admin_stats(message: types.Message):
    users = await get_all_users()
    stats = {}
    for u in users:
        last_status = u.get("status") or "Не выбран"
        stats[last_status] = stats.get(last_status, 0) + 1

    text = "📊 Статистика текущих статусов:\n"
    for status, count in stats.items():
        text += f"- {status}: {count}\n"
    await message.answer(text)

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
