import asyncpg

CREATE_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    full_name TEXT NOT NULL
);
"""

class Database:
    def __init__(self, dsn):
        self.dsn = dsn
        self.pool = None

    async def connect(self):
        self.pool = await asyncpg.create_pool(self.dsn)
        async with self.pool.acquire() as conn:
            await conn.execute(CREATE_USERS_TABLE)

    async def close(self):
        await self.pool.close()

    async def is_registered(self, user_id: int) -> bool:
        async with self.pool.acquire() as conn:
            result = await conn.fetchval(
                "SELECT 1 FROM users WHERE user_id = $1", user_id
            )
            return result is not None

    async def register_user(self, user_id: int, full_name: str):
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO users(user_id, full_name) 
                VALUES($1, $2) ON CONFLICT (user_id) DO NOTHING
                """,
                user_id,
                full_name,
            )

    async def get_full_name(self, user_id: int) -> str | None:
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT full_name FROM users WHERE user_id = $1", user_id
            )
