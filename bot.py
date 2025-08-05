import os
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    MessageHandler, ContextTypes, filters, ConversationHandler
)
from database import init_db, is_registered, register_user, get_full_name

TOKEN = os.environ["BOT_TOKEN"]

ASK_NAME = 1  # Этап диалога

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_registered(user_id):
        full_name = get_full_name(user_id)
        await update.message.reply_text(f"С возвращением, {full_name}!")
    else:
        await update.message.reply_text("Привет! Пожалуйста, введи своё ФИО для регистрации:")
        return ASK_NAME
    return ConversationHandler.END

async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    full_name = update.message.text.strip()
    register_user(user_id, full_name)
    await update.message.reply_text(f"Спасибо, {full_name}, вы зарегистрированы.")
    return ConversationHandler.END

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_registered(user_id):
        name = get_full_name(user_id)
        await update.message.reply_text(f"{name}, ваш статус: 🟢 Активен.")
    else:
        await update.message.reply_text("Вы не зарегистрированы. Напишите /start для начала.")

async def fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_registered(user_id):
        await update.message.reply_text("Я вас понял 👍")
    else:
        await update.message.reply_text("Пожалуйста, введите /start и укажите ФИО для регистрации.")

def main():
    init_db()

    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_name)]},
        fallbacks=[MessageHandler(filters.ALL, fallback)]
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("status", status))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, fallback))

    app.run_polling()

if __name__ == "__main__":
    main()
