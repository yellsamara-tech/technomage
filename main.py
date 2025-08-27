import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor

from db import init_db, add_user, get_user, update_status, get_all_users, get_admins

logging.basicConfig(level=logging.INFO)

API_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# --- Константы ---
CREATOR_ID = 452908347

# --- Состояния ---
class Registration(StatesGroup):
    waiting_for_fullname = State()
    waiting_for_tabel = State()

class Broadcast(StatesGroup):
    waiting_for_text = State()

class AdminAssign(StatesGroup):
    waiting_for_user = State()
    waiting_for_remove = State()

# --- Кнопки ---
user_kb = ReplyKeyboardMarkup(resize_keyboard=True)
user_kb.add("🟢 Я на работе (СП)")
user_kb.add("🔴 Я болею (Б)")
user_kb.add("🕒 Я в дороге (СП)")
user_kb.add("📌 У меня отгул (Вр)")

admin_kb = ReplyKeyboardMarkup(resize_keyboard=True)
admin_kb.add("📊 Посмотреть всех пользователей")
admin_kb.add("👑 Назначить админа")
admin_kb.add("❌ Убрать админа")
admin_kb.add("✉️ Сделать рассылку")

# --- Старт ---
@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    if not user:
        await add_user(message.from_user.id, message.from_user.full_name, is_admin=(message.from_user.id == CREATOR_ID))
        await message.answer(
            "👋 Привет! Я твой рабочий помощник.\n\n"
            "Со мной ты сможешь отмечать свой статус: работа, отгул, дорога, болезнь.\n"
            "А админы смогут видеть всех сотрудников и делать рассылки.\n\n"
            "👉 Давай начнем регистрацию.\n\nВведи, пожалуйста, своё ФИО:"
        )
        await Registration.waiting_for_fullname.set()
    else:
        # Уже зарегистрирован
        if user["is_admin"]:
            kb = admin_kb
        else:
            kb = user_kb
        await message.answer("✅ Бот активен. Меню доступно ниже:", reply_markup=kb)

# --- Регистрация ---
@dp.message_handler(state=Registration.waiting_for_fullname)
async def process_fullname(message: types.Message, state: FSMContext):
    await state.update_data(fullname=message.text)
    await message.answer("✍️ Теперь введи свой табельный номер:")
    await Registration.waiting_for_tabel.set()

@dp.message_handler(state=Registration.waiting_for_tabel)
async def process_tabel(message: types.Message, state: FSMContext):
    data = await state.get_data()
    fullname = data["fullname"]
    tabel = message.text
    # сохраняем ФИО+табель (у тебя можно расширить db.py, тут просто имя сохраняем)
    await add_user(message.from_user.id, f"{fullname} ({tabel})", is_admin=(message.from_user.id == CREATOR_ID))
    await state.finish()
    kb = admin_kb if message.from_user.id == CREATOR_ID else user_kb
    await message.answer("✅ Регистрация завершена!\nТеперь выбери свой статус:", reply_markup=kb)

# --- Пользовательские статусы ---
@dp.message_handler(lambda m: m.text in [
    "🟢 Я на работе (СП)",
    "🔴 Я болею (Б)",
    "🕒 Я в дороге (СП)",
    "📌 У меня отгул (Вр)"
])
async def user_status(message: types.Message):
    await update_status(message.from_user.id, message.text)
    await message.answer(f"✅ Твой статус обновлён: {message.text}")

# --- Админские функции ---
@dp.message_handler(lambda m: m.text == "📊 Посмотреть всех пользователей")
async def show_users(message: types.Message):
    user = await get_user(message.from_user.id)
    if not user or not user["is_admin"]:
        return
    users = await get_all_users()
    text = "👥 Все пользователи:\n\n"
    for u in users:
        text += f"ID: {u['id']} | {u['full_name']} | {'🛡️ Админ' if u['is_admin'] else '👤 Пользователь'}\n"
    await message.answer(text)

# --- Назначение админа ---
@dp.message_handler(lambda m: m.text == "👑 Назначить админа")
async def assign_admin(message: types.Message):
    if message.from_user.id != CREATOR_ID:
        await message.answer("⛔ Только создатель может назначать админов.")
        return
    users = await get_all_users()
    kb = InlineKeyboardMarkup()
    for u in users:
        if not u["is_admin"]:
            kb.add(InlineKeyboardButton(u["full_name"], callback_data=f"makeadmin_{u['id']}"))
    await message.answer("Выбери пользователя для назначения админом:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("makeadmin_"))
async def make_admin(call: types.CallbackQuery):
    user_id = int(call.data.split("_")[1])
    conn = await get_user(user_id)
    if conn:
        from db import asyncpg, DB_URL
        db = await asyncpg.connect(DB_URL)
        await db.execute("UPDATE users SET is_admin=TRUE WHERE id=$1", user_id)
        await db.close()
        await call.message.answer(f"✅ Пользователь {conn['full_name']} назначен админом.")
    await call.answer()

# --- Удаление админа ---
@dp.message_handler(lambda m: m.text == "❌ Убрать админа")
async def remove_admin(message: types.Message):
    if message.from_user.id != CREATOR_ID:
        await message.answer("⛔ Только создатель может убирать админов.")
        return
    admins = await get_admins()
    kb = InlineKeyboardMarkup()
    for u in admins:
        if u["id"] != CREATOR_ID:
            kb.add(InlineKeyboardButton(u["full_name"], callback_data=f"removeadmin_{u['id']}"))
    await message.answer("Выбери админа для снятия полномочий:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("removeadmin_"))
async def do_remove_admin(call: types.CallbackQuery):
    user_id = int(call.data.split("_")[1])
    from db import asyncpg, DB_URL
    db = await asyncpg.connect(DB_URL)
    await db.execute("UPDATE users SET is_admin=FALSE WHERE id=$1", user_id)
    await db.close()
    await call.message.answer(f"✅ Пользователь {user_id} лишён прав админа.")
    await call.answer()

# --- Рассылка ---
@dp.message_handler(lambda m: m.text == "✉️ Сделать рассылку")
async def start_broadcast(message: types.Message):
    user = await get_user(message.from_user.id)
    if not user or not user["is_admin"]:
        return
    await message.answer("✍️ Напиши текст рассылки:")
    await Broadcast.waiting_for_text.set()

@dp.message_handler(state=Broadcast.waiting_for_text)
async def send_broadcast(message: types.Message, state: FSMContext):
    text = message.text
    users = await get_all_users()
    for u in users:
        try:
            await bot.send_message(u["id"], f"📢 Рассылка:\n\n{text}")
        except:
            pass
    await message.answer("✅ Рассылка завершена.")
    await state.finish()

# --- Запуск ---
async def on_startup(dp):
    await init_db()
    logging.info("Бот запущен!")

if __name__ == "__main__":
    executor.start_polling(dp, on_startup=on_startup)
