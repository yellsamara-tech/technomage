import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiohttp import web
from db import init_db, get_user, add_user

logging.basicConfig(level=logging.INFO)

# Загружаем переменные окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")   # https://dia-804u.onrender.com/webhook
PORT = int(os.getenv("PORT", 8000))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    user_name = message.from_user.full_name

    user = await get_user(user_id)
    if not user:
        await add_user(user_id, user_name)
        await message.answer(f"Привет, {user_name}! Ты зарегистрирован ✅")
    else:
        await message.answer(f"С возвращением, {user_name}! 👋")


# ---- Webhook ----
async def handle_webhook(request: web.Request):
    data = await request.json()
    update = types.Update(**data)
    await dp.feed_update(bot, update)
    return web.Response()


async def on_startup(app):
    await init_db()  # подключаем БД
    await bot.set_webhook(WEBHOOK_URL)  # ставим вебхук
    logging.info(f"Webhook установлен: {WEBHOOK_URL}")


async def on_shutdown(app):
    logging.info("Отключение вебхука...")
    await bot.delete_webhook()


def main():
    app = web.Application()
    app.router.add_post("/webhook", handle_webhook)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    web.run_app(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()
