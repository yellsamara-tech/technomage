import os
import asyncpg
from datetime import date

DB_URL = os.getenv("DATABASE_URL")

# ----- Инициализация базы -----
async def init_db():
    conn = await asyncpg.connect(DB_URL)
    # Таблица пользователей
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id BIGINT PRIMARY KEY,
            full_name TEXT NOT NULL,
            status TEXT,
            last_update DATE,
            is_admin BOOLEAN DEFAULT FALSE
        )
    """)
    # Таблица истории статусов
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS status_history (
            user_id BIGINT REFERENCES users(id),
            status TEXT,
            status_date DATE,
            PRIMARY KEY(user_id, status_date)
        )
    """)
    await conn.close()

# ----- Добавление пользователя -----
async def add_user(user_id: int, full_name: str, is_admin: bool = False):
    conn = await asyncpg.connect(DB_URL)
    await conn.execute("""
        INSERT INTO users (id, full_name, is_admin) 
        VALUES ($1, $2, $3) 
        ON CONFLICT (id) DO NOTHING
    """, user_id, full_name, is_admin)
    await conn.close()

# ----- Получение пользователя -----
async def get_user(user_id: int):
    conn = await asyncpg.connect(DB_URL)
    row = await conn.fetchrow("SELECT * FROM users WHERE id=$1", user_id)
    await conn.close()
    return row

# ----- Обновление статуса -----
async def update_status(user_id: int, status: str):
    today = date.today()
    conn = await asyncpg.connect(DB_URL)
    # Обновляем текущий статус и дату последнего обновления
    await conn.execute("""
        UPDATE users SET status=$1, last_update=$2 WHERE id=$3
    """, status, today, user_id)
    # Добавляем запись в историю (ON CONFLICT обновляем запись)
    await conn.execute("""
        INSERT INTO status_history(user_id, status, status_date)
        VALUES($1, $2, $3)
        ON CONFLICT(user_id, status_date) DO UPDATE SET status=$2
    """, user_id, status, today)
    await conn.close()

# ----- Получение всех пользователей -----
async def get_all_users():
    conn = await asyncpg.connect(DB_URL)
    rows = await conn.fetch("SELECT * FROM users ORDER BY full_name")
    await conn.close()
    return rows

# ----- Получение админов -----
async def get_admins():
    conn = await asyncpg.connect(DB_URL)
    rows = await conn.fetch("SELECT * FROM users WHERE is_admin=TRUE")
    await conn.close()
    return rows

# ----- Назначение админа -----
async def make_admin(user_id: int):
    conn = await asyncpg.connect(DB_URL)
    await conn.execute("UPDATE users SET is_admin=TRUE WHERE id=$1", user_id)
    await conn.close()

# ----- Снятие прав админа -----
async def revoke_admin(user_id: int):
    conn = await asyncpg.connect(DB_URL)
    await conn.execute("UPDATE users SET is_admin=FALSE WHERE id=$1", user_id)
    await conn.close()

# ----- Получение истории пользователя -----
async def get_status_history(user_id: int):
    conn = await asyncpg.connect(DB_URL)
    rows = await conn.fetch(
        "SELECT status, status_date FROM status_history WHERE user_id=$1 ORDER BY status_date",
        user_id
    )
    await conn.close()
    return rows
