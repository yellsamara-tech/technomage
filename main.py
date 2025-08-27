import os
import asyncio
from datetime import datetime, date, time, timedelta
import pytz
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiohttp import web
from db import (
    init_db, add_user, get_user, update_status, get_all_users,
    get_admins, make_admin, revoke_admin, delete_user, get_status_history, get_users_without_status_today
)

# ----- Переменные окружения -----
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден")

CREATOR_ID = int(os.getenv("CREATOR_ID", "0"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Например: https://your-domain.com/webhook
PORT = int(os.getenv("PORT", 8000))     # Render предоставляет порт через переменные окружения
SAMARA_TZ = pytz.timezone("Europe/Samara")

# ----- Инициализация -----
storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)

# ----- FSM состояния -----
class Registration(StatesGroup):
    waiting_for_fullname = State()
    waiting_for_tabel = State()

class Broadcast(StatesGroup):
    waiting_for_text = State()

# ----- Клавиатуры -----
statuses = ["🟢 Я на работе (СП)", "🔴 Я болею (Б)", "🕒 Я в дороге (СП)", "📌 У меня отгул (Вр)"]

user_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=statuses[0]), KeyboardButton(text=statuses[1])],
        [KeyboardButton(text=statuses[2]), KeyboardButton(text=statuses[3])]
    ],
    resize_keyboard=True
)

admin_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📊 Посмотреть всех пользователей")],
        [KeyboardButton(text="👑 Назначить админа"), KeyboardButton(text="❌ Убрать админа"), KeyboardButton(text="🗑 Удалить пользователя")],
        [KeyboardButton(text="✉️ Сделать рассылку"), KeyboardButton(text="📈 Статистика статусов"), KeyboardButton(text="🗂 История статусов")]
    ],
    resize_keyboard=True
)

# ----- /start -----
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer(
            "👋 Привет! Я твой рабочий помощник.\n"
            "Ты сможешь отмечать свой статус: работа, болезнь, дорога, отгул.\n"
            "Админы смогут видеть всех пользователей и делать рассылки.\n\n"
            "👉 Давай начнем регистрацию.\nВведи своё ФИО:"
        )
        await state.set_state(Registration.waiting_for_fullname)
    else:
        kb = admin_kb if user.get("is_admin") or message.from_user.id == CREATOR_ID else user_kb
        await message.answer("✅ Бот активен. Меню доступно ниже:", reply_markup=kb)

# ----- Регистрация -----
@dp.message(Registration.waiting_for_fullname)
async def reg_fullname(message: types.Message, state: FSMContext):
    await state.update_data(fullname=message.text)
    await message.answer("✍️ Теперь введи свой табельный номер:")
    await state.set_state(Registration.waiting_for_tabel)

@dp.message(Registration.waiting_for_tabel)
async def reg_tabel(message: types.Message, state: FSMContext):
    data = await state.get_data()
    fullname = data["fullname"]
    tabel = message.text
    is_admin = message.from_user.id == CREATOR_ID
    await add_user(message.from_user.id, f"{fullname} ({tabel})", is_admin=is_admin)
    await state.clear()
    kb = admin_kb if is_admin else user_kb
    await message.answer("✅ Регистрация завершена! Выбери статус:", reply_markup=kb)

# ----- Пользовательские статусы -----
@dp.message(lambda m: m.text in statuses)
async def set_user_status(message: types.Message):
    await update_status(message.from_user.id, message.text)
    await message.answer(f"✅ Твой статус обновлён: {message.text}")

# ----- Админские команды -----
async def is_admin_or_creator(user_id: int):
    user = await get_user(user_id)
    return user and (user.get("is_admin") or user_id == CREATOR_ID)

# Просмотр всех пользователей
@dp.message(lambda m: m.text == "📊 Посмотреть всех пользователей")
async def admin_show_users(message: types.Message):
    if not await is_admin_or_creator(message.from_user.id):
        return
    users = await get_all_users()
    text = "👥 Все пользователи:\n" + "\n".join(
        f"{u['id']} | {u['full_name']} | {'🛡️ Админ' if u['is_admin'] else '👤 Пользователь'}" for u in users
    )
    await message.answer(text)

# История статусов
@dp.message(lambda m: m.text == "🗂 История статусов")
async def admin_status_history(message: types.Message):
    if not await is_admin_or_creator(message.from_user.id):
        return
    users = await get_all_users()
    text = "📜 История статусов пользователей:\n"
    for u in users:
        history = await get_status_history(u["id"])
        text += f"{u['full_name']}:\n"
        for record in history:
            text += f"  {record['date']} — {record['status']}\n"
    await message.answer(text)

# ----- Напоминания в 18:00 (самарское время) -----
async def daily_reminder():
    while True:
        now = datetime.now(SAMARA_TZ)
        target = datetime.combine(now.date(), time(18, 0, 0, tzinfo=SAMARA_TZ))
        if now > target:
            target += timedelta(days=1)
        await asyncio.sleep((target - now).total_seconds())
        
        users_to_remind = await get_users_without_status_today()
        for u in users_to_remind:
            try:
                await bot.send_message(u["id"], "⏰ Не забывай отметить свой статус за сегодня!")
            except:
                pass

# ----- Webhook -----
async def handle(request):
    update = types.Update(**await request.json())
    await dp.feed_update(bot, update)
    return web.Response()

async def on_startup(app):
    await init_db()
    await bot.delete_webhook()
    await bot.set_webhook(WEBHOOK_URL)
    asyncio.create_task(daily_reminder())
    print("Бот запущен на webhook!")

app = web.Application()
app.router.add_post("/webhook", handle)
app.on_startup.append(on_startup)

if __name__ == "__main__":
    web.run_app(app, port=PORT)
