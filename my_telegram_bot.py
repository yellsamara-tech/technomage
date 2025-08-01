import os
from flask import Flask, request
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, filters

TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=TOKEN)
app = Flask(__name__)

dispatcher = Dispatcher(bot, update_queue=None, workers=0, use_context=True)

# Кнопки меню
def get_menu_keyboard():
    buttons = [
        [InlineKeyboardButton("Дорога", callback_data="Дорога")],
        [InlineKeyboardButton("Отпуск", callback_data="Отпуск")],
        [InlineKeyboardButton("Выходной", callback_data="Выходной")],
        [InlineKeyboardButton("Выходной в рабочее время", callback_data="Выходной в рабочее время")],
        [InlineKeyboardButton("Больничный", callback_data="Больничный")],
    ]
    return InlineKeyboardMarkup(buttons)

def start(update, context):
    update.message.reply_text(
        "Привет! Выбери свой статус:", 
        reply_markup=get_menu_keyboard()
    )

def button_callback(update, context):
    query = update.callback_query
    user = query.from_user
    status = query.data

    # Сохраняем статус (логика может быть дополнена)
    # Тут можно записать в файл, базу или лог

    query.answer()
    query.edit_message_text(f"Ваш статус '{status}' учтен, спасибо, {user.first_name}!")

def handle_message(update, context):
    update.message.reply_text("Ваш статус учтен, Спасибо")

# Роут для webhook
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "OK"

# Чтобы проверить, что сервер запущен
@app.route("/")
def index():
    return "Bot is running"

# Регистрируем обработчики
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
dispatcher.add_handler(telegram.ext.CallbackQueryHandler(button_callback))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
