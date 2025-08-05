import os
import psycopg2
from psycopg2.extras import DictCursor
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, filters

# Инициализация подключения к базе
def init_db():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise Exception("DATABASE_URL environment variable not set")
    conn = psycopg2.connect(db_url, cursor_factory=DictCursor)
    return conn

# Проверка, зарегистрирован ли пользователь
def is_registered(user_id: int, conn) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM users WHERE user_id = %s", (user_id,))
        return cur.fetchone() is not None

# Регистрация пользователя (user_id, full_name)
def register_user(user_id: int, full_name: str, conn):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO users (user_id, full_name) VALUES (%s, %s) ON CONFLICT (user_id) DO NOTHING",
            (user_id, full_name)
        )
        conn.commit()

# Получить ФИО пользователя из БД
def get_full_name(user_id: int, conn) -> str | None:
    with conn.cursor() as cur:
        cur.execute("SELECT full_name FROM users WHERE user_id = %s", (user_id,))
        row = cur.fetchone()
        return row["full_name"] if row else None

# Обработчик команды /start (по желанию)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = context.bot_data['conn']
    if is_registered(user_id, conn):
        full_name = get_full_name(user_id, conn)
        await update.message.reply_text(f"Привет, {full_name}! Вы уже зарегистрированы.")
    else:
        await update.message.reply_text("Привет! Пожалуйста, напиши своё ФИО для регистрации.")

# Обработчик всех текстовых сообщений (регистрация новых пользователей)
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    conn = context.bot_data['conn']

    if not is_registered(user_id, conn):
        register_user(user_id, text, conn)
        await update.message.reply_text(f"Спасибо, {text}, вы успешно зарегистрированы!")
    else:
        full_name = get_full_name(user_id, conn)
        await update.message.reply_text(f"Вы уже зарегистрированы как {full_name}.")

def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise Exception("BOT_TOKEN environment variable not set")

    conn = init_db()

    application = ApplicationBuilder().token(token).build()

    # Кладём подключение в bot_data для доступа из обработчиков
    application.bot_data['conn'] = conn

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот запущен...")
    application.run_polling()

if __name__ == "__main__":
    main()
