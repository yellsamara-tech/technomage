import os
import asyncpg
from datetime import date

DB_URL = os.getenv("DATABASE_URL")

# Инициализация базы
async def init_db():
    conn = await asyncpg.connect(DB_URL)
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
    await conn.close()

async def add_user(user_id: int, full_name: str):
    conn = await asyncpg.connect(DB_URL)
    await conn.execute(
        "INSERT INTO users (id, full_name) VALUES ($1, $2) ON CONFLICT (id) DO NOTHING",
        user_id, full_name
    )
    await conn.close()

async def get_user(user_id: int):
    conn = await asyncpg.connect(DB_URL)
    row = await conn.fetchrow("SELECT * FROM users WHERE id=$1", user_id)
    await conn.close()
    return row

async def update_status(user_id: int, status: str):
    today = date.today()
    conn = await asyncpg.connect(DB_URL)
    # Обновляем текущий статус в users
    await conn.execute("UPDATE users SET status=$1 WHERE id=$2", status, user_id)
    # Добавляем запись в историю (ON CONFLICT — обновляем запись на этот день)
    await conn.execute("""
        INSERT INTO status_history(user_id, status, status_date)
        VALUES($1, $2, $3)
        ON CONFLICT(user_id, status_date) DO UPDATE SET status=$2
    """, user_id, status, today)
    await conn.close()

async def get_all_users():
    conn = await asyncpg.connect(DB_URL)
    rows = await conn.fetch("SELECT * FROM users ORDER BY full_name")
    await conn.close()
    return rows

async def get_status_history(user_id: int):
    conn = await asyncpg.connect(DB_URL)
    rows = await conn.fetch(
        "SELECT status, status_date FROM status_history WHERE user_id=$1 ORDER BY status_date",
        user_id
    )
    await conn.close()
    return rows

async def find_user_by_name(name: str):
    conn = await asyncpg.connect(DB_URL)
    rows = await conn.fetch("SELECT * FROM users WHERE full_name ILIKE $1", f"%{name}%")
    await conn.close()
    return rows

async def set_user_status(user_id: int, status: str):
    await update_status(user_id, status)

async def get_admins():
    conn = await asyncpg.connect(DB_URL)
    rows = await conn.fetch("SELECT * FROM users WHERE is_admin=TRUE")
    await conn.close()
    return rows
