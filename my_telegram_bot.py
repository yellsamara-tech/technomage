import os
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import Forbidden

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Твои кнопки
menu_buttons = [
    [KeyboardButton("Дорога"), KeyboardButton("Отпуск")],
    [KeyboardButton("Выходной"), KeyboardButton("Выходной в рабочее время")],
    [KeyboardButton("Больничный")],
]

reply_markup = ReplyKeyboardMarkup(menu_buttons, resize_keyboard=True, one_time_keyboard=False)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.reply_text(
            "Привет! Выберите свой статус из меню ниже:",
            reply_markup=reply_markup
        )
    except Forbidden:
        print(f"Пользователь {update.message.from_user.id} заблокировал бота.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text

    valid_statuses = ["Дорога", "Отпуск", "Выходной", "Выходной в рабочее время", "Больничный"]

    try:
        if user_text in valid_statuses:
            await update.message.reply_text(f"Вы выбрали: {user_text}. Ваш статус учтен, Спасибо!")
            # Можно добавить сохранение статуса сюда
        else:
            await update.message.reply_text("Ваш статус учтен, Спасибо")
    except Forbidden:
        print(f"Пользователь {update.message.from_user.id} заблокировал бота.")

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
