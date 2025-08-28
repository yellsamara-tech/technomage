import os
import asyncio
from datetime import date, datetime
from aiohttp import web
import requests

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

# ====== ВАЖНО: импорт функций БД из db.py ======
from db import (
    init_db, add_user, get_user, get_all_users,
    make_admin, revoke_admin, delete_user,
    update_status, get_status_history
)

# ========= Переменные окружения =========
BOT_TOKEN   = os.getenv("BOT_TOKEN",   "8304128948:AAGfzX5TIABL3DVKkmynWovRvEEVvtPsTzg")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://dia-804u.onrender.com/webhook")  # именно /webhook
PORT        = int(os.getenv("PORT", "8000"))
CREATOR_ID  = int(os.getenv("CREATOR_ID", "452908347"))

# ========= Инициализация бота/диспетчера =========
storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)

# ========= FSM =========
class Registration(StatesGroup):
    waiting_for_fullname = State()
    waiting_for_tabel = State()
    waiting_for_phone = State()

class Broadcast(StatesGroup):
    waiting_for_text = State()

# ========= Статусы (кнопки) =========
statuses = [
    "🟢 Я на работе (СП)",
    "🔴 Я болею (Б)",
    "🕒 Я в дороге (СП)",
    "📌 У меня отгул (Вр)"
]

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

# ========= Хелперы =========
async def is_admin(user_id: int) -> bool:
    u = await get_user(user_id)
    if not u:
        return False
    return bool(u["is_admin"] or (user_id == CREATOR_ID))

# ========= Хэндлеры =========
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer(
            "👋 Привет! Давай зарегистрируемся.\n"
            "Введи своё ФИО:"
        )
        await state.set_state(Registration.waiting_for_fullname)
    else:
        kb = admin_kb if await is_admin(message.from_user.id) else user_kb
        await message.answer("✅ Бот активен. Меню доступно ниже:", reply_markup=kb)

@dp.message(Registration.waiting_for_fullname)
async def reg_fullname(message: types.Message, state: FSMContext):
    await state.update_data(fullname=message.text.strip())
    await message.answer("✍️ Теперь введи свой табельный номер:")
    await state.set_state(Registration.waiting_for_tabel)

@dp.message(Registration.waiting_for_tabel)
async def reg_tabel(message: types.Message, state: FSMContext):
    await state.update_data(tabel=message.text.strip())
    await message.answer("📱 Теперь введи номер телефона:")
    await state.set_state(Registration.waiting_for_phone)

@dp.message(Registration.waiting_for_phone)
async def reg_phone(message: types.Message, state: FSMContext):
    data = await state.get_data()
    fullname = data.get("fullname", "").strip()
    tabel = data.get("tabel", "").strip()
    phone = message.text.strip()
    is_admin_flag = (message.from_user.id == CREATOR_ID)

    # Сохраняем пользователя
    await add_user(
        user_id=message.from_user.id,
        full_name=f"{fullname} ({tabel})" if tabel else fullname,
        tab_number=tabel,
        phone=phone,
        is_admin=is_admin_flag
    )
    await state.clear()

    kb = admin_kb if is_admin_flag else user_kb
    await message.answer("✅ Регистрация завершена! Выбери статус:", reply_markup=kb)

# Установка статуса
@dp.message(lambda m: m.text in statuses)
async def set_user_status_handler(message: types.Message):
    await update_status(message.from_user.id, message.text)
    await message.answer(f"✅ Твой статус обновлён: {message.text}")

# ======== Админка ========

# Список всех пользователей
@dp.message(lambda m: m.text == "📊 Посмотреть всех пользователей")
async def admin_show_users(message: types.Message):
    if not await is_admin(message.from_user.id):
        return
    users = await get_all_users()
    if not users:
        await message.answer("Пока нет зарегистрированных пользователей.")
        return
    lines = []
    for u in users:
        role = "🛡️ Админ" if u["is_admin"] else "👤 Пользователь"
        lines.append(f"{u['user_id']} | {u['full_name']} | {role}")
    await message.answer("👥 Все пользователи:\n" + "\n".join(lines))

# Назначить админа (inline список)
@dp.message(lambda m: m.text == "👑 Назначить админа")
async def admin_assign(message: types.Message):
    if message.from_user.id != CREATOR_ID:
        await message.answer("⛔ Только создатель может назначать админов.")
        return
    users = await get_all_users()
    candidates = [u for u in users if not u["is_admin"]]
    if not candidates:
        await message.answer("Нет пользователей для назначения.")
        return
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=u["full_name"], callback_data=f"makeadmin_{u['user_id']}")]
            for u in candidates
        ]
    )
    await message.answer("Выбери пользователя для назначения админом:", reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith("makeadmin_"))
async def callback_makeadmin(call: types.CallbackQuery):
    if call.from_user.id != CREATOR_ID:
        await call.answer("Недостаточно прав", show_alert=True)
        return
    user_id = int(call.data.split("_", 1)[1])
    await make_admin(user_id)
    await call.message.answer(f"✅ Пользователь {user_id} назначен админом.")
    await call.answer()

# Убрать админа (inline список)
@dp.message(lambda m: m.text == "❌ Убрать админа")
async def admin_remove(message: types.Message):
    if message.from_user.id != CREATOR_ID:
        await message.answer("⛔ Только создатель может снимать админов.")
        return
    users = await get_all_users()
    admins = [u for u in users if u["is_admin"] and u["user_id"] != CREATOR_ID]
    if not admins:
        await message.answer("Нет админов для снятия.")
        return
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=u["full_name"], callback_data=f"removeadmin_{u['user_id']}")]
            for u in admins
        ]
    )
    await message.answer("Выбери админа для снятия прав:", reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith("removeadmin_"))
async def callback_removeadmin(call: types.CallbackQuery):
    if call.from_user.id != CREATOR_ID:
        await call.answer("Недостаточно прав", show_alert=True)
        return
    user_id = int(call.data.split("_", 1)[1])
    await revoke_admin(user_id)
    await call.message.answer(f"✅ Пользователь {user_id} лишён прав админа.")
    await call.answer()

# Удалить пользователя (inline список)
@dp.message(lambda m: m.text == "🗑 Удалить пользователя")
async def admin_delete_user(message: types.Message):
    if not await is_admin(message.from_user.id):
        return
    users = await get_all_users()
    deletable = [u for u in users if u["user_id"] != CREATOR_ID]
    if not deletable:
        await message.answer("Нет пользователей для удаления.")
        return
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=u["full_name"], callback_data=f"deleteuser_{u['user_id']}")]
            for u in deletable
        ]
    )
    await message.answer("Выбери пользователя для удаления:", reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith("deleteuser_"))
async def callback_delete_user(call: types.CallbackQuery):
    if not await is_admin(call.from_user.id):
        await call.answer("Недостаточно прав", show_alert=True)
        return
    user_id = int(call.data.split("_", 1)[1])
    await delete_user(user_id)
    await call.message.answer(f"✅ Пользователь {user_id} удалён.")
    await call.answer()

# Рассылка
@dp.message(lambda m: m.text == "✉️ Сделать рассылку")
async def admin_broadcast(message: types.Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await message.answer("✍️ Введите текст рассылки:")
    await state.set_state(Broadcast.waiting_for_text)

@dp.message(Broadcast.waiting_for_text)
async def send_broadcast(message: types.Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        await state.clear()
        return
    text = message.text
    users = await get_all_users()
    success = 0
    fail = 0
    for u in users:
        try:
            await bot.send_message(u["user_id"], f"📢 Рассылка:\n\n{text}")
            success += 1
        except Exception:
            fail += 1
    await message.answer(f"✅ Рассылка завершена.\nУспешно: {success}, Ошибки: {fail}")
    await state.clear()

# Статистика статусов
@dp.message(lambda m: m.text == "📈 Статистика статусов")
async def admin_status_stats(message: types.Message):
    if not await is_admin(message.from_user.id):
        return
    today = date.today()
    users = await get_all_users()
    counters = {s: 0 for s in statuses}
    for u in users:
        rows = await get_status_history(u["user_id"], today)
        if rows:
            # берем последнюю запись за сегодня
            last = rows[-1]
            st = last["status"]
            if st in counters:
                counters[st] += 1
    lines = [f"{k}: {v}" for k, v in counters.items()]
    await message.answer(f"📊 Статистика статусов на {today}:\n" + "\n".join(lines))

# ========= Webhook handlers (aiohttp) =========
async def index(request: web.Request):
    return web.Response(text="OK: bot is running")

async def webhook_get(request: web.Request):
    # чтоб руками заходить без 405
    return web.Response(text="Webhook endpoint. Use POST from Telegram.")

async def webhook_post(request: web.Request):
    try:
        data = await request.json()
    except Exception:
        return web.Response(status=400, text="Bad JSON")

    try:
        update = types.Update.model_validate(data)
    except Exception as e:
        print("Update validate error:", e)
        return web.Response(status=400, text="Bad Update")

    try:
        await dp.feed_update(bot, update)
    except Exception as e:
        print("feed_update error:", e)
    return web.Response(text="ok")

app = web.Application()
app.router.add_get("/", index)
app.router.add_get("/webhook", webhook_get)
app.router.add_post("/webhook", webhook_post)

# ========= Startup / Shutdown =========
async def on_startup(app: web.Application):
    print("Starting up...")
    # инициализация БД
    await init_db()
    # установка вебхука
    await bot.set_webhook(WEBHOOK_URL)

async def on_shutdown(app: web.Application):
    print("Shutting down...")
    await bot.delete_webhook()
    await bot.session.close()

app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

# ========= Entry point =========
if __name__ == "__main__":
    web.run_app(app, port=PORT)
