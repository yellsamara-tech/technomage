import os
import psycopg2

DB_URL = os.environ["DATABASE_URL"]

def connect():
    return psycopg2.connect(DB_URL, sslmode="require")

def init_db():
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    full_name TEXT NOT NULL
                )
            """)
            conn.commit()

def is_registered(user_id):
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM users WHERE user_id = %s", (user_id,))
            return cur.fetchone() is not None

def register_user(user_id, full_name):
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO users (user_id, full_name)
                VALUES (%s, %s)
                ON CONFLICT (user_id) DO UPDATE SET full_name = EXCLUDED.full_name
            """, (user_id, full_name))
            conn.commit()

def get_full_name(user_id):
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT full_name FROM users WHERE user_id = %s", (user_id,))
            row = cur.fetchone()
            return row[0] if row else None
