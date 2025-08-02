import sqlite3
from datetime import datetime

DB_FILE = "status.db"

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        days_columns = ", ".join([f"d{i} TEXT" for i in range(1, 32)])
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                tab_number TEXT,
                full_name TEXT,
                {days_columns}
            )
        """)
        conn.commit()

def add_user(user_id, tab_number, full_name):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
        if cursor.fetchone():
            return
        cursor.execute("INSERT INTO users (user_id, tab_number, full_name) VALUES (?, ?, ?)", (user_id, tab_number, full_name))
        conn.commit()

def get_user_by_id(user_id):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return cursor.fetchone()

def update_status(user_id, day, status):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        column = f"d{day}"
        cursor.execute(f"UPDATE users SET {column} = ? WHERE user_id = ?", (status, user_id))
        conn.commit()

def get_status_matrix():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users")
        return cursor.fetchall()
