import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from database import Database

DATABASE_URL = "postgresql://user:password@host:port/dbname"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я асинхронный бот на python-telegram-bot 20.6!")

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db: Database = context.application.bot_data["db"]

    if await db.is_registered(user.id):
        await update.message.reply_text("Вы уже зарегистрированы.")
    else:
        full_name = user.full_name or user.username or "Неизвестный"
        await db.register_user(user.id, full_name)
        await update.message.reply_text(f"Вы успешно зарегистрированы, {full_name}!")

async def main():
    db = Database(DATABASE_URL)
    await db.connect()

    app = ApplicationBuilder().token("YOUR_BOT_TOKEN").build()
    app.bot_data["db"] = db

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("register", register))

    print("Бот запущен...")
    await app.run_polling()

    await db.close()

if __name__ == "__main__":
    asyncio.run(main())
