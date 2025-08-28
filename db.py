# db.py
import asyncpg
import os
from datetime import date

DATABASE_URL = os.getenv("DATABASE_URL")

pool: asyncpg.Pool | None = None


async def init_db():
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL)

    async with pool.acquire() as conn:
        # Создаём таблицу пользователей
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            user_id BIGINT UNIQUE NOT NULL,
            tab_number VARCHAR(50),
            full_name VARCHAR(255),
            phone VARCHAR(50)
        )
        """)
        # Таблица статусов
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS statuses (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            status TEXT NOT NULL,
            status_date DATE NOT NULL
        )
        """)


# === Работа с пользователями ===

async def get_user(user_id: int):
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM users WHERE user_id=$1", user_id)


async def add_user(user_id: int, tab_number: str, full_name: str, phone: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (user_id, tab_number, full_name, phone)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id) DO NOTHING
        """, user_id, tab_number, full_name, phone)


# === Работа со статусами ===

async def set_status(user_id: int, status: str):
    today = date.today()
    async with pool.acquire() as conn:
        # Если статус за сегодня уже есть — обновляем
        existing = await conn.fetchrow("""
            SELECT * FROM statuses WHERE user_id=$1 AND status_date=$2
        """, user_id, today)

        if existing:
            await conn.execute("""
                UPDATE statuses SET status=$1 WHERE user_id=$2 AND status_date=$3
            """, status, user_id, today)
        else:
            await conn.execute("""
                INSERT INTO statuses (user_id, status, status_date)
                VALUES ($1, $2, $3)
            """, user_id, status, today)


async def get_status(user_id: int, day: date = None):
    if day is None:
        day = date.today()
    async with pool.acquire() as conn:
        return await conn.fetchrow("""
            SELECT status FROM statuses WHERE user_id=$1 AND status_date=$2
        """, user_id, day)
