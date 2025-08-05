import sqlite3

DB_FILE = "users.db"

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                full_name TEXT
            )
        ''')

def is_registered(user_id):
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
        return cur.fetchone() is not None

def register_user(user_id, full_name):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("INSERT OR REPLACE INTO users (user_id, full_name) VALUES (?, ?)", (user_id, full_name))

def get_full_name(user_id):
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.execute("SELECT full_name FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        return row[0] if row else None
