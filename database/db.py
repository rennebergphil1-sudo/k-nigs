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

            CREATE TABLE IF NOT EXISTS team_members (
                id SERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                position TEXT NOT NULL,
                rank_order INT DEFAULT 100,
                note TEXT,
                added_at TIMESTAMPTZ DEFAULT now(),
                UNIQUE(guild_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS user_xp (
                guild_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                xp INT DEFAULT 0,
                level INT DEFAULT 0,
                last_message TIMESTAMPTZ,
                PRIMARY KEY (guild_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS reaction_roles (
                id SERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                message_id BIGINT NOT NULL,
                role_id BIGINT NOT NULL,
                emoji TEXT,
                label TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS team_hierarchy (
                id SERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                role_id BIGINT NOT NULL,
                step INT NOT NULL,
                UNIQUE(guild_id, step),
                UNIQUE(guild_id, role_id)
            );

            CREATE TABLE IF NOT EXISTS warnings (
                id SERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                moderator_id BIGINT NOT NULL,
                reason TEXT,
                created_at TIMESTAMPTZ DEFAULT now()
            );

            CREATE TABLE IF NOT EXISTS giveaways (
                id SERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                channel_id BIGINT NOT NULL,
                message_id BIGINT NOT NULL,
                prize TEXT NOT NULL,
                winners_count INT DEFAULT 1,
                hosted_by BIGINT NOT NULL,
                ends_at TIMESTAMPTZ NOT NULL,
                ended BOOLEAN DEFAULT FALSE
            );

            CREATE TABLE IF NOT EXISTS giveaway_entries (
                giveaway_id INT REFERENCES giveaways(id) ON DELETE CASCADE,
                user_id BIGINT NOT NULL,
                PRIMARY KEY (giveaway_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id BIGINT PRIMARY KEY,
                welcome_channel_id BIGINT,
                welcome_message TEXT,
                leave_channel_id BIGINT,
                leave_message TEXT
            );

            CREATE TABLE IF NOT EXISTS tiktok_config (
                guild_id BIGINT PRIMARY KEY,
                tiktok_username TEXT NOT NULL,
                channel_id BIGINT NOT NULL,
                role_ping_id BIGINT,
                message TEXT,
                is_live BOOLEAN DEFAULT FALSE,
                last_notified_at TIMESTAMPTZ
            );

            CREATE TABLE IF NOT EXISTS voice_greet_config (
                guild_id BIGINT PRIMARY KEY,
                channel_id BIGINT NOT NULL,
                message TEXT
            );
            """
        )
