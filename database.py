import os
import asyncpg

DB_URL = os.getenv("DATABASE_URL")


async def init_db():
    conn = await asyncpg.connect(DB_URL)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            full_name TEXT NOT NULL
        );
    """)
    return conn


async def is_registered(conn, user_id):
    row = await conn.fetchrow("SELECT 1 FROM users WHERE user_id = $1", user_id)
    return row is not None


async def register_user(conn, user_id, full_name):
    await conn.execute(
        "INSERT INTO users (user_id, full_name) VALUES ($1, $2)",
        user_id, full_name
    )
