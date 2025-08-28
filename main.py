import os
import asyncio
from datetime import date, datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiohttp import web
import asyncpg

# ===== Переменные окружения =====
BOT_TOKEN = os.getenv("BOT_TOKEN", "8304128948:AAGfzX5TIABL3DVKkmynWovRvEEVvtPsTzg")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://dia-804u.onrender.com")
PORT = int(os.getenv("PORT", 8000))
CREATOR_ID = int(os.getenv("CREATOR_ID", "452908347"))
DB_URL = os.getenv("DATABASE_URL")

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

class AdminActions(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_message = State()

# ===== Статусы =====
statuses = ["🟢 На работе (СП)", "🔴 Болезнь (Б)", "🕒 В дороге (СП)", "📌 Отгул (Вр)"]

# ===== Клавиатуры =====
user_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(statuses[0]), KeyboardButton(statuses[1])],
        [KeyboardButton(statuses[2]), KeyboardButton(statuses[3])]
    ],
    resize_keyboard=True
)

admin_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton("📊 Посмотреть всех пользователей")],
        [KeyboardButton("👑 Назначить админа"), KeyboardButton("❌ Убрать админа"), KeyboardButton("🗑 Удалить пользователя")],
        [KeyboardButton("✉️ Сделать рассылку"), KeyboardButton("📈 Статистика статусов")]
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

# ===== Админ функции =====
@dp.message(lambda m: m.text in ["📊 Посмотреть всех пользователей"] and (m.from_user.id==CREATOR_ID))
async def view_all_users(message: types.Message):
    users = await get_all_users()
    text = "\n".join([f"{u['full_name']} - {'Админ' if u['is_admin'] else 'Пользователь'}" for u in users])
    await message.answer(f"👥 Список пользователей:\n{text}")

@dp.message(lambda m: m.text in ["👑 Назначить админа"])
async def cmd_make_admin(message: types.Message, state: FSMContext):
    await message.answer("Введите user_id пользователя для назначения админом:")
    await state.set_state(AdminActions.waiting_for_user_id)
    await state.update_data(action="make_admin")

@dp.message(lambda m: m.text in ["❌ Убрать админа"])
async def cmd_revoke_admin(message: types.Message, state: FSMContext):
    await message.answer("Введите user_id пользователя для снятия админа:")
    await state.set_state(AdminActions.waiting_for_user_id)
    await state.update_data(action="revoke_admin")

@dp.message(lambda m: m.text in ["🗑 Удалить пользователя"])
async def cmd_delete_user(message: types.Message, state: FSMContext):
    await message.answer("Введите user_id пользователя для удаления:")
    await state.set_state(AdminActions.waiting_for_user_id)
    await state.update_data(action="delete_user")

@dp.message(AdminActions.waiting_for_user_id)
async def handle_admin_user_id(message: types.Message, state: FSMContext):
    data = await state.get_data()
    action = data["action"]
    user_id = int(message.text)
    if action=="make_admin":
        await make_admin(user_id)
        await message.answer("✅ Пользователь назначен админом")
    elif action=="revoke_admin":
        await revoke_admin(user_id)
        await message.answer("✅ Админские права сняты")
    elif action=="delete_user":
        await delete_user(user_id)
        await message.answer("✅ Пользователь удалён")
    await state.clear()

@dp.message(lambda m: m.text in ["✉️ Сделать рассылку"])
async def cmd_broadcast(message: types.Message, state: FSMContext):
    await message.answer("Введите текст рассылки:")
    await state.set_state(AdminActions.waiting_for_message)

@dp.message(AdminActions.waiting_for_message)
async def handle_broadcast(message: types.Message, state: FSMContext):
    users = await get_all_users()
    count = 0
    for u in users:
        try:
            await bot.send_message(u["user_id"], message.text)
            count += 1
        except:
            pass
    await message.answer(f"✅ Рассылка выполнена. Сообщение отправлено {count} пользователям.")
    await state.clear()

@dp.message(lambda m: m.text in ["📈 Статистика статусов"])
async def cmd_status_stats(message: types.Message):
    today = date.today()
    users = await get_all_users()
    stats = {}
    for status in statuses:
        stats[status] = 0
    for u in users:
        rows = await get_status_history(u["user_id"], today)
        if rows:
            stats[rows[0]["status"]] +=1
    text = "\n".join([f"{k}: {v}" for k,v in stats.items()])
    await message.answer(f"📊 Статистика на {today}:\n{text}")

# ===== Webhook =====
async def handle(request: web.Request):
    if request.method == "POST":
        data = await request.json()
        update = types.Update(**data)
        await dp.feed_update(bot, update)
        return web.Response()
    return web.Response(status=405)

# ===== Запуск веб-сервера =====
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
    web.run_app(app, port=PORT, on_startup=[on_startup], on_shutdown=[on_shutdown])
