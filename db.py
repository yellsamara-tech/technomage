import aiosqlite
from datetime import date

DB_FILE = "bot.db"

# ----- Инициализация базы -----
async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            full_name TEXT,
            is_admin INTEGER DEFAULT 0,
            status TEXT,
            tabel TEXT
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS status_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            status TEXT,
            status_date DATE
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """)
        await db.commit()

# ----- Пользователи -----
async def add_user(user_id, full_name, is_admin=False):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
            INSERT OR IGNORE INTO users (id, full_name, is_admin)
            VALUES (?, ?, ?)
        """, (user_id, full_name, int(is_admin)))
        await db.commit()

async def get_user(user_id):
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT * FROM users WHERE id=?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"id": row[0], "full_name": row[1], "is_admin": bool(row[2]), "status": row[3], "tabel": row[4]}
            return None

async def get_all_users():
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT * FROM users") as cursor:
            rows = await cursor.fetchall()
            return [{"id": r[0], "full_name": r[1], "is_admin": bool(r[2]), "status": r[3], "tabel": r[4]} for r in rows]

async def get_admins():
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT * FROM users WHERE is_admin=1") as cursor:
            rows = await cursor.fetchall()
            return [{"id": r[0], "full_name": r[1], "is_admin": True, "status": r[3], "tabel": r[4]} for r in rows]

async def make_admin(user_id):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("UPDATE users SET is_admin=1 WHERE id=?", (user_id,))
        await db.commit()

async def revoke_admin(user_id):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("UPDATE users SET is_admin=0 WHERE id=?", (user_id,))
        await db.commit()

async def delete_user(user_id):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("DELETE FROM users WHERE id=?", (user_id,))
        await db.execute("DELETE FROM status_history WHERE user_id=?", (user_id,))
        await db.commit()

# ----- Статусы -----
async def update_status(user_id, status):
    today = date.today()
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("UPDATE users SET status=? WHERE id=?", (status, user_id))
        # сохраняем историю
        await db.execute("""
            INSERT INTO status_history (user_id, status, status_date)
            VALUES (?, ?, ?)
        """, (user_id, status, today))
        await db.commit()

async def get_status_history(user_id):
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT status, status_date FROM status_history WHERE user_id=? ORDER BY status_date DESC", (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [{"status": r[0], "status_date": r[1]} for r in rows]

# ----- Настройки -----
async def set_reminder_time(hour, minute):
    async with aiosqlite.connect(DB_FILE) as db:
        value = f"{hour:02d}:{minute:02d}"
        await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('reminder_time', ?)", (value,))
        await db.commit()

async def get_reminder_time():
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT value FROM settings WHERE key='reminder_time'") as cursor:
            row = await cursor.fetchone()
            if row:
                hour, minute = map(int, row[0].split(":"))
                return {"hour": hour, "minute": minute}
            return None
