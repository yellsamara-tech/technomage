import os
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
from aiogram.types import Update
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")  # например https://your-app-name.onrender.com
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

bot = Bot(token=TOKEN)
dp = Dispatcher()
app = FastAPI()


@dp.message()
async def echo_handler(message: types.Message):
    await message.reply(f"Привет, {message.from_user.full_name}!")


@app.on_event("startup")
async def on_startup():
    await bot.set_webhook(WEBHOOK_URL)


@app.on_event("shutdown")
async def on_shutdown():
    await bot.delete_webhook()


# Обрабатываем входящие запросы (webhook)
@app.post(WEBHOOK_PATH)
async def webhook_handler(request: Request):
    body = await request.body()
    update = Update.model_validate_json(body)
    await dp.feed_update(bot, update)
    return {"ok": True}
