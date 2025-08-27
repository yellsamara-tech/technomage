import os
import asyncio
from datetime import date, datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pytz import timezone
from db import (
    init_db, add_user, get_user, update_status, get_all_users, get_admins,
    make_admin, revoke_admin, delete_user, get_status_history, set_reminder_time, get_reminder_time
)

# ----- Переменные окружения -----
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден")

CREATOR_ID = int(os.getenv("CREATOR_ID", "0"))  # твой ID по умолчанию

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

class ReminderTime(StatesGroup):
    waiting_for_time = State()

# ----- Клавиатуры -----
user_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton("🟢 Я на работе (СП)"), KeyboardButton("🔴 Я болею (Б)")],
        [KeyboardButton("🕒 Я в дороге (СП)"), KeyboardButton("📌 У меня отгул (Вр)")],
        [KeyboardButton("ℹ️ Проверить последний статус")]
    ],
    resize_keyboard=True
)

admin_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton("📊 Посмотреть всех пользователей")],
        [KeyboardButton("📈 Статистика по статусам"), KeyboardButton("📜 История пользователя")],
        [KeyboardButton("👑 Назначить админа"), KeyboardButton("❌ Убрать админа")],
        [KeyboardButton("🗑️ Удалить пользователя"), KeyboardButton("✉️ Сделать рассылку")],
        [KeyboardButton("⏰ Изменить время напоминания")]
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
            "Админы смогут видеть всех пользователей, делать рассылки, статистику и управлять напоминаниями.\n\n"
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
@dp.message(lambda m: m.text in ["🟢 Я на работе (СП)", "🔴 Я болею (Б)", "🕒 Я в дороге (СП)", "📌 У меня отгул (Вр)"])
async def set_user_status(message: types.Message):
    await update_status(message.from_user.id, message.text)
    await message.answer(f"✅ Твой статус обновлён: {message.text}")

@dp.message(lambda m: m.text == "ℹ️ Проверить последний статус")
async def check_status(message: types.Message):
    user = await get_user(message.from_user.id)
    last_status = user.get("status") or "ещё не выбран"
    await message.answer(f"📌 Твой последний статус: {last_status}")

# ----- Админ: Просмотр пользователей -----
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

# ----- Админ: Статистика по статусам -----
@dp.message(lambda m: m.text == "📈 Статистика по статусам")
async def admin_status_stats(message: types.Message):
    users = await get_all_users()
    today = date.today()
    text = f"📊 Статистика статусов за {today}:\n"
    for u in users:
        history = await get_status_history(u["id"])
        today_status = next((h["status"] for h in history if h["status_date"] == today), "не выбран")
        text += f"{u['full_name']}: {today_status}\n"
    await message.answer(text)

# ----- Админ: История пользователя -----
@dp.message(lambda m: m.text == "📜 История пользователя")
async def admin_user_history(message: types.Message, state: FSMContext):
    await message.answer("Введите ID пользователя для просмотра истории:")
    await state.set_state(Registration.waiting_for_fullname)  # переиспользуем для ввода ID

# ----- Админ: Назначение и снятие админов -----
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

# ----- Админ: Удаление пользователей -----
@dp.message(lambda m: m.text == "🗑️ Удалить пользователя")
async def admin_delete_user(message: types.Message):
    deleter = await get_user(message.from_user.id)
    if not deleter:
        return
    users = await get_all_users()
    kb = InlineKeyboardMarkup(row_width=1)
    for u in users:
        # создатель видит всех, админ только обычных пользователей
        if message.from_user.id == CREATOR_ID or (deleter.get("is_admin") and not u["is_admin"]):
            kb.add(InlineKeyboardButton(u["full_name"], callback_data=f"delete_{u['id']}"))
    if kb.inline_keyboard:
        await message.answer("Выбери пользователя для удаления:", reply_markup=kb)
    else:
        await message.answer("Нет пользователей для удаления.")

@dp.callback_query(lambda c: c.data.startswith("delete_"))
async def callback_delete_user(call: types.CallbackQuery):
    deleter = await get_user(call.from_user.id)
    user_id = int(call.data.split("_")[1])
    target = await get_user(user_id)
    if not target:
        await call.answer("Пользователь не найден.", show_alert=True)
        return
    if call.from_user.id != CREATOR_ID and target.get("is_admin"):
        await call.answer("⛔ Нельзя удалить админа.", show_alert=True)
        return
    await delete_user(user_id)
    await call.message.answer(f"✅ Пользователь {target['full_name']} удалён.")
    await call.answer()

# ----- Админ: Рассылка -----
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

# ----- Админ: Настройка времени напоминаний -----
@dp.message(lambda m: m.text == "⏰ Изменить время напоминания")
async def admin_set_reminder(message: types.Message, state: FSMContext):
    await message.answer("Введите новое время напоминания в формате ЧЧ:ММ (например 09:00):")
    await state.set_state(ReminderTime.waiting_for_time)

@dp.message(ReminderTime.waiting_for_time)
async def set_reminder_time_handler(message: types.Message, state: FSMContext):
    try:
        t = datetime.strptime(message.text, "%H:%M").time()
        await set_reminder_time(t.hour, t.minute)
        await message.answer(f"✅ Время напоминания установлено на {t.strftime('%H:%M')}")
    except:
        await message.answer("⛔ Неверный формат времени. Попробуйте снова (ЧЧ:ММ)")
    await state.clear()

# ----- Ежедневное напоминание -----
scheduler = AsyncIOScheduler(timezone=timezone("Europe/Samara"))

async def send_daily_reminder():
    users = await get_all_users()
    for u in users:
        try:
            await bot.send_message(u["id"], "⏰ Пожалуйста, обновите свой статус на сегодня!")
        except:
            pass

async def main():
    await init_db()
    # Устанавливаем расписание напоминаний
    reminder_time = await get_reminder_time()
    if reminder_time:
        scheduler.add_job(send_daily_reminder, "cron", hour=reminder_time["hour"], minute=reminder_time["minute"])
    scheduler.start()
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
