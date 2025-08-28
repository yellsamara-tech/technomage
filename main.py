import os
import asyncio
from datetime import date, datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiohttp import web
import asyncpg

# ===== Переменные окружения =====
BOT_TOKEN = os.getenv("BOT_TOKEN", "8304128948:AAGfzX5TIABL3DVKkmynWovRvEEVvtPsTzg")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://dia-804u.onrender.com")
PORT = int(os.getenv("PORT", 8000))
CREATOR_ID = int(os.getenv("CREATOR_ID", "0"))
DB_URL = os.getenv("DATABASE_URL")  # PostgreSQL URL

# ===== Инициализация =====
storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)
pool = None  # будет инициализирован в init_db()

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
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_statuses (
                user_id BIGINT,
                log_date DATE,
                status TEXT,
                PRIMARY KEY(user_id, log_date)
            );
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

# ===== Админские функции =====

# Показать всех пользователей
@dp.message(lambda m: m.text == "📊 Посмотреть всех пользователей")
async def admin_show_users(message: types.Message):
    user = await get_user(message.from_user.id)
    if not user or (not user["is_admin"] and message.from_user.id != CREATOR_ID):
        return
    users = await get_all_users()
    text = "👥 Все пользователи:\n"
    for u in users:
        text += f"{u['user_id']} | {u['full_name']} | {'🛡️ Админ' if u['is_admin'] else '👤 Пользователь'}\n"
    await message.answer(text)

# Назначение админа
@dp.message(lambda m: m.text == "👑 Назначить админа")
async def admin_assign(message: types.Message):
    if message.from_user.id != CREATOR_ID:
        await message.answer("⛔ Только создатель может назначать админов")
        return
    users = await get_all_users()
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=u["full_name"], callback_data=f"makeadmin_{u['user_id']}")]
                         for u in users if not u["is_admin"]]
    )
    await message.answer("Выбери пользователя для назначения админом:", reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith("makeadmin_"))
async def callback_makeadmin(call: types.CallbackQuery):
    user_id = int(call.data.split("_")[1])
    await make_admin(user_id)
    user = await get_user(user_id)
    await call.message.answer(f"✅ Пользователь {user['full_name']} назначен админом.")
    await call.answer()

# Снятие админа
@dp.message(lambda m: m.text == "❌ Убрать админа")
async def admin_remove(message: types.Message):
    if message.from_user.id != CREATOR_ID:
        await message.answer("⛔ Только создатель может снимать админов")
        return
    admins = [u for u in await get_all_users() if u["is_admin"] and u["user_id"] != CREATOR_ID]
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=u["full_name"], callback_data=f"removeadmin_{u['user_id']}")] for u in admins]
    )
    await message.answer("Выбери админа для снятия прав:", reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith("removeadmin_"))
async def callback_removeadmin(call: types.CallbackQuery):
    user_id = int(call.data.split("_")[1])
    await revoke_admin(user_id)
    await call.message.answer(f"✅ Пользователь {user_id} лишён прав админа.")
    await call.answer()

# Удаление пользователя
@dp.message(lambda m: m.text == "🗑 Удалить пользователя")
async def admin_delete_user(message: types.Message):
    user = await get_user(message.from_user.id)
    if not user or (not user["is_admin"] and message.from_user.id != CREATOR_ID):
        return
    users = [u for u in await get_all_users() if u["user_id"] != CREATOR_ID and not u["is_admin"]]
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=u["full_name"], callback_data=f"deleteuser_{u['user_id']}")] for u in users]
    )
    await message.answer("Выбери пользователя для удаления:", reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith("deleteuser_"))
async def callback_delete_user(call: types.CallbackQuery):
    user_id = int(call.data.split("_")[1])
    await delete_user(user_id)
    await call.message.answer(f"✅ Пользователь {user_id} удалён.")
    await call.answer()

# Рассылка
@dp.message(lambda m: m.text == "✉️ Сделать рассылку")
async def admin_broadcast(message: types.Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    if not user or (not user["is_admin"] and message.from_user.id != CREATOR_ID):
        return
    await message.answer("✍️ Напиши текст рассылки:")
    await state.set_state(Broadcast.waiting_for_text)

@dp.message(Broadcast.waiting_for_text)
async def send_broadcast(message: types.Message, state: FSMContext):
    text = message.text
    users = await get_all_users()
    success = 0
    fail = 0
    for u in users:
        try:
            await bot.send_message(u["user_id"], f"📢 Рассылка:\n\n{text}")
            success += 1
        except:
            fail += 1
    await message.answer(f"✅ Рассылка завершена.\nУспешно: {success}, Ошибки: {fail}")
    await state.clear()

# Статистика статусов
@dp.message(lambda m: m.text == "📈 Статистика статусов")
async def admin_status_stats(message: types.Message):
    user = await get_user(message.from_user.id)
    if not user or (not user["is_admin"] and message.from_user.id != CREATOR_ID):
        return
    today = date.today()
    users = await get_all_users()
    text = f"📊 Статистика статусов на {today}:\n"
    for u in users:
        history = await get_status_history(u["user_id"], today)
        status = history[-1]["status"] if history else "Не установлен"
        text += f"{u['full_name']}: {status}\n"
    await message.answer(text)

# ===== Webhook через aiohttp =====
async def handle(request: web.Request):
    data = await request.json()
    update = types.Update(**data)
    await dp.feed_update(bot, update)
    return web.Response()

app = web.Application()
app.router.add_post(f"/{BOT_TOKEN}", handle)

async def on_startup():
    await init_db()
    await bot.set_webhook(f"{WEBHOOK_URL}/{BOT_TOKEN}")

async def on_shutdown():
    await bot.delete_webhook()
    await bot.session.close()

if __name__ == "__main__":
    web.run_app(app, port=PORT, print=None)
