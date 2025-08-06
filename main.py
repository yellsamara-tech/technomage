import asyncio
from aiohttp import web
from aiogram import BaseMiddleware
from aiogram.types import Update
from app.bot import bot, dp
from app.config import WEBHOOK_URL, WEBHOOK_PATH, BOT_TOKEN
from app.handlers import *  # noqa: F401,F403

async def on_startup(app):
    await bot.set_webhook(WEBHOOK_URL + WEBHOOK_PATH)
    print("Webhook set:", WEBHOOK_URL + WEBHOOK_PATH)

async def on_shutdown(app):
    await bot.delete_webhook()
    await bot.session.close()

async def handle_update(request: web.Request):
    request_body = await request.json()
    update = Update(**request_body)
    await dp.process_update(update)
    return web.Response()

app = web.Application()
app.router.add_post(WEBHOOK_PATH, handle_update)
app.on_startup.append(on_startup)
app.on_cleanup.append(on_shutdown)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000)
