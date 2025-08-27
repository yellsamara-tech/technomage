import asyncpg
from datetime import date, datetime
import os

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL не найден в переменных окружения")

# ----- Инициализация базы -----
async def init_db():
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id BIGINT PRIMARY KEY,
        full_name TEXT NOT NULL,
        is_admin BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT NOW()
    )
    """)
    await conn.execute("""
    CREATE TABLE IF NOT EXISTS statuses (
        id SERIAL PRIMARY KEY,
        user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
        status TEXT NOT NULL,
        status_date DATE NOT NULL
    )
    """)
    await conn.close()

# ----- Пользователи -----
async def add_user(user_id: int, full_name: str, is_admin: bool = False):
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute(
        "INSERT INTO users (id, full_name, is_admin) VALUES ($1, $2, $3) ON CONFLICT (id) DO NOTHING",
        user_id, full_name, is_admin
    )
    await conn.close()

async def get_user(user_id: int):
    conn = await asyncpg.connect(DATABASE_URL)
    row = await conn.fetchrow("SELECT id, full_name, is_admin FROM users WHERE id = $1", user_id)
    await conn.close()
    if row:
        return {"id": row["id"], "full_name": row["full_name"], "is_admin": row["is_admin"]}
    return None

async def get_all_users():
    conn = await asyncpg.connect(DATABASE_URL)
    rows = await conn.fetch("SELECT id, full_name, is_admin FROM users")
    await conn.close()
    return [{"id": r["id"], "full_name": r["full_name"], "is_admin": r["is_admin"]} for r in rows]

async def delete_user(user_id: int):
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("DELETE FROM users WHERE id = $1", user_id)
    await conn.close()

# ----- Статусы -----
async def update_status(user_id: int, status: str):
    today = date.today()
    conn = await asyncpg.connect(DATABASE_URL)
    existing = await conn.fetchrow(
        "SELECT id FROM statuses WHERE user_id=$1 AND status_date=$2",
        user_id, today
    )
    if existing:
        await conn.execute("UPDATE statuses SET status=$1 WHERE id=$2", status, existing["id"])
    else:
        await conn.execute(
            "INSERT INTO statuses (user_id, status, status_date) VALUES ($1, $2, $3)",
            user_id, status, today
        )
    await conn.close()

async def get_status_history(user_id: int, status_date: date = None):
    conn = await asyncpg.connect(DATABASE_URL)
    if status_date:
        rows = await conn.fetch(
            "SELECT status, status_date FROM statuses WHERE user_id=$1 AND status_date=$2 ORDER BY status_date ASC",
            user_id, status_date
        )
    else:
        rows = await conn.fetch(
            "SELECT status, status_date FROM statuses WHERE user_id=$1 ORDER BY status_date ASC",
            user_id
        )
    await conn.close()
    return [{"status": r["status"], "status_date": r["status_date"]} for r in rows]

async def get_status_statistics(stat_date: date = None):
    conn = await asyncpg.connect(DATABASE_URL)
    if stat_date:
        rows = await conn.fetch(
            "SELECT status, COUNT(*) as count FROM statuses WHERE status_date=$1 GROUP BY status",
            stat_date
        )
    else:
        rows = await conn.fetch(
            "SELECT status, COUNT(*) as count FROM statuses GROUP BY status"
        )
    await conn.close()
    return {r["status"]: r["count"] for r in rows}

async def get_users_without_status_today():
    today = date.today()
    conn = await asyncpg.connect(DATABASE_URL)
    rows = await conn.fetch("""
        SELECT id, full_name FROM users
        WHERE id NOT IN (
            SELECT user_id FROM statuses WHERE status_date=$1
        )
    """, today)
    await conn.close()
    return [{"id": r["id"], "full_name": r["full_name"]} for r in rows]

# ----- Админы -----
async def get_admins():
    conn = await asyncpg.connect(DATABASE_URL)
    rows = await conn.fetch("SELECT id, full_name FROM users WHERE is_admin=TRUE")
    await conn.close()
    return [{"id": r["id"], "full_name": r["full_name"], "is_admin": True} for r in rows]

async def make_admin(user_id: int):
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("UPDATE users SET is_admin=TRUE WHERE id=$1", user_id)
    await conn.close()

async def revoke_admin(user_id: int):
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("UPDATE users SET is_admin=FALSE WHERE id=$1", user_id)
    await conn.close()
