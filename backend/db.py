from pathlib import Path

import asyncpg

from . import config

pool: asyncpg.Pool | None = None


async def init():
    global pool
    pool = await asyncpg.create_pool(
        config.DATABASE_URL, min_size=1, max_size=5, statement_cache_size=0
    )
    sql = (Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")
    async with pool.acquire() as c:
        await c.execute(sql)


async def get_user(tg_id: int):
    return await pool.fetchrow(
        """INSERT INTO users (telegram_id) VALUES ($1)
           ON CONFLICT (telegram_id) DO UPDATE SET telegram_id = EXCLUDED.telegram_id
           RETURNING *""",
        tg_id,
    )


async def update_user(uid: int, **fields):
    sets = ", ".join(f"{k}=${i + 2}" for i, k in enumerate(fields))
    await pool.execute(f"UPDATE users SET {sets} WHERE id=$1", uid, *fields.values())


async def add_tx(user_id, kind, amount, currency, category, note, created_at=None):
    return await pool.fetchrow(
        """INSERT INTO transactions (user_id, kind, amount, currency, category_id, note, created_at)
           VALUES ($1, $2, $3, $4, (SELECT id FROM categories WHERE slug=$5), $6, COALESCE($7, now()))
           RETURNING id,
             (SELECT title FROM categories WHERE slug=$5) AS title,
             (SELECT icon FROM categories WHERE slug=$5) AS icon""",
        user_id, kind, amount, currency, category, note, created_at,
    )


async def all_tx(user_id: int):
    return await pool.fetch(
        """SELECT t.id, t.kind, t.amount, t.currency, t.note, t.created_at,
                  c.slug, c.title, c.icon
           FROM transactions t LEFT JOIN categories c ON c.id = t.category_id
           WHERE t.user_id=$1 ORDER BY t.created_at DESC""",
        user_id,
    )


async def delete_tx(user_id: int, tx_id: int):
    await pool.execute("DELETE FROM transactions WHERE id=$1 AND user_id=$2", tx_id, user_id)
