import os
import asyncpg

DB_URL = os.getenv("DATABASE_URL")  # Render автоматически подставит это значение

# Инициализация базы
async def init_db():
    conn = await asyncpg.connect(DB_URL)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id BIGINT PRIMARY KEY,
            full_name TEXT NOT NULL,
            status TEXT
        )
    """)
    await conn.close()

# Добавление пользователя (без статуса)
async def add_user(user_id: int, full_name: str):
    conn = await asyncpg.connect(DB_URL)
    await conn.execute(
        "INSERT INTO users (id, full_name) VALUES ($1, $2) ON CONFLICT (id) DO NOTHING",
        user_id, full_name
    )
    await conn.close()

# Получение пользователя по ID
async def get_user(user_id: int):
    conn = await asyncpg.connect(DB_URL)
    row = await conn.fetchrow("SELECT * FROM users WHERE id=$1", user_id)
    await conn.close()
    return row

# Обновление статуса
async def update_status(user_id: int, status: str):
    conn = await asyncpg.connect(DB_URL)
    await conn.execute(
        "UPDATE users SET status=$1 WHERE id=$2",
        status, user_id
    )
    await conn.close()

# Получение всех пользователей (например, для админов)
async def get_all_users():
    conn = await asyncpg.connect(DB_URL)
    rows = await conn.fetch("SELECT * FROM users ORDER BY full_name")
    await conn.close()
    return rows
