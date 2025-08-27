import os
import asyncio
from datetime import date
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from db import init_db, add_user, get_user, update_status, get_all_users, get_admins, make_admin, revoke_admin

# --- Переменные окружения ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден")

CREATOR_ID = int(os.getenv("CREATOR_ID", "0"))  # твой ID из Environment

# --- Инициализация бота и dispatcher ---
storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)

# --- FSM состояния ---
class Registration(StatesGroup):
    waiting_for_fullname = State()
    waiting_for_tabel = State()

class Broadcast(StatesGroup):
    waiting_for_text = State()

# --- Клавиатуры ---
user_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🟢 Я на работе (СП)"), KeyboardButton(text="🔴 Я болею (Б)")],
        [KeyboardButton(text="🕒 Я в дороге (СП)"), KeyboardButton(text="📌 У меня отгул (Вр)")]
    ],
    resize_keyboard=True
)

admin_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📊 Посмотреть всех пользователей")],
        [KeyboardButton(text="👑 Назначить админа"), KeyboardButton(text="❌ Убрать админа")],
        [KeyboardButton(text="✉️ Сделать рассылку")]
    ],
    resize_keyboard=True
)

# --- /start ---
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

# --- Регистрация ---
@dp.message(lambda m: m.text and m.text.strip() and m.get_current().state == Registration.waiting_for_fullname.state)
async def reg_fullname(message: types.Message, state: FSMContext):
    await state.update_data(fullname=message.text.strip())
    await message.answer("✍️ Теперь введи свой табельный номер:")
    await state.set_state(Registration.waiting_for_tabel)

@dp.message(lambda m: m.text and m.text.strip() and m.get_current().state == Registration.waiting_for_tabel.state)
async def reg_tabel(message: types.Message, state: FSMContext):
    data = await state.get_data()
    fullname = data["fullname"]
    tabel = message.text.strip()
    is_admin = message.from_user.id == CREATOR_ID
    await add_user(message.from_user.id, f"{fullname} ({tabel})", is_admin=is_admin)
    await state.clear()
    kb = admin_kb if is_admin else user_kb
    await message.answer("✅ Регистрация завершена! Выбери статус:", reply_markup=kb)

# --- Пользовательские статусы ---
@dp.message(lambda m: m.text and m.text.startswith(("🟢", "🔴", "🕒", "📌")))
async def set_user_status(message: types.Message):
    await update_status(message.from_user.id, message.text)
    await message.answer(f"✅ Твой статус обновлён: {message.text}")

# --- Админские команды ---
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

@dp.message(lambda m: m.text == "✉️ Сделать рассылку")
async def admin_broadcast(message: types.Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    if not user or (not user.get("is_admin") and message.from_user.id != CREATOR_ID):
        return
    await message.answer("✍️ Напиши текст рассылки:")
    await state.set_state(Broadcast.waiting_for_text)

@dp.message(lambda m: m.get_current().state == Broadcast.waiting_for_text.state)
async def send_broadcast(message: types.Message, state: FSMContext):
    text = message.text
    users = await get_all_users()
    success = 0
    fail = 0
    for u in users:
        try:
            await bot.send_message(u["id"], f"📢 Рассылка:\n\n{text}")
            success += 1
        except:
            fail += 1
    await message.answer(f"✅ Рассылка завершена.\nУспешно: {success}, Ошибки: {fail}")
    await state.clear()

# --- Запуск ---
async def main():
    await init_db()
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

