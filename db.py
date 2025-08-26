import os
import asyncpg

DB_URL = os.getenv("DATABASE_URL")  # Render автоматически даст эту переменную

async def init_db():
    conn = await asyncpg.connect(DB_URL)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id BIGINT PRIMARY KEY,
            full_name TEXT NOT NULL
        )
    """)
    await conn.close()

async def add_user(user_id: int, full_name: str):
    conn = await asyncpg.connect(DB_URL)
    await conn.execute("INSERT INTO users (id, full_name) VALUES ($1, $2) ON CONFLICT (id) DO NOTHING", user_id, full_name)
    await conn.close()

async def get_user(user_id: int):
    conn = await asyncpg.connect(DB_URL)
    row = await conn.fetchrow("SELECT * FROM users WHERE id=$1", user_id)
    await conn.close()
    return row
