import asyncio
import html
import logging
import os
import random
from datetime import date, datetime
from typing import Optional, List, Dict, Any

import asyncpg
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from topup import register_topup_handlers


# =========================================================
# НАСТРОЙКИ
# =========================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
SUPPORT_ID = int(os.getenv("SUPPORT_ID", "0"))

SUPPORT_USERNAME = "@Eclipsed_consult"

MIN_WITHDRAW = 15
REF_BONUS = 0.85

# Фото главного меню — 768x439
MENU_PHOTO = (
    "AgACAgIAAxkBAAEuWDpqmWLboBOFIlHcmgpylNym1rLLIgACSB1rG8qiyEgmn7iMl-EITAEAAwIAA3gAAz0E"
)

# Обязательные каналы/чаты (будут добавлены при первом запуске)
DEFAULT_REQUIRED = [
    {"chat_id": "@eclipsedlf", "title": "Канал"},
    {"chat_id": "@GiftsEzzChat", "title": "Чат"},
]


if not BOT_TOKEN:
    raise ValueError("Переменная BOT_TOKEN не задана!")

if not DATABASE_URL:
    raise ValueError("Переменная DATABASE_URL не задана!")


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
db_pool = None

# TOPUP_INTEGRATION_V1
register_topup_handlers(dp, bot, lambda: db_pool, SUPPORT_ID)

# BALANCE_BUTTON_V1
@dp.callback_query(F.data == "balance")
async def balance_callback(call: types.CallbackQuery):
    data = await get_user_data(str(call.from_user.id))
    balance = data.get("balance", 0) if data else 0
    await call.answer(f"Ваш баланс: {balance} ⭐", show_alert=True)



# =========================================================
# СОСТОЯНИЯ
# =========================================================

class WithdrawStates(StatesGroup):
    waiting_for_amount = State()


class AdminStates(StatesGroup):
    waiting_for_give_data = State()
    waiting_for_give_refs = State()
    waiting_for_delete_refs = State()
    waiting_for_broadcast_msg = State()
    waiting_for_new_channel = State()


# =========================================================
# БАЗА ДАННЫХ POSTGRESQL
# =========================================================

async def init_db():
    global db_pool

    logger.info("Подключение к PostgreSQL...")

    db_pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=1,
        max_size=5,
        command_timeout=60
    )

    async with db_pool.acquire() as db:

        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                balance NUMERIC(12, 2) NOT NULL DEFAULT 0,
                refs INTEGER NOT NULL DEFAULT 0,
                referred_by BIGINT DEFAULT NULL,
                ref_credited BOOLEAN NOT NULL DEFAULT FALSE,
                last_daily DATE DEFAULT NULL
            )
        """)

        # Добавляем колонку full_name, если её ещё нет
        await db.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS full_name TEXT
        """)

        await db.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS ref_credited
            BOOLEAN NOT NULL DEFAULT FALSE
        """)

        # Новая таблица для лидеров
        await db.execute("""
            CREATE TABLE IF NOT EXISTS leaders (
                user_id BIGINT PRIMARY KEY,
                refs INTEGER NOT NULL DEFAULT 0,
                username TEXT,
                full_name TEXT,
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        # Добавляем колонку full_name, если её нет
        await db.execute("""
            ALTER TABLE leaders
            ADD COLUMN IF NOT EXISTS full_name TEXT
        """)

        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_leaders_refs
            ON leaders(refs DESC)
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS topup_requests (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                username TEXT,
                full_name TEXT,
                amount NUMERIC(12, 2) NOT NULL,
                gift_name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                processed_by BIGINT DEFAULT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS required_chats (
                id SERIAL PRIMARY KEY,
                chat_id TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS withdrawals (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                username TEXT,
                full_name TEXT,
                amount NUMERIC(12, 2) NOT NULL,
                balance_before NUMERIC(12, 2) NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                admin_message_id BIGINT
            )
        """)

        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_refs
            ON users(refs DESC)
        """)

        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_withdrawals_user
            ON withdrawals(user_id)
        """)

        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_withdrawals_status
            ON withdrawals(status)
        """)

        for chat in DEFAULT_REQUIRED:
            await db.execute("""
                INSERT INTO required_chats (chat_id, title)
                VALUES ($1, $2)
                ON CONFLICT (chat_id) DO NOTHING
            """, chat["chat_id"], chat["title"])

    logger.info("PostgreSQL успешно подключён!")


async def close_db():
    global db_pool

    if db_pool:
        await db_pool.close()
        logger.info("Соединение с PostgreSQL закрыто.")
