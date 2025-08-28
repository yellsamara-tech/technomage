import asyncpg
from datetime import date, datetime
import os

DB_URL = os.getenv("DATABASE_URL")
pool = None

async def init_db():
    global pool
    pool = await asyncpg.create_pool(DB_URL)
    async with pool.acquire() as conn:
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            full_name TEXT,
            tab_number TEXT,
            phone TEXT,
            is_admin BOOLEAN DEFAULT FALSE
        );
        """)
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS user_statuses (
            user_id BIGINT,
            log_date DATE,
            status TEXT,
            PRIMARY KEY(user_id, log_date)
        );
        """)

async def add_user(user_id, full_name, tab_number="", phone="", is_admin=False):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users(user_id, full_name, tab_number, phone, is_admin)
            VALUES($1,$2,$3,$4,$5) ON CONFLICT(user_id) DO NOTHING
        """, user_id, full_name, tab_number, phone, is_admin)

async def get_user(user_id):
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM users WHERE user_id=$1", user_id)

async def get_all_users():
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM users ORDER BY full_name")

async def make_admin(user_id):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET is_admin=TRUE WHERE user_id=$1", user_id)

async def revoke_admin(user_id):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET is_admin=FALSE WHERE user_id=$1", user_id)

async def delete_user(user_id):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM users WHERE user_id=$1", user_id)
        await conn.execute("DELETE FROM user_statuses WHERE user_id=$1", user_id)

async def update_status(user_id, status, log_date=None):
    log_date = log_date or date.today()
    if isinstance(log_date, str):
        log_date = datetime.strptime(log_date, "%Y-%m-%d").date()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO user_statuses(user_id, log_date, status)
            VALUES($1,$2,$3)
            ON CONFLICT(user_id, log_date) DO UPDATE SET status=EXCLUDED.status
        """, user_id, log_date, status)

async def get_status_history(user_id, log_date=None):
    async with pool.acquire() as conn:
        if log_date:
            if isinstance(log_date, str):
                log_date = datetime.strptime(log_date, "%Y-%m-%d").date()
            return await conn.fetch("SELECT * FROM user_statuses WHERE user_id=$1 AND log_date=$2", user_id, log_date)
        return await conn.fetch("SELECT * FROM user_statuses WHERE user_id=$1 ORDER BY log_date", user_id)
