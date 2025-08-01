from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

TOKEN = "8304128948:AAGfzX5TIABL3DVKkmynWovRvEEVvtPsTzg"

# Кнопки
status_keyboard = ReplyKeyboardMarkup(
    keyboard=[["Больничный", "Отпуск"], ["ВР", "ОУ"]],
    resize_keyboard=True
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Выберите статус:",
        reply_markup=status_keyboard
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user = update.message.from_user.first_name
    await update.message.reply_text(f"Статус принят: {text}")
    # тут можно сохранить в файл или таблицу

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот запущен!")
    app.run_polling()
