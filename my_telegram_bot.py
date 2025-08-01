import os
from flask import Flask, request
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

app = Flask(__name__)

# Простая стартовая страница для проверки, что сервер запущен
@app.route('/')
def index():
    return "Бот запущен и работает!"

BOT_TOKEN = os.getenv("BOT_TOKEN")  # Убедись, что в Render переменная окружения BOT_TOKEN задана

# Обработчик команды /start — показывает кнопки меню
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["Дорога", "Отпуск"],
        ["Выходной", "Выходной в рабочее время"],
        ["Больничный"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        "Выберите статус из меню или отправьте произвольное сообщение:",
        reply_markup=reply_markup,
    )

# Обработчик текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    # Здесь можно добавить логику записи статуса
    await update.message.reply_text("Ваш статус учтен, Спасибо")

# Маршрут webhook, по которому Телеграм будет слать обновления
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
async def webhook():
    data = await request.get_json()
    update = Update.de_json(data, application.bot)
    await application.update_queue.put(update)
    return "OK"

if __name__ == "__main__":
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Запускаем Flask, прослушиваем порт из переменной окружения (Render подставит)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
