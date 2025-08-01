import os
from datetime import datetime
from collections import defaultdict
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# Получаем токен из переменной окружения
TOKEN = os.environ.get("BOT_TOKEN", "8304128948:AAGfzX5TIABL3DVKkmynWovRvEEVvtPsTzg")

# Память: один статус в день
user_logs = defaultdict(dict)

# Клавиатура со статусами
status_keyboard = [["Больничный", "Отпуск"], ["ВР", "ОУ"]]
markup = ReplyKeyboardMarkup(status_keyboard, resize_keyboard=True, one_time_keyboard=False)

# Обработка команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Выберите статус:", reply_markup=markup)

# Обработка сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    username = update.message.from_user.username or f"user_{user_id}"
    date_str = datetime.now().strftime("%Y-%m-%d")

    status = update.message.text.strip()

    # Записываем или обновляем статус на текущую дату
    user_logs[user_id][date_str] = status

    print(f"[{date_str}] @{username}: {status}")
    await update.message.reply_text(f"Статус на {date_str}: {status}")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("Бот запущен...")
    app.run_polling()
