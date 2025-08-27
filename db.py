import aiosqlite
from datetime import date, datetime

DB_PATH = "bot.db"

# ----------------- Инициализация базы -----------------
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                full_name TEXT,
                is_admin INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS status_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                status TEXT,
                status_date DATE,
                status_time TIME,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)
        await db.commit()

# ----------------- Пользователи -----------------
async def add_user(user_id: int, full_name: str, is_admin: bool = False):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO users (id, full_name, is_admin) VALUES (?, ?, ?)",
            (user_id, full_name, int(is_admin))
        )
        await db.commit()

async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, full_name, is_admin FROM users WHERE id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"id": row[0], "full_name": row[1], "is_admin": bool(row[2])}
            return None

async def get_all_users():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, full_name, is_admin FROM users") as cursor:
            rows = await cursor.fetchall()
            return [{"id": r[0], "full_name": r[1], "is_admin": bool(r[2])} for r in rows]

async def get_admins():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, full_name FROM users WHERE is_admin = 1") as cursor:
            rows = await cursor.fetchall()
            return [{"id": r[0], "full_name": r[1]} for r in rows]

async def make_admin(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_admin = 1 WHERE id = ?", (user_id,))
        await db.commit()

async def revoke_admin(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_admin = 0 WHERE id = ?", (user_id,))
        await db.commit()

async def delete_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM users WHERE id = ?", (user_id,))
        await db.execute("DELETE FROM status_history WHERE user_id = ?", (user_id,))
        await db.commit()

# ----------------- Статусы -----------------
async def update_status(user_id: int, status: str):
    today = date.today()
    now = datetime.now().time()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO status_history (user_id, status, status_date, status_time) VALUES (?, ?, ?, ?)",
            (user_id, status, today, now)
        )
        await db.commit()

async def get_status_history(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT status, status_date, status_time FROM status_history WHERE user_id = ? ORDER BY id DESC",
            (user_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [{"status": r[0], "status_date": r[1], "status_time": r[2]} for r in rows]
