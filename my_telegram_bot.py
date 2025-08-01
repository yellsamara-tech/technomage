import os
from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN")  # Не вставляй токен вручную

# Старт
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [['Больничный', 'Отпуск'], ['ВР', 'ОУ']]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Выберите статус:", reply_markup=reply_markup)

# Обработка кнопки
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.username or update.effective_user.first_name
    text = update.message.text
    print(f"Получено сообщение от {user}: {text}")
    await update.message.reply_text(f"Вы выбрали: {text}")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Бот запущен")
    app.run_polling()

if __name__ == "__main__":
    main()
