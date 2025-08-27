import aiosqlite
from datetime import date, datetime, timedelta

DB_FILE = "users.db"

# ----- Инициализация базы -----
async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                full_name TEXT NOT NULL,
                is_admin INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS status_history (
                user_id INTEGER,
                status TEXT,
                status_date DATE,
                PRIMARY KEY(user_id, status_date),
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY,
                reminder_time TEXT DEFAULT '18:00'
            )
        """)
        await db.commit()

# ----- Добавление пользователя -----
async def add_user(user_id: int, full_name: str, is_admin: bool = False):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
            INSERT OR IGNORE INTO users (id, full_name, is_admin)
            VALUES (?, ?, ?)
        """, (user_id, full_name, int(is_admin)))
        await db.commit()

# ----- Получение пользователя -----
async def get_user(user_id: int):
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT * FROM users WHERE id=?", (user_id,)) as cursor:
            return await cursor.fetchone()

# ----- Получение всех пользователей -----
async def get_all_users():
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT * FROM users ORDER BY full_name") as cursor:
            return await cursor.fetchall()

# ----- Получение всех админов -----
async def get_admins():
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT * FROM users WHERE is_admin=1") as cursor:
            return await cursor.fetchall()

# ----- Назначить админа -----
async def make_admin(user_id: int):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("UPDATE users SET is_admin=1 WHERE id=?", (user_id,))
        await db.commit()

# ----- Снять админа -----
async def revoke_admin(user_id: int):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("UPDATE users SET is_admin=0 WHERE id=?", (user_id,))
        await db.commit()

# ----- Удаление пользователя -----
async def delete_user(user_id: int):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("DELETE FROM users WHERE id=?", (user_id,))
        await db.execute("DELETE FROM status_history WHERE user_id=?", (user_id,))
        await db.commit()

# ----- Обновление статуса -----
async def update_status(user_id: int, status: str):
    today = date.today()
    async with aiosqlite.connect(DB_FILE) as db:
        # Вставка или обновление статуса на сегодня
        await db.execute("""
            INSERT INTO status_history(user_id, status, status_date)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, status_date) DO UPDATE SET status=excluded.status
        """, (user_id, status, today))
        await db.commit()

# ----- Получение истории пользователя -----
async def get_status_history(user_id: int):
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("""
            SELECT status, status_date FROM status_history
            WHERE user_id=? ORDER BY status_date
        """, (user_id,)) as cursor:
            return await cursor.fetchall()

# ----- Статистика по статусам за сегодня -----
async def get_today_status_stats():
    today = date.today()
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("""
            SELECT status, COUNT(*) FROM status_history
            WHERE status_date=?
            GROUP BY status
        """, (today,)) as cursor:
            return await cursor.fetchall()

# ----- Время ежедневного напоминания -----
async def set_reminder_time(time_str: str):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("DELETE FROM reminders")
        await db.execute("INSERT INTO reminders (reminder_time) VALUES (?)", (time_str,))
        await db.commit()

async def get_reminder_time():
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT reminder_time FROM reminders ORDER BY id DESC LIMIT 1") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else "18:00"
