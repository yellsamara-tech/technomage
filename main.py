import os
from datetime import date
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from db import init_db, add_user, get_user, get_all_users, make_admin, revoke_admin, delete_user, update_status, get_status_history

# ===== Переменные окружения =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", 8000))
CREATOR_ID = int(os.getenv("CREATOR_ID", "0"))
DB_URL = os.getenv("DATABASE_URL")

if not all([BOT_TOKEN, WEBHOOK_URL, DB_URL]):
    raise ValueError("❌ Не все обязательные переменные окружения заданы!")

# ===== Инициализация бота =====
storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)

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
        [KeyboardButton(statuses[0]), KeyboardButton(statuses[1])],
        [KeyboardButton(statuses[2]), KeyboardButton(statuses[3])]
    ], resize_keyboard=True
)

admin_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton("📊 Посмотреть всех пользователей")],
        [KeyboardButton("👑 Назначить админа"), KeyboardButton("❌ Убрать админа"), KeyboardButton("🗑 Удалить пользователя")],
        [KeyboardButton("✉️ Сделать рассылку"), KeyboardButton("📈 Статистика статусов")]
    ], resize_keyboard=True
)

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

# ===== Админка =====
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

@dp.message(lambda m: m.text == "👑 Назначить админа")
async def admin_assign(message: types.Message):
    if message.from_user.id != CREATOR_ID:
        await message.answer("⛔ Только создатель может назначать админов")
        return
    users = await get_all_users()
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(u["full_name"], callback_data=f"makeadmin_{u['user_id']}")] for u in users if not u["is_admin"]]
    )
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
    users = await get_all_users()
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(u["full_name"], callback_data=f"removeadmin_{u['user_id']}")] for u in users if u["is_admin"] and u["user_id"] != CREATOR_ID]
    )
    await message.answer("Выбери админа для снятия прав:", reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith("removeadmin_"))
async def callback_removeadmin(call: types.CallbackQuery):
    user_id = int(call.data.split("_")[1])
    await revoke_admin(user_id)
    await call.message.answer(f"✅ Пользователь {user_id} лишён прав админа.")
    await call.answer()

@dp.message(lambda m: m.text == "🗑 Удалить пользователя")
async def admin_delete_user(message: types.Message):
    users = await get_all_users()
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(u["full_name"], callback_data=f"deleteuser_{u['user_id']}")] for u in users if u["user_id"] != CREATOR_ID and not u["is_admin"]]
    )
    await message.answer("Выбери пользователя для удаления:", reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith("deleteuser_"))
async def callback_delete_user(call: types.CallbackQuery):
    user_id = int(call.data.split("_")[1])
    await delete_user(user_id)
    await call.message.answer(f"✅ Пользователь {user_id} удалён.")
    await call.answer()

@dp.message(lambda m: m.text == "✉️ Сделать рассылку")
async def admin_broadcast(message: types.Message, state: FSMContext):
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

@dp.message(lambda m: m.text == "📈 Статистика статусов")
async def admin_status_stats(message: types.Message):
    users = await get_all_users()
    today = date.today().isoformat()
    text = f"📊 Статистика статусов на {today}:\n"
    for u in users:
        history = await get_status_history(u["user_id"], today)
        status = history[-1]["status"] if history else "Не установлен"
        text += f"{u['full_name']}: {status}\n"
    await message.answer(text)

# ===== Webhook =====
async def handle(request: web.Request):
    if request.method == "POST":
        data = await request.json()
        print("✅ Получен апдейт:", data)  # для логов Render
        update = types.Update(**data)
        await dp.feed_update(bot, update)
        return web.Response()
    return web.Response(status=405)

# ===== Запуск сервера =====
app = web.Application()
app.router.add_post(f"/{BOT_TOKEN}", handle)  # путь = токен

async def on_startup():
    await init_db(DB_URL)
    await bot.delete_webhook()
    await bot.set_webhook(f"{WEBHOOK_URL}/{BOT_TOKEN}")
    print("✅ Webhook установлен, бот готов!")

async def on_shutdown():
    await bot.delete_webhook()
    await bot.session.close()

if __name__ == "__main__":
    web.run_app(app, port=PORT)
