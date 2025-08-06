from aiogram import types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from app.bot import dp, bot
from app.database import get_async_session
from app.models import User
from sqlalchemy.future import select

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    async with get_async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        user = result.scalar_one_or_none()
        if not user:
            user = User(telegram_id=message.from_user.id, full_name=message.from_user.full_name)
            session.add(user)
            await session.commit()
    await message.answer(f"Привет, {message.from_user.full_name}!
Отправь свой статус командой /status <текст>.")

@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    text = message.get_args()
    if not text:
        await message.answer("Пожалуйста, отправь статус после команды, например:\n/status на работе")
        return
    async with get_async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        user = result.scalar_one_or_none()
        if user:
            user.status = text
            await session.commit()
            await message.answer(f"Статус обновлен: {text}")
        else:
            await message.answer("Вы не зарегистрированы, отправьте /start для регистрации.")
