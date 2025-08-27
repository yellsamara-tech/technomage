import aiosqlite
from datetime import datetime, date

DB_FILE = "users.db"

# ----- Инициализация базы -----
async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            full_name TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS statuses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            status_date TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """)
        await db.commit()

# ----- Пользователи -----
async def add_user(user_id: int, full_name: str, is_admin: bool = False):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (id, full_name, is_admin) VALUES (?, ?, ?)",
            (user_id, full_name, int(is_admin))
        )
        await db.commit()

async def get_user(user_id: int):
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT * FROM users WHERE id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"id": row[0], "full_name": row[1], "is_admin": bool(row[2])}
            return None

async def get_all_users():
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT * FROM users") as cursor:
            rows = await cursor.fetchall()
            return [{"id": r[0], "full_name": r[1], "is_admin": bool(r[2])} for r in rows]

async def delete_user(user_id: int):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("DELETE FROM users WHERE id = ?", (user_id,))
        await db.execute("DELETE FROM statuses WHERE user_id = ?", (user_id,))
        await db.commit()

# ----- Статусы -----
async def update_status(user_id: int, status: str):
    today = date.today().isoformat()
    async with aiosqlite.connect(DB_FILE) as db:
        # Проверяем, есть ли уже статус за сегодня
        async with db.execute(
            "SELECT id FROM statuses WHERE user_id = ? AND status_date = ?",
            (user_id, today)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                await db.execute("UPDATE statuses SET status = ? WHERE id = ?", (status, row[0]))
            else:
                await db.execute(
                    "INSERT INTO statuses (user_id, status, status_date) VALUES (?, ?, ?)",
                    (user_id, status, today)
                )
        await db.commit()

async def get_status_history(user_id: int, status_date: str = None):
    async with aiosqlite.connect(DB_FILE) as db:
        query = "SELECT status, status_date FROM statuses WHERE user_id = ?"
        params = [user_id]
        if status_date:
            query += " AND status_date = ?"
            params.append(status_date)
        async with db.execute(query, tuple(params)) as cursor:
            rows = await cursor.fetchall()
            return [{"status": r[0], "status_date": r[1]} for r in rows]

async def get_status_statistics(stat_date: str = None):
    """Возвращает статистику по статусам всех пользователей за выбранную дату"""
    async with aiosqlite.connect(DB_FILE) as db:
        query = "SELECT status, COUNT(*) FROM statuses"
        params = []
        if stat_date:
            query += " WHERE status_date = ?"
            params.append(stat_date)
        query += " GROUP BY status"
        async with db.execute(query, tuple(params)) as cursor:
            rows = await cursor.fetchall()
            return {r[0]: r[1] for r in rows}

# ----- Админы -----
async def get_admins():
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT * FROM users WHERE is_admin = 1") as cursor:
            rows = await cursor.fetchall()
            return [{"id": r[0], "full_name": r[1], "is_admin": True} for r in rows]

async def make_admin(user_id: int):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("UPDATE users SET is_admin = 1 WHERE id = ?", (user_id,))
        await db.commit()

async def revoke_admin(user_id: int):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("UPDATE users SET is_admin = 0 WHERE id = ?", (user_id,))
        await db.commit()
