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
import db  # твой файл db.py

# ===== Переменные окружения =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", 8000))
CREATOR_ID = int(os.getenv("CREATOR_ID", 0))

# ===== Инициализация =====
storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)

# ===== FSM состояния =====
class Registration(StatesGroup):
    waiting_for_fullname = State()
    waiting_for_tabel = State()
    waiting_for_phone = State()

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

# ===== Обработчики =====
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("👋 Привет! Давай зарегистрируемся.\nВведи своё ФИО:")
        await state.set_state(Registration.waiting_for_fullname)
    else:
        kb = admin_kb if user["is_admin"] or message.from_user.id == CREATOR_ID else user_kb
        await message.answer("✅ Бот активен. Меню доступно ниже:", reply_markup=kb)

@dp.message(lambda m: m.text not in statuses)
async def reg_fullname(message: types.Message, state: FSMContext):
    data = await state.get_data()
    current_state = await state.get_state()
    
    if current_state == Registration.waiting_for_fullname.state:
        await state.update_data(fullname=message.text)
        await message.answer("✍️ Теперь введи свой табельный номер:")
        await state.set_state(Registration.waiting_for_tabel)
        return
    elif current_state == Registration.waiting_for_tabel.state:
        await state.update_data(tabel=message.text)
        await message.answer("📱 Теперь введи номер телефона:")
        await state.set_state(Registration.waiting_for_phone)
        return
    elif current_state == Registration.waiting_for_phone.state:
        data = await state.get_data()
        fullname = data.get("fullname")
        tabel = data.get("tabel")
        phone = message.text
        is_admin = message.from_user.id == CREATOR_ID
        await db.add_user(message.from_user.id, f"{fullname} ({tabel})", tabel, phone, is_admin)
        await state.clear()
        kb = admin_kb if is_admin else user_kb
        await message.answer("✅ Регистрация завершена! Выбери статус:", reply_markup=kb)
        return

@dp.message(lambda m: m.text in statuses)
async def set_user_status(message: types.Message):
    await db.update_status(message.from_user.id, message.text)
    await message.answer(f"✅ Твой статус обновлён: {message.text}")

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
    await db.init_db()
    await bot.delete_webhook()
    await bot.set_webhook(f"{WEBHOOK_URL}/{BOT_TOKEN}")
    print("✅ Webhook установлен, бот готов!")

async def on_shutdown():
    await bot.delete_webhook()
    await bot.session.close()

if __name__ == "__main__":
    web.run_app(app, port=PORT, print=None, handle_signals=True)
