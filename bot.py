import os
import asyncio
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
)
from database import init_db, register_user, is_registered

BOT_TOKEN = os.getenv("BOT_TOKEN")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = await init_db()
    user_id = update.effective_user.id
    full_name = update.effective_user.full_name

    if not await is_registered(conn, user_id):
        await register_user(conn, user_id, full_name)
        await update.message.reply_text("Вы успешно зарегистрированы.")
    else:
        await update.message.reply_text("Вы уже зарегистрированы.")
    await conn.close()


if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.run_polling()
