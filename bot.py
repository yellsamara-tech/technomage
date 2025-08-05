import os
import asyncio
import logging
import asyncpg
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# Логгирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загружаем токен и строку подключения из переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

if not BOT_TOKEN or not DATABASE_URL:
    raise RuntimeError("BOT_TOKEN и DATABASE_URL должны быть заданы в переменных окружения")

# Инициализация подключения к базе
async def init_db():
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            full_name TEXT NOT NULL
        );
    """)
    return conn

# Регистрация пользователя
async def register_user(conn, user_id: int, full_name: str):
    await conn.execute("""
        INSERT INTO users (user_id, full_name)
        VALUES ($1, $2)
        ON CONFLICT (user_id) DO NOTHING;
    """, user_id, full_name)

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = context.bot_data.get("db")
    await register_user(conn, user.id, user.full_name)
    await update.message.reply_text(f"Привет, {user.full_name}! Ты зарегистрирован.")

# Команда /me — возвращает имя из базы
async def me(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = context.bot_data.get("db")
    row = await conn.fetchrow("SELECT full_name FROM users WHERE user_id = $1", user_id)
    if row:
        await update.message.reply_text(f"Ты в базе как: {row['full_name']}")
    else:
        await update.message.reply_text("Ты ещё не зарегистрирован. Напиши /start.")

# Основной запуск
async def main():
    conn = await init_db()

    application = Application.builder().token(BOT_TOKEN).build()

    # Сохраняем подключение к БД в bot_data
    application.bot_data["db]()_
