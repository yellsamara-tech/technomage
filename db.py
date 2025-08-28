import asyncpg
import os
import logging

pool = None

async def init_db():
    """
    Создаём подключение к PostgreSQL
    """
    global pool
    if pool is None:
        db_url = os.getenv("DATABASE_URL")
        logging.info(f"Подключение к БД: {db_url}")
        pool = await asyncpg.create_pool(dsn=db_url)
    return pool


async def get_user(user_id: int):
    """
    Получить пользователя из таблицы users
    """
    global pool
    if pool is None:
        await init_db()
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)


async def add_user(user_id: int, name: str):
    """
    Добавить пользователя в таблицу users
    """
    global pool
    if pool is None:
        await init_db()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users (id, name)
            VALUES ($1, $2)
            ON CONFLICT (id) DO NOTHING
            """,
            user_id, name
        )
