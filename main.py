import os
import asyncio
from datetime import date, datetime
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from db import (
    init_db, add_user, get_user, update_status,
    get_all_users, get_admins, make_admin, revoke_admin,
    get_status_history, delete_user
)

# ----- Переменные окружения -----
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден")

RENDER_URL = os.getenv("RENDER_EXTERNAL_URL")
if not RENDER_URL:
    raise ValueError("❌ RENDER_EXTERNAL_URL не найден")

PORT = int(os.getenv("PORT", 5000))
CREATOR_ID = int(os.getenv("CREATOR_ID", "0"))  # твой ID

# ----- Инициализация бота и диспетчера -----
storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)

WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"{RENDER_URL}{WEBHOOK_PATH}"

# ----- FSM состояния -----
class Registration(StatesGroup):
    waiting_for_fullname = State()
    waiting_for_tabel = State()

class Broadcast(StatesGroup):
    waiting_for_text = State()

# ----- Клавиатуры -----
user_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton("🟢 Я на работе (СП)"), KeyboardButton("🔴 Я болею (Б)")],
        [KeyboardButton("🕒 Я в дороге (СП)"), KeyboardButton("📌 У меня отгул (Вр)")],
        [KeyboardButton("ℹ️ Мой последний статус"), KeyboardButton("📊 Моя статистика")]
    ],
    resize_keyboard=True
)

admin_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton("📊 Посмотреть всех пользователей")],
        [KeyboardButton("👑 Назначить админа"), KeyboardButton("❌ Убрать админа")],
        [KeyboardButton("✉️ Сделать рассылку"), KeyboardButton("🗑 Удалить пользователя")],
        [KeyboardButton("📈 Статистика статусов за сегодня")]
    ],
    resize_keyboard=True
)

# ----- /start -----
@dp.message(commands=["start"])
async def cmd_start(message: types.Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer(
            "👋 Привет! Я твой рабочий помощник.\n"
            "Ты сможешь отмечать свой статус: работа, болезнь, дорога, отгул.\n"
            "Админы смогут видеть всех пользователей, рассылки и статистику.\n\n"
            "👉 Давай начнем регистрацию.\nВведи своё ФИО:"
        )
        await state.set_state(Registration.waiting_for_fullname)
    else:
        kb = admin_kb if user.get("is_admin") or message.from_user.id == CREATOR_ID else user_kb
        await message.answer("✅ Бот активен. Меню доступно ниже:", reply_markup=kb)

# ----- Регистрация -----
@dp.message(state=Registration.waiting_for_fullname)
async def reg_fullname(message: types.Message, state: FSMContext):
    await state.update_data(fullname=message.text)
    await message.answer("✍️ Теперь введи свой табельный номер:")
    await state.set_state(Registration.waiting_for_tabel)

@dp.message(state=Registration.waiting_for_tabel)
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
@dp.message(lambda m: m.text in ["🟢 Я на работе (СП)", "🔴 Я болею (Б)", "🕒 Я в дороге (СП)", "📌 У меня отгул (Вр)"])
async def set_user_status(message: types.Message):
    await update_status(message.from_user.id, message.text)
    await message.answer(f"✅ Твой статус обновлён: {message.text}")

# ----- Проверка своего статуса и статистика -----
@dp.message(lambda m: m.text == "ℹ️ Мой последний статус")
async def my_last_status(message: types.Message):
    user = await get_user(message.from_user.id)
    await message.answer(f"📌 Твой последний статус: {user.get('status') or 'ещё не выбран'}")

@dp.message(lambda m: m.text == "📊 Моя статистика")
async def my_status_stats(message: types.Message):
    history = await get_status_history(message.from_user.id)
    if not history:
        await message.answer("📌 История пуста")
        return
    text = "📊 Твоя история статусов:\n"
    for h in history:
        text += f"{h['status_date']}: {h['status']}\n"
    await message.answer(text)

# ----- Админские команды -----
@dp.message(lambda m: m.text == "📊 Посмотреть всех пользователей")
async def admin_show_users(message: types.Message):
    user = await get_user(message.from_user.id)
    if not user or (not user.get("is_admin") and message.from_user.id != CREATOR_ID):
        return
    users = await get_all_users()
    text = "👥 Все пользователи:\n"
    for u in users:
        text += f"{u['id']} | {u['full_name']} | {'🛡️ Админ' if u['is_admin'] else '👤 Пользователь'}\n"
    await message.answer(text)

# ----- Назначение и снятие админов -----
@dp.message(lambda m: m.text == "👑 Назначить админа")
async def admin_assign(message: types.Message):
    if message.from_user.id != CREATOR_ID:
        await message.answer("⛔ Только создатель может назначать админов")
        return
    users = await get_all_users()
    kb = InlineKeyboardMarkup(row_width=1)
    for u in users:
        if not u["is_admin"]:
            kb.add(InlineKeyboardButton(u["full_name"], callback_data=f"makeadmin_{u['id']}"))
    await message.answer("Выбери пользователя для назначения админом:", reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith("makeadmin_"))
async def callback_makeadmin(call: types.CallbackQuery):
    user_id = int(call.data.split("_")[1])
    await make_admin(user_id)
    user = await get_user(user_id)
    await call.message.answer(f"✅ Пользователь {user['full_name']} назначен админом.")
    await call.answer()

@dp.message(lambda m: m.text == "❌ Убрать админа")
async def admin_remove(message: types.Message):
    if message.from_user.id != CREATOR_ID:
        await message.answer("⛔ Только создатель может снимать админов")
        return
    admins = await get_admins()
    kb = InlineKeyboardMarkup(row_width=1)
    for u in admins:
        if u["id"] != CREATOR_ID:
            kb.add(InlineKeyboardButton(u["full_name"], callback_data=f"removeadmin_{u['id']}"))
    await message.answer("Выбери админа для снятия прав:", reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith("removeadmin_"))
async def callback_removeadmin(call: types.CallbackQuery):
    user_id = int(call.data.split("_")[1])
    await revoke_admin(user_id)
    await call.message.answer(f"✅ Пользователь {user_id} лишён прав админа.")
    await call.answer()

# ----- Удаление пользователя -----
@dp.message(lambda m: m.text == "🗑 Удалить пользователя")
async def admin_delete_user(message: types.Message):
    admins = await get_admins()
    if message.from_user.id != CREATOR_ID and message.from_user.id not in [a['id'] for a in admins]:
        return
    users = await get_all_users()
    kb = InlineKeyboardMarkup(row_width=1)
    for u in users:
        if u["id"] != CREATOR_ID:
            kb.add(InlineKeyboardButton(u["full_name"], callback_data=f"deluser_{u['id']}"))
    await message.answer("Выбери пользователя для удаления:", reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith("deluser_"))
async def callback_delete_user
