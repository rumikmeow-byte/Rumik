import aiosqlite
from datetime import date, datetime
from typing import Optional, List, Tuple

DB_PATH = "bot.db"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                balance REAL DEFAULT 0.0,
                referrals_count INTEGER DEFAULT 0,
                referred_by INTEGER DEFAULT NULL,
                last_roulette TEXT DEFAULT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS withdraw_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS promo_codes (
                code TEXT PRIMARY KEY,
                reward REAL NOT NULL,
                max_activations INTEGER NOT NULL,
                max_per_user INTEGER DEFAULT 1,
                current_activations INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS promo_activations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                activated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(code, user_id)
            )
        """)
        # Добавляем промокоды по умолчанию
        await db.execute("""
            INSERT OR IGNORE INTO promo_codes (code, reward, max_activations, max_per_user)
            VALUES 
                ('IZIDROP', 12.0, 100, 1),
                ('LOL10', 10.0, 10, 1)
        """)
        await db.commit()


async def get_user(user_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def create_user(user_id: int, username: str, full_name: str, referred_by: Optional[int] = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT OR IGNORE INTO users (user_id, username, full_name, referred_by)
               VALUES (?, ?, ?, ?)""",
            (user_id, username, full_name, referred_by)
        )
        await db.commit()


async def update_user_info(user_id: int, username: str, full_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET username = ?, full_name = ? WHERE user_id = ?",
            (username, full_name, user_id)
        )
        await db.commit()


async def add_balance(user_id: int, amount: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id = ?",
            (amount, user_id)
        )
        await db.commit()


async def set_balance(user_id: int, amount: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET balance = ? WHERE user_id = ?",
            (amount, user_id)
        )
        await db.commit()


async def increment_referrals(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET referrals_count = referrals_count + 1 WHERE user_id = ?",
            (user_id,)
        )
        await db.commit()


async def set_last_roulette(user_id: int, d: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET last_roulette = ? WHERE user_id = ?",
            (d, user_id)
        )
        await db.commit()


async def get_top_referrers(limit: int = 5) -> List[Tuple]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """SELECT user_id, username, full_name, referrals_count, balance
               FROM users
               WHERE referrals_count > 0
               ORDER BY referrals_count DESC
               LIMIT ?""",
            (limit,)
        ) as cursor:
            return await cursor.fetchall()


async def create_withdraw_request(user_id: int, amount: float) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO withdraw_requests (user_id, amount) VALUES (?, ?)",
            (user_id, amount)
        )
        await db.commit()
        return cursor.lastrowid
