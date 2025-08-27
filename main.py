import os
import asyncio
from datetime import date, datetime, time, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, Update
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from db import (
    init_db, add_user, get_user, update_status, get_all_users,
    get_admins, make_admin, revoke_admin, delete_user,
    get_status_history, get_users_without_status_today
)
from aiohttp import web
import pytz

# ----- Переменные окружения -----
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден")

CREATOR_ID = int(os.getenv("CREATOR_ID", "0"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
if not WEBHOOK_URL:
    raise ValueError("❌ WEBHOOK_URL не найден")

# ----- Инициализация бота и диспетчера -----
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
        [KeyboardButton(text="👑 Назначить админа"), KeyboardButton(text="❌ Убрать админа"), KeyboardButton(text="🗑 Удалить пользователя")],
        [KeyboardButton(text="✉️ Сделать рассылку"), KeyboardButton(text="📈 Статистика статусов")]
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
statuses = ["🟢 Я на работе (СП)", "🔴 Я болею (Б)", "🕒 Я в дороге (СП)", "📌 У меня отгул (Вр)"]

@dp.message(lambda m: m.text in statuses)
async def set_user_status(message: types.Message):
    await update_status(message.from_user.id, message.text)
    await message.answer(f"✅ Твой статус обновлён: {message.text}")

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

# --- Назначение админа ---
@dp.message(lambda m: m.text == "👑 Назначить админа")
async def admin_assign(message: types.Message):
    if message.from_user.id != CREATOR_ID:
        await message.answer("⛔ Только создатель может назначать админов")
        return
    users = await get_all_users()
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=u["full_name"], callback_data=f"makeadmin_{u['id']}")]
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

# --- Снятие админа ---
@dp.message(lambda m: m.text == "❌ Убрать админа")
async def admin_remove(message: types.Message):
    if message.from_user.id != CREATOR_ID:
        await message.answer("⛔ Только создатель может снимать админов")
        return
    admins = await get_admins()
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=u["full_name"], callback_data=f"removeadmin_{u['id']}")]
                         for u in admins if u["id"] != CREATOR_ID]
    )
    await message.answer("Выбери админа для снятия прав:", reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith("removeadmin_"))
async def callback_removeadmin(call: types.CallbackQuery):
    user_id = int(call.data.split("_")[1])
    await revoke_admin(user_id)
    await call.message.answer(f"✅ Пользователь {user_id} лишён прав админа.")
    await call.answer()

# --- Удаление пользователя ---
@dp.message(lambda m: m.text == "🗑 Удалить пользователя")
async def admin_delete_user(message: types.Message):
    user = await get_user(message.from_user.id)
    if not user or (not user.get("is_admin") and message.from_user.id != CREATOR_ID):
        return
    users = await get_all_users()
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=u["full_name"], callback_data=f"deleteuser_{u['id']}")]
                         for u in users if u["id"] != CREATOR_ID and not u["is_admin"]]
    )
    await message.answer("Выбери пользователя для удаления:", reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith("deleteuser_"))
async def callback_delete_user(call: types.CallbackQuery):
    user_id = int(call.data.split("_")[1])
    await delete_user(user_id)
    await call.message.answer(f"✅ Пользователь {user_id} удалён.")
    await call.answer()

# --- Рассылка ---
@dp.message(lambda m: m.text == "✉️ Сделать рассылку")
async def admin_broadcast(message: types.Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    if not user or (not user.get("is_admin") and message.from_user.id != CREATOR_ID):
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
            await bot.send_message(u["id"], f"📢 Рассылка:\n\n{text}")
            success += 1
        except:
            fail += 1
    await message.answer(f"✅ Рассылка завершена.\nУспешно: {success}, Ошибки: {fail}")
    await state.clear()

# --- Статистика статусов ---
@dp.message(lambda m: m.text == "📈 Статистика статусов")
async def admin_status_stats(message: types.Message):
    user = await get_user(message.from_user.id)
    if not user or (not user.get("is_admin") and message.from_user.id != CREATOR_ID):
        return
    today = date.today()
    users = await get_all_users()
    text = f"📊 Статистика статусов на {today}:\n"
    for u in users:
        history = await get_status_history(u["id"], today)
        status = history[-1]["status"] if history else "Не установлен"
        text += f"{u['full_name']}: {status}\n"
    await message.answer(text)

# ----- Вебхук и сервер -----
WEBHOOK_PATH = f"/{BOT_TOKEN}"
app = web.Application()

async def handle(request):
    update = Update(**await request.json())
    await dp.feed_update(bot, update)
    return web.Response()

app.router.add_post(WEBHOOK_PATH, handle)

async def on_startup(app):
    await init_db()
    await bot.set_webhook(WEBHOOK_URL)
    # Запуск задачи уведомлений
    asyncio.create_task(daily_status_reminder())

# ----- Напоминания в 18:00 по Самарскому времени -----
async def daily_status_reminder():
    tz = pytz.timezone("Europe/Samara")
    while True:
        now = datetime.now(tz)
        target_time = tz.localize(datetime.combine(now.date(), time(18, 0)))
        if now > target_time:
            target_time += timedelta(days=1)
        await asyncio.sleep((target_time - now).total_seconds())
        users = await get_users_without_status_today()
        for u in users:
            try:
                await bot.send_message(u["id"], "⚠️ Не забудьте обновить свой статус на сегодня!")
            except:
                continue

if __name__ == "__main__":
    web.run_app(app, port=int(os.getenv("PORT", 8000)), on_startup=[on_startup])
