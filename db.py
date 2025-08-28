import asyncpg
from datetime import datetime, date
import os

DB_URL = os.getenv("DATABASE_URL")


async def create_pool():
    return await asyncpg.create_pool(dsn=DB_URL)


async def init_db():
    pool = await create_pool()
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
            UNIQUE(user_id, status_date) -- 🔑 гарантирует один статус в день
        )
        """)
    await pool.close()


# =============================
# Работа с пользователями
# =============================
async def add_user(pool, user_id: int, tab_number: str, full_name: str, phone: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (user_id, tab_number, full_name, phone)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id) DO UPDATE 
              SET tab_number = EXCLUDED.tab_number,
                  full_name = EXCLUDED.full_name,
                  phone = EXCLUDED.phone
        """, user_id, tab_number, full_name, phone)


async def get_user(pool, user_id: int):
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM users WHERE user_id=$1", user_id)


async def set_admin(pool, user_id: int, is_admin: bool):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET is_admin=$1 WHERE user_id=$2", is_admin, user_id)


async def get_admins(pool):
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM users WHERE is_admin = TRUE")


# =============================
# Работа со статусами
# =============================
async def add_status(pool, user_id: int, status: str, status_date=None):
    """Добавить или обновить статус пользователя на дату"""
    if status_date is None:
        status_date = date.today()

    if isinstance(status_date, str):
        status_date = datetime.strptime(status_date, "%Y-%m-%d").date()

    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO statuses (user_id, status, status_date)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id, status_date) DO UPDATE 
              SET status = EXCLUDED.status
        """, user_id, status, status_date)


async def get_status(pool, user_id: int, status_date=None):
    if status_date is None:
        status_date = date.today()
    if isinstance(status_date, str):
        status_date = datetime.strptime(status_date, "%Y-%m-%d").date()

    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM statuses WHERE user_id=$1 AND status_date=$2",
            user_id, status_date
        )


async def get_all_statuses(pool, status_date=None):
    """Получить статусы всех пользователей за дату"""
    if status_date is None:
        status_date = date.today()
    if isinstance(status_date, str):
        status_date = datetime.strptime(status_date, "%Y-%m-%d").date()

    async with pool.acquire() as conn:
        return await conn.fetch(
            "SELECT u.full_name, u.tab_number, s.status "
            "FROM users u "
            "LEFT JOIN statuses s ON u.user_id = s.user_id AND s.status_date=$1",
            status_date
        )
