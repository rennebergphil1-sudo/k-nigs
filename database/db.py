import asyncpg
import config

_pool: asyncpg.Pool | None = None


async def init_pool():
    global _pool
    _pool = await asyncpg.create_pool(config.DATABASE_URL, min_size=1, max_size=10)
    await _create_schema()
    return _pool


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB Pool wurde noch nicht initialisiert. init_pool() zuerst aufrufen.")
    return _pool


async def _create_schema():
    async with _pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS characters (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                guild_id BIGINT NOT NULL,
                name TEXT NOT NULL,
                faction TEXT,
                backstory TEXT,
                image_url TEXT,
                stats JSONB DEFAULT '{}',
                created_at TIMESTAMPTZ DEFAULT now(),
                UNIQUE(user_id, guild_id, name)
            );

            CREATE TABLE IF NOT EXISTS inventory_items (
                id SERIAL PRIMARY KEY,
                character_id INT REFERENCES characters(id) ON DELETE CASCADE,
                item_name TEXT NOT NULL,
                quantity INT DEFAULT 1,
                description TEXT
            );

            CREATE TABLE IF NOT EXISTS rp_scenes (
                id SERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                channel_id BIGINT NOT NULL,
                title TEXT NOT NULL,
                created_by BIGINT NOT NULL,
                archived BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMPTZ DEFAULT now()
            );

            CREATE TABLE IF NOT EXISTS support_tickets (
                id SERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                channel_id BIGINT NOT NULL,
                opened_by BIGINT NOT NULL,
                status TEXT DEFAULT 'open',
                created_at TIMESTAMPTZ DEFAULT now(),
                closed_at TIMESTAMPTZ
            );

            CREATE TABLE IF NOT EXISTS security_events (
                id SERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                user_id BIGINT,
                event_type TEXT NOT NULL,
                details TEXT,
                created_at TIMESTAMPTZ DEFAULT now()
            );
            """
        )
