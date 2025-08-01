
import os
import asyncio
from flask import Flask, request
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# === Настройки бота ===
BOT_TOKEN = "8304128948:AAGfzX5TIABL3DVKkmynWovRvEEVvtPsTzg"
RENDER_EXTERNAL_HOSTNAME = "technomage.onrender.com"
WEBHOOK_URL = f"https://{RENDER_EXTERNAL_HOSTNAME}/{BOT_TOKEN}"

# === Flask приложение ===
app = Flask(__name__)

# === Telegram приложение ===
application = Application.builder().token(BOT_TOKEN).build()

# === Установка webhook при запуске ===
@app.before_first_request
def init_webhook():
    print(f"Устанавливаю webhook на: {WEBHOOK_URL}")
    asyncio.get_event_loop().create_task(application.bot.set_webhook(WEBHOOK_URL))

# === Простая стартовая страница ===
@app.route('/')
def index():
    return "Бот запущен и работает!"

# === Обработчик команды /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["Дорога", "Отпуск"],
        ["Выходной", "Выходной в рабочее время"],
        ["Больничный"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        "Выберите статус из меню или отправьте произвольное сообщение:",
        reply_markup=reply_markup
    )

# === Обработчик любого текстового сообщения ===
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ваш статус учтен, спасибо!")

# === Webhook — Telegram отправляет сюда обновления ===
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json()
    update = Update.de_json(data, application.bot)
    asyncio.run(application.update_queue.put(update))
    return "OK"

# === Регистрация обработчиков ===
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# === Запуск Flask-приложения ===
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))

