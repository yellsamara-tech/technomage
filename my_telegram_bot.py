
import os
import asyncio
from flask import Flask, request
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")

app = Flask(__name__)
application = Application.builder().token(BOT_TOKEN).build()

# Стартовая страница
@app.route('/')
def index():
    return "Бот запущен и работает!"

# Устанавливаем webhook при первом запросе
@app.before_first_request
def init_webhook():
    url = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/{BOT_TOKEN}"
    asyncio.get_event_loop().create_task(application.bot.set_webhook(url))

# Webhook обработка
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json()
    update = Update.de_json(data, application.bot)
    asyncio.run(application.update_queue.put(update))
    return "OK"

# Обработчик /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["Дорога", "Отпуск"],
        ["Выходной", "Выходной в рабочее время"],
        ["Больничный"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("Выберите статус из меню или отправьте произвольное сообщение:", reply_markup=reply_markup)

# Обработчик текста
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    await update.message.reply_text("Ваш статус учтен, Спасибо")

# Регистрируем обработчики
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# Запуск Flask-приложения
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
