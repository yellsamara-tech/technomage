import asyncpg
from datetime import datetime, date
import os

DB_URL = os.getenv("DATABASE_URL")


async def create_pool():
    return await asyncpg.create_pool(dsn=DB_URL)


async def init_db(pool):
    async with pool.acquire() as conn:
        # Таблица пользователей
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            user_id BIGINT UNIQUE NOT NULL,
            tab_number VARCHAR(50),
            full_name TEXT,
            phone TEXT,
            is_admin BOOLEAN DEFAULT FALSE
        )
        """)
        # Таблица статусов
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS statuses (
            id SERIAL PRIMARY KEY,
            user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
            status TEXT,
            status_date DATE NOT NULL,
            UNIQUE(user_id, status_date)
        )
        """)
