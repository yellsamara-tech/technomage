import psycopg

def init_db():
    conn = psycopg.connect(conninfo=os.getenv("DATABASE_URL"))
    with conn.cursor() as cur:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            full_name TEXT
        )
        """)
        conn.commit()
    return conn

# пример запроса
def is_registered(user_id, conn):
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM users WHERE user_id = %s", (user_id,))
        return cur.fetchone() is not None

def register_user(user_id, full_name, conn):
    with conn.cursor() as cur:
        cur.execute("INSERT INTO users (user_id, full_name) VALUES (%s, %s) ON CONFLICT (user_id) DO NOTHING", (user_id, full_name))
        conn.commit()

def get_full_name(user_id, conn):
    with conn.cursor() as cur:
        cur.execute("SELECT full_name FROM users WHERE user_id = %s", (user_id,))
        row = cur.fetchone()
        return row[0] if row else None
