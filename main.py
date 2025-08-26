from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from db import init_db, add_user, get_user, update_status

# Кнопки статусов
status_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✅ Работаю"), KeyboardButton(text="🤒 Болею")],
        [KeyboardButton(text="🏖 Отпуск"), KeyboardButton(text="✍️ Свой вариант")]
    ],
    resize_keyboard=True
)

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    user = await get_user(message.from_user.id)
    if user:
        await message.answer(f"Ты уже зарегистрирован как: {user[1]}\n\nВыбери свой статус:", reply_markup=status_kb)
    else:
        await message.answer("Привет! Введи своё ФИО для регистрации.")

@dp.message()
async def process_message(message: types.Message):
    user = await get_user(message.from_user.id)

    # Если пользователь ещё не зарегистрирован → сохраняем ФИО
    if not user:
        full_name = message.text.strip()
        await add_user(message.from_user.id, full_name)
        await message.answer(f"✅ Зарегистрировал тебя как: {full_name}\n\nТеперь выбери свой статус:", reply_markup=status_kb)
        return

    # Если пользователь зарегистрирован → обновляем статус
    text = message.text.strip()
    if text == "✍️ Свой вариант":
        await message.answer("Напиши свой статус сообщением 👇")
    else:
        await update_status(message.from_user.id, text)
        await message.answer(f"📌 Статус обновлён: {text}")
