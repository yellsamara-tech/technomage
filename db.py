import os
import asyncpg
from datetime import date

DB_URL = os.getenv("DATABASE_URL")

# ----- Пул соединений -----
pool: asyncpg.pool.Pool = None

async def init_db():
    global pool
    pool = await asyncpg.create_pool(DB_URL)

    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id BIGINT PRIMARY KEY,
                full_name TEXT NOT NULL,
                status TEXT,
                is_admin BOOLEAN DEFAULT FALSE
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS status_history (
                user_id BIGINT REFERENCES users(id),
                status TEXT,
                status_date DATE,
                PRIMARY KEY(user_id, status_date)
            )
        """)

# ----- Пользователи -----
async def add_user(user_id: int, full_name: str):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO users (id, full_name) VALUES ($1, $2) ON CONFLICT (id) DO NOTHING",
            user_id, full_name
        )

async def get_user(user_id: int):
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM users WHERE id=$1", user_id)

async def get_all_users():
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM users ORDER BY full_name")

async def find_user_by_name(name: str):
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM users WHERE full_name ILIKE $1", f"%{name}%")

async def get_admins():
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM users WHERE is_admin=TRUE")

# ----- Статусы -----
async def update_status(user_id: int, status: str):
    today = date.today()
    async with pool.acquire() as conn:
        # обновляем текущий статус
        await conn.execute("UPDATE users SET status=$1 WHERE id=$2", status, user_id)
        # добавляем в историю с обновлением, если запись уже есть
        await conn.execute("""
            INSERT INTO status_history(user_id, status, status_date)
            VALUES($1, $2, $3)
            ON CONFLICT(user_id, status_date) DO UPDATE SET status=$2
        """, user_id, status, today)

async def set_user_status(user_id: int, status: str):
    await update_status(user_id, status)

async def get_status_history(user_id: int):
    async with pool.acquire() as conn:
        return await conn.fetch(
            "SELECT status, status_date FROM status_history WHERE user_id=$1 ORDER BY status_date",
            user_id
        )
