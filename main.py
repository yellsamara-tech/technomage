import os
import asyncio
from datetime import date, datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, Update
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiohttp import web
import asyncpg

# ===== Переменные окружения =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
CREATOR_ID = int(os.getenv("CREATOR_ID", 0))
DB_URL = os.getenv("DATABASE_URL")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", 8000))

if not BOT_TOKEN or not DB_URL or not WEBHOOK_URL:
    raise ValueError("Не указаны обязательные переменные окружения BOT_TOKEN, DATABASE_URL, WEBHOOK_URL")

# ===== Инициализация =====
storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)
pool = None

# ===== FSM состояния =====
class Registration(StatesGroup):
    waiting_for_fullname = State()
    waiting_for_tabel = State()
    waiting_for_phone = State()

class Broadcast(StatesGroup):
    waiting_for_text = State()

# ===== Статусы =====
statuses = ["🟢 Я на работе (СП)", "🔴 Я болею (Б)", "🕒 Я в дороге (СП)", "📌 У меня отгул (Вр)"]

# ===== Клавиатуры =====
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
        [KeyboardButton(text="✉️ Сделать рассылку"), KeyboardButton(text="📈 Статистика статусов")]
    ],
    resize_keyboard=True
)

# ===== Инициализация базы =====
async def init_db():
    global pool
    pool = await asyncpg.create_pool(DB_URL)
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                full_name TEXT,
                tab_number TEXT,
                phone TEXT,
                is_admin BOOLEAN DEFAULT FALSE
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_statuses (
                user_id BIGINT,
                log_date DATE,
                status TEXT,
                PRIMARY KEY(user_id, log_date)
            )
        """)

# ===== Функции работы с БД =====
async def add_user(user_id, full_name, tab_number="", phone="", is_admin=False):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users(user_id, full_name, tab_number, phone, is_admin)
            VALUES($1,$2,$3,$4,$5) ON CONFLICT(user_id) DO NOTHING
        """, user_id, full_name, tab_number, phone, is_admin)

async def get_user(user_id):
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM users WHERE user_id=$1", user_id)

async def get_all_users():
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM users ORDER BY full_name")

async def make_admin(user_id):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET is_admin=TRUE WHERE user_id=$1", user_id)

async def revoke_admin(user_id):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET is_admin=FALSE WHERE user_id=$1", user_id)

async def delete_user(user_id):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM users WHERE user_id=$1", user_id)
        await conn.execute("DELETE FROM user_statuses WHERE user_id=$1", user_id)

async def update_status(user_id, status, log_date=None):
    log_date = log_date or date.today()
    if isinstance(log_date, str):
        log_date = datetime.strptime(log_date, "%Y-%m-%d").date()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO user_statuses(user_id, log_date, status)
            VALUES($1,$2,$3)
            ON CONFLICT(user_id, log_date) DO UPDATE SET status=EXCLUDED.status
        """, user_id, log_date, status)

async def get_status_history(user_id, log_date=None):
    async with pool.acquire() as conn:
        if log_date:
            if isinstance(log_date, str):
                log_date = datetime.strptime(log_date, "%Y-%m-%d").date()
            return await conn.fetch("SELECT * FROM user_statuses WHERE user_id=$1 AND log_date=$2", user_id, log_date)
        return await conn.fetch("SELECT * FROM user_statuses WHERE user_id=$1 ORDER BY log_date", user_id)

# ===== Обработчики =====
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer("👋 Привет! Давай зарегистрируемся.\nВведи своё ФИО:")
        await state.set_state(Registration.waiting_for_fullname)
    else:
        kb = admin_kb if user["is_admin"] or message.from_user.id == CREATOR_ID else user_kb
        await message.answer("✅ Бот активен. Меню доступно ниже:", reply_markup=kb)

@dp.message(Registration.waiting_for_fullname)
async def reg_fullname(message: types.Message, state: FSMContext):
    await state.update_data(fullname=message.text)
    await message.answer("✍️ Теперь введи свой табельный номер:")
    await state.set_state(Registration.waiting_for_tabel)

@dp.message(Registration.waiting_for_tabel)
async def reg_tabel(message: types.Message, state: FSMContext):
    await state.update_data(tabel=message.text)
    await message.answer("📱 Теперь введи номер телефона:")
    await state.set_state(Registration.waiting_for_phone)

@dp.message(Registration.waiting_for_phone)
async def reg_phone(message: types.Message, state: FSMContext):
    data = await state.get_data()
    fullname = data["fullname"]
    tabel = data["tabel"]
    phone = message.text
    is_admin = message.from_user.id == CREATOR_ID
    await add_user(message.from_user.id, f"{fullname} ({tabel})", tabel, phone, is_admin)
    await state.clear()
    kb = admin_kb if is_admin else user_kb
    await message.answer("✅ Регистрация завершена! Выбери статус:", reply_markup=kb)

@dp.message(lambda m: m.text in statuses)
async def set_user_status(message: types.Message):
    await update_status(message.from_user.id, message.text)
    await message.answer(f"✅ Твой статус обновлён: {message.text}")

# ===== Webhook =====
async def handle(request: web.Request):
    if request.method == "POST":
        data = await request.json()
        update = Update(**data)
        await dp.feed_update(bot, update)
        return web.Response()
    return web.Response(status=405)

# ===== Запуск =====
app = web.Application()
app.router.add_post(f"/{BOT_TOKEN}", handle)

async def on_startup():
    await init_db()
    await bot.delete_webhook()
    await bot.set_webhook(f"{WEBHOOK_URL}/{BOT_TOKEN}")
    print("✅ Webhook установлен, бот готов!")

async def on_shutdown():
    await bot.delete_webhook()
    await bot.session.close()

if __name__ == "__main__":
    web.run_app(app, port=PORT)
