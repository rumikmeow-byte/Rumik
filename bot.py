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


async def ensure_user(user_id: str, username: str = "", full_name: str = ""):
    """Сохраняет или обновляет пользователя в БД."""
    async with db_pool.acquire() as db:
        await db.execute("""
            INSERT INTO users (user_id, username, full_name)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id)
            DO UPDATE SET
                username = EXCLUDED.username,
                full_name = EXCLUDED.full_name
            WHERE EXCLUDED.username IS NOT NULL AND EXCLUDED.username <> ''
               OR EXCLUDED.full_name IS NOT NULL AND EXCLUDED.full_name <> ''
        """, int(user_id), username, full_name)


async def get_user_data(user_id: str) -> Dict[str, Any]:
    async with db_pool.acquire() as db:
        row = await db.fetchrow(
            "SELECT * FROM users WHERE user_id = $1",
            int(user_id)
        )

        return dict(row) if row else {}


async def get_required_chats() -> List[Dict[str, str]]:
    async with db_pool.acquire() as db:
        rows = await db.fetch(
            "SELECT id, chat_id, title FROM required_chats ORDER BY id"
        )

        return [dict(row) for row in rows]


async def check_subscription(user_id: int) -> bool:
    """Проверяет подписку на все обязательные каналы/чаты."""

    chats = await get_required_chats()

    if not chats:
        return True

    for chat in chats:
        try:
            member = await bot.get_chat_member(
                chat_id=chat["chat_id"],
                user_id=user_id
            )

            if member.status in ("left", "kicked"):
                return False

        except Exception as e:
            logger.warning(
                f"Ошибка проверки {chat['chat_id']}: {e}"
            )
            return False

    return True


async def credit_referral_if_needed(user_id: int):
    """Начисляет реферальный бонус после полной подписки."""

    async with db_pool.acquire() as db:
        async with db.transaction():

            row = await db.fetchrow("""
                SELECT referred_by, ref_credited
                FROM users
                WHERE user_id = $1
                FOR UPDATE
            """, user_id)

            if not row:
                return

            if not row["referred_by"]:
                return

            if row["ref_credited"]:
                return

            ref_id = row["referred_by"]

            await db.execute("""
                UPDATE users
                SET refs = refs + 1,
                    balance = balance + $1
                WHERE user_id = $2
            """, REF_BONUS, ref_id)

            await db.execute("""
                UPDATE users
                SET ref_credited = TRUE
                WHERE user_id = $1
            """, user_id)

    try:
        await bot.send_message(
            ref_id,
            f"🎉 <b>Новый реферал!</b>\n\n"
            f"⭐ Вам начислено <b>+{REF_BONUS:.2f} ⭐</b>\n"
            f"(пользователь подписался на все каналы)",
            parse_mode="HTML"
        )
    except Exception:
        pass

    # Обновить таблицу лидеров для реферера
    await update_leader(ref_id)


# =========================================================
# ФУНКЦИЯ ОБНОВЛЕНИЯ ТАБЛИЦЫ ЛИДЕРОВ (переписана)
# =========================================================

async def update_leader(user_id: int):
    """Обновляет запись в таблице leaders на основе данных из users."""
    async with db_pool.acquire() as db:
        row = await db.fetchrow(
            "SELECT refs, username, full_name FROM users WHERE user_id = $1",
            user_id
        )
        if not row:
            await db.execute(
                "DELETE FROM leaders WHERE user_id = $1",
                user_id
            )
            return
        refs = row["refs"]
        username = row.get("username")
        full_name = row.get("full_name")
        await db.execute("""
            INSERT INTO leaders (user_id, username, full_name, refs, updated_at)
            VALUES ($1, $2, $3, $4, NOW())
            ON CONFLICT (user_id)
            DO UPDATE SET
                username = EXCLUDED.username,
                full_name = EXCLUDED.full_name,
                refs = EXCLUDED.refs,
                updated_at = NOW()
        """, user_id, username, full_name, refs)


# =========================================================
# WEB-SERVER ДЛЯ RENDER
# =========================================================

async def health_check(request):
    return web.Response(text="GiftsMMS Bot is running!")


async def start_web_server():
    app = web.Application()

    app.router.add_get("/", health_check)
    app.router.add_get("/health", health_check)

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.getenv("PORT", "10000"))

    site = web.TCPSite(
        runner,
        "0.0.0.0",
        port
    )

    await site.start()

    logger.info(
        f"Web-server запущен на порту {port}"
    )

    return runner


# =========================================================
# КЛАВИАТУРЫ
# =========================================================

BUTTON_TEXTS = {
    "channel": "📢 Канал",
    "support": "💬 Поддержка",
    "referrals": "🎁 Рефералы",
    "roulette": "🎰 Рулетка",
    "withdraw": "💳 Вывод",
    "leaders": "👑 Лидеры по рефералам",
    "admin": "⚙️ Админ-панель",
}


def main_menu_keyboard(
    user_id: int,
    support_id: Optional[int] = None
) -> InlineKeyboardMarkup:

    if support_id is None:
        support_id = SUPPORT_ID

    # Группы кнопок
    buttons = [
        # Группа 1: Канал и Поддержка
        [
            InlineKeyboardButton(
                text="📢 Канал",
                url="https://t.me/eclipsedlf"
            ),
            InlineKeyboardButton(
                text="💬 Поддержка",
                url="https://t.me/Eclipsed_consult"
            ),
        ],
        # Группа 2: Рефералы
        [
            InlineKeyboardButton(
                text="🎁 Рефералы",
                callback_data="referrals"
            ),
        ],
        # Группа 3: Рулетка и Вывод
        [
            InlineKeyboardButton(
                text="🎰 Рулетка",
                callback_data="roulette"
            ),
            InlineKeyboardButton(
                text="💳 Вывод",
                callback_data="withdraw"
            ),
        ],
        # Группа 4: Лидеры
        [
            InlineKeyboardButton(
                text="👑 Лидеры по рефералам",
                callback_data="leaders"
            ),
        ],
    ]

    # Если админ – добавляем админ-панель
    if user_id == support_id and support_id:
        buttons.append([
            InlineKeyboardButton(
                text="⚙️ Админ-панель",
                callback_data="admin_panel"
            )
        ])

    # Формируем клавиатуру с разделителями (пустыми строками между группами)
    keyboard = []
    for i, row in enumerate(buttons):
        keyboard.append(row)
        # После каждой группы, кроме последней, добавляем пустую строку (разделитель)
        if i < len(buttons) - 1:
            keyboard.append([])  # пустая строка

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔙 Назад в меню",
                    callback_data="menu"
                )
            ]
        ]
    )


def admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💳 Изменить баланс",
                    callback_data="admin_give_balance"
                )
            ],

            [
                InlineKeyboardButton(
                    text="➕ Выдать рефералов",
                    callback_data="admin_give_refs"
                ),
                InlineKeyboardButton(
                    text="➖ Удалить рефералов",
                    callback_data="admin_delete_refs"
                ),
            ],

            [
                InlineKeyboardButton(
                    text="📢 Рассылка всем",
                    callback_data="admin_broadcast"
                )
            ],

            [
                InlineKeyboardButton(
                    text="➕ Добавить канал",
                    callback_data="admin_add_channel"
                ),
                InlineKeyboardButton(
                    text="🗑️ Удалить канал",
                    callback_data="admin_delete_channel"
                ),
            ],

            [
                InlineKeyboardButton(
                    text="📋 Список каналов",
                    callback_data="admin_list_channels"
                ),
            ],

            [
                InlineKeyboardButton(
                    text="🔙 Назад",
                    callback_data="menu"
                )
            ],
        ]
    )


def withdrawal_keyboard(
    withdrawal_id: int
) -> InlineKeyboardMarkup:

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ ПОДТВЕРДИТЬ",
                    callback_data=f"withdraw_confirm:{withdrawal_id}"
                ),
                InlineKeyboardButton(
                    text="❌ ОТМЕНИТЬ",
                    callback_data=f"withdraw_cancel:{withdrawal_id}"
                ),
            ]
        ]
    )


async def subscription_keyboard() -> InlineKeyboardMarkup:

    chats = await get_required_chats()

    buttons = []

    for chat in chats:
        username = chat["chat_id"].lstrip("@")

        buttons.append([
            InlineKeyboardButton(
                text="📢 " + chat["title"],
                url=f"https://t.me/{username}"
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            text="✨ Проверить подписку",
            callback_data="check_sub"
        )
    ])

    return InlineKeyboardMarkup(
        inline_keyboard=buttons
    )


# =========================================================
# ФУНКЦИЯ ПРОВЕРКИ ПОДПИСКИ ДЛЯ ВСЕХ ДЕЙСТВИЙ
# =========================================================

async def require_subscription(call_or_msg):
    """Универсальная проверка подписки. Возвращает True, если подписан, иначе отправляет сообщение с клавиатурой."""
    user_id = call_or_msg.from_user.id
    # Администратору разрешаем проходить без подписки (чтобы мог управлять)
    if user_id == SUPPORT_ID:
        return True

    if await check_subscription(user_id):
        return True
    else:
        # Если не подписан, отправляем уведомление и клавиатуру для подписки
        if isinstance(call_or_msg, types.CallbackQuery):
            await call_or_msg.answer("🔒 Подпишитесь на каналы!", show_alert=True)
            # Показываем клавиатуру подписки
            await bot.send_message(
                user_id,
                "🔒 <b>Для доступа к боту подпишитесь на наши каналы!</b>\n\n"
                "После подписки нажмите «✨ Проверить подписку».",
                reply_markup=await subscription_keyboard(),
                parse_mode="HTML"
            )
        else:
            await call_or_msg.answer(
                "🔒 <b>Для доступа к боту подпишитесь на наши каналы!</b>\n\n"
                "После подписки нажмите кнопку «✨ Проверить подписку».",
                reply_markup=await subscription_keyboard(),
                parse_mode="HTML"
            )
        return False


# =========================================================
# ГЛАВНОЕ МЕНЮ
# =========================================================

async def show_menu(
    target: types.Message | types.CallbackQuery
):

    user = target.from_user
    user_id = str(user.id)

    await ensure_user(
        user_id,
        user.username or f"User_{user_id[:6]}",
        user.full_name or ""
    )

    # Проверяем подписку (если не админ)
    if user.id != SUPPORT_ID and not await check_subscription(user.id):
        # Если не подписан, показываем клавиатуру подписки и выходим
        if isinstance(target, types.CallbackQuery):
            await target.answer("🔒 Подпишитесь на каналы!", show_alert=True)
        await bot.send_message(
            user.id,
            "🔒 <b>Для доступа к боту подпишитесь на наши каналы!</b>\n\n"
            "После подписки нажмите «✨ Проверить подписку».",
            reply_markup=await subscription_keyboard(),
            parse_mode="HTML"
        )
        return

    # Если подписан – начисляем бонус и показываем меню
    await credit_referral_if_needed(user.id)

    data = await get_user_data(user_id)

    balance = float(
        data.get("balance", 0)
    )

    name = html.escape(
        user.first_name or "Helper"
    )

    # Новый стиль сообщения (как на скриншоте)
    caption = (
        f"✨ <b>Привет, {name}!</b>\n"
        "💎 <b>Добро пожаловать в GiftsMMS Bot</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"⭐ <b>Твой баланс:</b> <code>{balance:.2f} ⭐</code>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💰 Зарабатывай звёзды за приглашение!\n"
        "Выдача товаров моментальна!\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "⬇️ <b>Выбери раздел:</b>"
    )

    if isinstance(target, types.CallbackQuery):
        try:
            await target.message.delete()
        except Exception:
            pass
        chat_id = user.id
    else:
        chat_id = target.chat.id

    try:
        await bot.send_photo(
            chat_id=chat_id,
            photo=MENU_PHOTO,
            caption=caption,
            reply_markup=main_menu_keyboard(user.id),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"Не удалось отправить фото меню: {e}")
        await bot.send_message(
            chat_id=chat_id,
            text=caption,
            reply_markup=main_menu_keyboard(user.id),
            parse_mode="HTML"
        )


# =========================================================
# START & MENU
# =========================================================

@dp.message(CommandStart())
@dp.message(Command("menu"))
async def cmd_start(message: types.Message):

    user_id = str(message.from_user.id)

    await ensure_user(
        user_id,
        message.from_user.username or f"User_{user_id[:6]}",
        message.from_user.full_name or ""
    )

    args = message.text.split()

    if len(args) > 1:

        ref_id = args[1]

        if ref_id.startswith("ref_"):
            ref_id = ref_id[4:]

        if (
            ref_id != user_id
            and ref_id.isdigit()
        ):

            async with db_pool.acquire() as db:

                async with db.transaction():

                    user_row = await db.fetchrow(
                        """
                        SELECT referred_by
                        FROM users
                        WHERE user_id = $1
                        FOR UPDATE
                        """,
                        int(user_id)
                    )

                    ref_exists = await db.fetchrow(
                        """
                        SELECT user_id
                        FROM users
                        WHERE user_id = $1
                        """,
                        int(ref_id)
                    )

                    if (
                        ref_exists
                        and user_row
                        and user_row["referred_by"] is None
                    ):

                        await db.execute(
                            """
                            UPDATE users
                            SET referred_by = $1
                            WHERE user_id = $2
                            AND referred_by IS NULL
                            """,
                            int(ref_id),
                            int(user_id)
                        )

    await show_menu(message)


# =========================================================
# ПРОВЕРКА ПОДПИСКИ (кнопка)
# =========================================================

@dp.callback_query(F.data == "check_sub")
async def cb_check_sub(call: types.CallbackQuery):

    if await check_subscription(
        call.from_user.id
    ):

        await credit_referral_if_needed(
            call.from_user.id
        )

        await call.answer(
            "🎉 Подписка успешно подтверждена!"
        )

        await show_menu(call)

    else:

        await call.answer(
            "❌ Вы подписались не на все каналы!",
            show_alert=True
        )


# =========================================================
# НАЗАД
# =========================================================

@dp.callback_query(F.data == "menu")
async def cb_menu(
    call: types.CallbackQuery,
    state: FSMContext
):

    await state.clear()
    await show_menu(call)


# =========================================================
# РУЛЕТКА
# =========================================================

@dp.callback_query(F.data == "roulette")
async def cb_roulette(call: types.CallbackQuery):

    # Проверка подписки
    if not await require_subscription(call):
        return

    user_id = str(call.from_user.id)

    await ensure_user(
        user_id,
        call.from_user.username or f"User_{user_id[:6]}",
        call.from_user.full_name or ""
    )

    data = await get_user_data(user_id)

    today = date.today()
    last_daily = data.get("last_daily")

    if (
        last_daily == today
        or (
            hasattr(last_daily, "date")
            and last_daily.date() == today
        )
    ):

        await call.answer(
            "⏳ Вы уже испытали удачу сегодня!\n"
            "Возвращайтесь завтра.",
            show_alert=True
        )

        return

    prizes = [
        0.5,
        5,
        6,
        10
    ]

    weights = [
        50,
        30,
        15,
        5
    ]

    win = random.choices(
        prizes,
        weights=weights
    )[0]

    async with db_pool.acquire() as db:

        result = await db.execute(
            """
            UPDATE users
            SET balance = balance + $1,
                last_daily = $2
            WHERE user_id = $3
            AND (
                last_daily IS NULL
                OR last_daily <> $2
            )
            """,
            win,
            today,
            int(user_id)
        )

        if not result.endswith("1"):

            await call.answer(
                "⏳ Вы уже крутили рулетку сегодня!",
                show_alert=True
            )

            return

    new_data = await get_user_data(user_id)

    new_balance = float(
        new_data.get("balance", 0)
    )

    text = (
        "🎰 <b>Ежедневная Рулетка</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🎁 Вы выиграли: <b>+{win:.2f} ⭐</b>\n"
        f"⭐ Ваш баланс: "
        f"<code>{new_balance:.2f} ⭐</code>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "<i>Следующая попытка будет доступна завтра!</i>"
    )

    try:
        await call.message.delete()
    except Exception:
        pass

    await bot.send_message(
        call.from_user.id,
        text,
        reply_markup=back_keyboard(),
        parse_mode="HTML"
    )

    await call.answer()


# =========================================================
# РЕФЕРАЛЫ
# =========================================================

@dp.callback_query(F.data == "referrals")
async def cb_referrals(call: types.CallbackQuery):

    # Проверка подписки
    if not await require_subscription(call):
        return

    user_id = str(call.from_user.id)

    await ensure_user(
        user_id,
        call.from_user.username or f"User_{user_id[:6]}",
        call.from_user.full_name or ""
    )

    me = await bot.get_me()

    ref_link = (
        f"https://t.me/{me.username}"
        f"?start={user_id}"
    )

    data = await get_user_data(user_id)

    refs = data.get("refs", 0)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 Поделиться ссылкой",
                    url=(
                        "https://t.me/share/url"
                        f"?url={ref_link}"
                    )
                )
            ],

            [
                InlineKeyboardButton(
                    text="🔙 Назад в меню",
                    callback_data="menu"
                )
            ],
        ]
    )

    text = (
        "👥 <b>Реферальная программа</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🔗 <b>Ваша ссылка:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        f"⭐ Бонус за друга: "
        f"<b>+{REF_BONUS:.2f} ⭐</b>\n"
        f"📊 Ваши рефералы: "
        f"<code>{refs} чел.</code>\n\n"
        "<i>Бонус начисляется сразу после "
        "подписки друга на все каналы!</i>"
    )

    try:
        await call.message.delete()
    except Exception:
        pass

    await bot.send_message(
        call.from_user.id,
        text,
        reply_markup=kb,
        parse_mode="HTML"
    )

    await call.answer()


# =========================================================
# ВЫВОД
# =========================================================

@dp.callback_query(F.data == "withdraw")
async def cb_withdraw(
    call: types.CallbackQuery,
    state: FSMContext
):

    # Проверка подписки
    if not await require_subscription(call):
        return

    await state.set_state(
        WithdrawStates.waiting_for_amount
    )

    text = (
        "💳 <b>Заявка на вывод ⭐</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 Минимальная сумма: "
        f"<b>{MIN_WITHDRAW} ⭐</b>\n\n"
        "Введите количество звёзд для вывода:"
    )

    try:
        await call.message.delete()
    except Exception:
        pass

    await bot.send_message(
        call.from_user.id,
        text,
        reply_markup=back_keyboard(),
        parse_mode="HTML"
    )

    await call.answer()


@dp.message(WithdrawStates.waiting_for_amount)
async def process_withdraw(
    message: types.Message,
    state: FSMContext
):
    # Проверка подписки (для сообщений тоже)
    if not await require_subscription(message):
        await state.clear()
        return

    user_id = str(message.from_user.id)

    await ensure_user(
        user_id,
        message.from_user.username or f"User_{user_id[:6]}",
        message.from_user.full_name or ""
    )

    try:

        amount = float(
            message.text
            .replace(",", ".")
            .strip()
        )

    except (ValueError, AttributeError):

        await message.answer(
            "❌ Введите корректное число.",
            reply_markup=back_keyboard()
        )

        return

    if amount < MIN_WITHDRAW:

        await message.answer(
            f"❌ Минимальный вывод составляет "
            f"<b>{MIN_WITHDRAW} ⭐</b>",
            reply_markup=back_keyboard(),
            parse_mode="HTML"
        )

        return

    if amount <= 0:

        await message.answer(
            "❌ Сумма должна быть больше нуля.",
            reply_markup=back_keyboard()
        )

        return

    data = await get_user_data(user_id)

    balance = float(
        data.get("balance", 0)
    )

    if balance < amount:

        await message.answer(
            "❌ Недостаточно средств на балансе.\n\n"
            f"Ваш баланс: "
            f"<code>{balance:.2f} ⭐</code>",
            reply_markup=back_keyboard(),
            parse_mode="HTML"
        )

        return

    if not SUPPORT_ID:

        await message.answer(
            "❌ Система выплат временно недоступна.",
            reply_markup=back_keyboard()
        )

        await state.clear()

        return

    username = (
        f"@{message.from_user.username}"
        if message.from_user.username
        else "нет username"
    )

    full_name = message.from_user.full_name

    created_at = datetime.now().strftime(
        "%d.%m.%Y %H:%M"
    )

    async with db_pool.acquire() as db:

        async with db.transaction():

            row = await db.fetchrow(
                """
                SELECT balance
                FROM users
                WHERE user_id = $1
                FOR UPDATE
                """,
                int(user_id)
            )

            if (
                not row
                or float(row["balance"]) < amount
            ):

                await message.answer(
                    "❌ Недостаточно средств.",
                    reply_markup=back_keyboard()
                )

                await state.clear()

                return

            balance_before = float(
                row["balance"]
            )

            withdrawal_id = await db.fetchval(
                """
                INSERT INTO withdrawals
                (
                    user_id,
                    username,
                    full_name,
                    amount,
                    balance_before,
                    status,
                    created_at
                )
                VALUES
                (
                    $1, $2, $3, $4,
                    $5, 'pending', $6
                )
                RETURNING id
                """,
                int(user_id),
                username,
                full_name,
                amount,
                balance_before,
                created_at
            )

            result = await db.execute(
                """
                UPDATE users
                SET balance = balance - $1
                WHERE user_id = $2
                AND balance >= $1
                """,
                amount,
                int(user_id)
            )

            if not result.endswith("1"):
                raise RuntimeError(
                    "Ошибка при списании средств."
                )

    admin_text = (
        "📥 <b>НОВАЯ ЗАЯВКА НА ВЫВОД</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Имя: "
        f"{html.escape(full_name)}\n"
        f"🔗 Username: "
        f"{html.escape(username)}\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"⭐ Сумма: "
        f"<b>{amount:.2f} ⭐</b>\n"
        f"💎 Баланс до: "
        f"<code>{balance_before:.2f} ⭐</code>\n"
        f"📅 Дата: {created_at}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📝 Заявка №"
        f"<code>{withdrawal_id}</code>"
    )

    try:

        admin_message = await bot.send_message(
            chat_id=SUPPORT_ID,
            text=admin_text,
            reply_markup=withdrawal_keyboard(
                withdrawal_id
            ),
            parse_mode="HTML"
        )

        async with db_pool.acquire() as db:

            await db.execute(
                """
                UPDATE withdrawals
                SET admin_message_id = $1
                WHERE id = $2
                """,
                admin_message.message_id,
                withdrawal_id
            )

    except Exception as e:

        logger.error(
            f"Ошибка отправки заявки админу: {e}"
        )

        async with db_pool.acquire() as db:

            async with db.transaction():

                row = await db.fetchrow(
                    """
                    SELECT amount, user_id
                    FROM withdrawals
                    WHERE id = $1
                    AND status = 'pending'
                    FOR UPDATE
                    """,
                    withdrawal_id
                )

                if row:

                    await db.execute(
                        """
                        UPDATE users
                        SET balance = balance + $1
                        WHERE user_id = $2
                        """,
                        float(row["amount"]),
                        row["user_id"]
                    )

                    await db.execute(
                        """
                        UPDATE withdrawals
                        SET status = 'cancelled'
                        WHERE id = $1
                        """,
                        withdrawal_id
                    )

        await message.answer(
            "❌ Ошибка отправки заявки. "
            "Средства возвращены.",
            reply_markup=back_keyboard()
        )

        await state.clear()

        return

    await message.answer(
        f"✅ <b>Заявка №{withdrawal_id} создана!</b>\n\n"
        f"⭐ Сумма: "
        f"<code>{amount:.2f} ⭐</code>\n"
        "⏳ Ожидайте обработки администратором.",
        reply_markup=back_keyboard(),
        parse_mode="HTML"
    )

    await state.clear()


# =========================================================
# ПОДТВЕРЖДЕНИЕ ВЫВОДА
# =========================================================

@dp.callback_query(
    F.data.startswith("withdraw_confirm:")
)
async def confirm_withdraw(
    call: types.CallbackQuery
):

    if call.from_user.id != SUPPORT_ID:

        await call.answer(
            "❌ Нет доступа!",
            show_alert=True
        )

        return

    try:

        withdrawal_id = int(
            call.data.split(":")[1]
        )

    except (ValueError, IndexError):

        await call.answer(
            "❌ Некорректная заявка.",
            show_alert=True
        )

        return

    async with db_pool.acquire() as db:

        async with db.transaction():

            withdrawal = await db.fetchrow(
                """
                SELECT *
                FROM withdrawals
                WHERE id = $1
                FOR UPDATE
                """,
                withdrawal_id
            )

            if not withdrawal:

                await call.answer(
                    "❌ Заявка не найдена.",
                    show_alert=True
                )

                return

            if withdrawal["status"] != "pending":

                await call.answer(
                    "⚠️ Заявка уже обработана.",
                    show_alert=True
                )

                return

            await db.execute(
                """
                UPDATE withdrawals
                SET status = 'approved'
                WHERE id = $1
                AND status = 'pending'
                """,
                withdrawal_id
            )

    try:

        await bot.send_message(
            int(withdrawal["user_id"]),
            f"🎉 <b>Вывод подтверждён!</b>\n\n"
            f"⭐ Отправлено: "
            f"<code>{float(withdrawal['amount']):.2f} ⭐</code>\n"
            f"📝 Заявка №"
            f"<code>{withdrawal_id}</code>\n\n"
            "💎 Средства переведены администратором.",
            parse_mode="HTML"
        )

    except Exception as e:

        logger.warning(
            f"Не удалось уведомить пользователя: {e}"
        )

    new_text = (
        "✅ <b>ВЫВОД ПОДТВЕРЖДЁН</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Имя: "
        f"{html.escape(withdrawal['full_name'])}\n"
        f"🔗 Username: "
        f"{html.escape(withdrawal['username'])}\n"
        f"🆔 ID: "
        f"<code>{withdrawal['user_id']}</code>\n"
        f"⭐ Сумма: "
        f"<b>{float(withdrawal['amount']):.2f} ⭐</b>\n"
        f"📅 Дата: "
        f"{withdrawal['created_at']}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📝 Заявка №"
        f"<code>{withdrawal_id}</code>"
    )

    try:

        await call.message.edit_text(
            new_text,
            parse_mode="HTML"
        )

    except Exception as e:

        logger.warning(
            f"Не удалось изменить сообщение заявки: {e}"
        )

    await call.answer(
        "✅ Успешно подтверждено!"
    )


# =========================================================
# ОТМЕНА ВЫВОДА
# =========================================================

@dp.callback_query(
    F.data.startswith("withdraw_cancel:")
)
async def cancel_withdraw(
    call: types.CallbackQuery
):

    if call.from_user.id != SUPPORT_ID:

        await call.answer(
            "❌ Нет доступа!",
            show_alert=True
        )

        return

    try:

        withdrawal_id = int(
            call.data.split(":")[1]
        )

    except (ValueError, IndexError):

        await call.answer(
            "❌ Некорректная заявка.",
            show_alert=True
        )

        return

    async with db_pool.acquire() as db:

        async with db.transaction():

            withdrawal = await db.fetchrow(
                """
                SELECT *
                FROM withdrawals
                WHERE id = $1
                FOR UPDATE
                """,
                withdrawal_id
            )

            if not withdrawal:

                await call.answer(
                    "❌ Заявка не найдена.",
                    show_alert=True
                )

                return

            if withdrawal["status"] != "pending":

                await call.answer(
                    "⚠️ Заявка уже обработана.",
                    show_alert=True
                )

                return

            await db.execute(
                """
                UPDATE withdrawals
                SET status = 'cancelled'
                WHERE id = $1
                AND status = 'pending'
                """,
                withdrawal_id
            )

            await db.execute(
                """
                UPDATE users
                SET balance = balance + $1
                WHERE user_id = $2
                """,
                float(withdrawal["amount"]),
                withdrawal["user_id"]
            )

    try:

        await bot.send_message(
            int(withdrawal["user_id"]),
            f"❌ <b>Вывод отменён</b>\n\n"
            f"⭐ Возвращено на баланс: "
            f"<code>{float(withdrawal['amount']):.2f} ⭐</code>\n"
            f"📝 Заявка №"
            f"<code>{withdrawal_id}</code>",
            parse_mode="HTML"
        )

    except Exception as e:

        logger.warning(
            f"Не удалось уведомить пользователя: {e}"
        )

    new_text = (
        "❌ <b>ВЫВОД ОТМЕНЁН</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Имя: "
        f"{html.escape(withdrawal['full_name'])}\n"
        f"🔗 Username: "
        f"{html.escape(withdrawal['username'])}\n"
        f"🆔 ID: "
        f"<code>{withdrawal['user_id']}</code>\n"
        f"⭐ Сумма: "
        f"<b>{float(withdrawal['amount']):.2f} ⭐</b>\n"
        f"📅 Дата: "
        f"{withdrawal['created_at']}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🔄 Средства возвращены на баланс"
    )

    try:

        await call.message.edit_text(
            new_text,
            parse_mode="HTML"
        )

    except Exception as e:

        logger.warning(
            f"Не удалось изменить сообщение заявки: {e}"
        )

    await call.answer(
        "❌ Отменено, средства возвращены."
    )


# =========================================================
# ЛИДЕРЫ ПО РЕФЕРАЛАМ (кнопка в меню) — с именами и юзернеймами
# =========================================================

@dp.callback_query(F.data == "leaders")
async def cb_leaders(call: types.CallbackQuery):
    # Проверка подписки
    if not await require_subscription(call):
        return

    async with db_pool.acquire() as db:
        rows = await db.fetch("""
            SELECT user_id, username, full_name, refs
            FROM leaders
            WHERE refs > 0
            ORDER BY refs DESC, user_id ASC
            LIMIT 10
        """)
    if not rows:
        text = (
            "👑 <b>ЛИДЕРЫ ПО РЕФЕРАЛАМ</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "📭 <i>Пока лидеров нет. Приглашайте друзей!</i>"
        )
        kb = back_keyboard()
    else:
        medals = ["🥇", "🥈", "🥉"] + [f"{i+1}." for i in range(3, len(rows))]
        lines = ["👑 <b>ЛИДЕРЫ ПО РЕФЕРАЛАМ</b>", "━━━━━━━━━━━━━━━━━━━━"]
        buttons = []
        for i, row in enumerate(rows):
            uid = str(row["user_id"])
            # Формируем отображение: полное имя + @username, если есть
            if row["full_name"]:
                display_name = html.escape(row["full_name"])
                if row["username"]:
                    display_name += f" (@{html.escape(row['username'])})"
            elif row["username"]:
                display_name = "@" + html.escape(row["username"])
            else:
                display_name = f"User{uid[:6]}"
            refs = row["refs"]
            medal = medals[i] if i < len(medals) else f"{i+1}."
            lines.append(f"{medal} <b>{display_name}</b> — <code>{refs}</code> реф.")
            buttons.append([
                InlineKeyboardButton(
                    text=f"{medal} {display_name}",
                    url=f"tg://user?id={uid}"
                )
            ])
        buttons.append([
            InlineKeyboardButton(
                text="🔙 Назад в меню",
                callback_data="menu"
            )
        ])
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        text = "\n".join(lines)

    try:
        await call.message.delete()
    except Exception:
        pass
    await bot.send_message(
        call.from_user.id,
        text,
        reply_markup=kb,
        parse_mode="HTML"
    )
    await call.answer()


# =========================================================
# КОМАНДА /top (дублирует кнопку, но работает без кнопок) — тоже с именами
# =========================================================

@dp.message(Command("top"))
async def cmd_top(message: types.Message):
    # Проверка подписки (для админа пропускаем)
    if message.from_user.id != SUPPORT_ID and not await check_subscription(message.from_user.id):
        await message.answer(
            "🔒 <b>Для доступа к боту подпишитесь на наши каналы!</b>",
            reply_markup=await subscription_keyboard(),
            parse_mode="HTML"
        )
        return

    async with db_pool.acquire() as db:
        rows = await db.fetch("""
            SELECT user_id, username, full_name, refs
            FROM leaders
            WHERE refs > 0
            ORDER BY refs DESC, user_id ASC
            LIMIT 10
        """)
    if not rows:
        text = (
            "👑 <b>ЛИДЕРЫ ПО РЕФЕРАЛАМ</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "📭 <i>Пока лидеров нет. Приглашайте друзей!</i>"
        )
    else:
        medals = ["🥇", "🥈", "🥉"] + [f"{i+1}." for i in range(3, len(rows))]
        lines = ["👑 <b>ЛИДЕРЫ ПО РЕФЕРАЛАМ</b>", "━━━━━━━━━━━━━━━━━━━━"]
        for i, row in enumerate(rows):
            uid = str(row["user_id"])
            if row["full_name"]:
                display_name = html.escape(row["full_name"])
                if row["username"]:
                    display_name += f" (@{html.escape(row['username'])})"
            elif row["username"]:
                display_name = "@" + html.escape(row["username"])
            else:
                display_name = f"User{uid[:6]}"
            refs = row["refs"]
            medal = medals[i] if i < len(medals) else f"{i+1}."
            lines.append(f"{medal} <b>{display_name}</b> — <code>{refs}</code> реф.")
        text = "\n".join(lines)
    await message.answer(text, parse_mode="HTML")


# =========================================================
# АДМИН-КОМАНДА /refresh_leaders (пересчёт таблицы)
# =========================================================

@dp.message(Command("refresh_leaders"))
async def refresh_leaders(message: types.Message):
    if message.from_user.id != SUPPORT_ID:
        return
    await message.answer("🔄 Пересчёт таблицы лидеров...")
    async with db_pool.acquire() as db:
        await db.execute("TRUNCATE TABLE leaders")
        await db.execute("""
            INSERT INTO leaders (user_id, username, full_name, refs, updated_at)
            SELECT user_id, username, full_name, refs, NOW()
            FROM users
            WHERE refs > 0
        """)
    await message.answer("✅ Таблица лидеров пересчитана!")


# =========================================================
# АДМИН-ПАНЕЛЬ
# =========================================================

@dp.callback_query(F.data == "admin_panel")
@dp.message(Command("admin"))
async def show_admin_panel(
    event: types.Message | types.CallbackQuery
):

    if event.from_user.id != SUPPORT_ID:

        if isinstance(
            event,
            types.CallbackQuery
        ):

            await event.answer(
                "❌ Нет доступа!",
                show_alert=True
            )

        return

    # Для админа проверка подписки не требуется

    async with db_pool.acquire() as db:

        row = await db.fetchrow(
            """
            SELECT
                COUNT(*) AS total_users,
                COALESCE(SUM(balance), 0)
                AS total_balance
            FROM users
            """
        )

    total_users = row["total_users"]

    total_balance = float(
        row["total_balance"]
    )

    text = (
        "⚙️ <b>ПАНЕЛЬ АДМИНИСТРАТОРА</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Всего пользователей: "
        f"<code>{total_users}</code>\n"
        f"💰 Сумма всех балансов: "
        f"<code>{total_balance:.2f} ⭐</code>\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )

    if isinstance(
        event,
        types.CallbackQuery
    ):

        try:
            await event.message.delete()
        except Exception:
            pass

        await bot.send_message(
            event.from_user.id,
            text,
            reply_markup=admin_keyboard(),
            parse_mode="HTML"
        )

        await event.answer()

    else:

        await event.answer(
            text,
            reply_markup=admin_keyboard(),
            parse_mode="HTML"
        )


# =========================================================
# ИЗМЕНЕНИЕ БАЛАНСА
# =========================================================

@dp.callback_query(
    F.data == "admin_give_balance"
)
async def cb_admin_give(
    call: types.CallbackQuery,
    state: FSMContext
):

    if call.from_user.id != SUPPORT_ID:
        return

    await state.set_state(
        AdminStates.waiting_for_give_data
    )

    text = (
        "💳 <b>Изменение баланса</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Введите данными одной строкой:\n"
        "<code>ID Сумма</code>\n\n"
        "Пример пополнения:\n"
        "<code>123456789 15</code>\n\n"
        "Пример списания:\n"
        "<code>123456789 -10</code>"
    )

    try:
        await call.message.delete()
    except Exception:
        pass

    await bot.send_message(
        call.from_user.id,
        text,
        reply_markup=back_keyboard(),
        parse_mode="HTML"
    )

    await call.answer()


@dp.message(
    AdminStates.waiting_for_give_data
)
async def process_admin_give(
    message: types.Message,
    state: FSMContext
):

    if message.from_user.id != SUPPORT_ID:
        return

    parts = message.text.strip().split()

    if len(parts) != 2:

        await message.answer(
            "❌ Неверный формат. Используйте:\n"
            "<code>ID Сумма</code>",
            reply_markup=back_keyboard(),
            parse_mode="HTML"
        )

        return

    target_id = parts[0]

    try:

        amount = float(
            parts[1].replace(",", ".")
        )

    except ValueError:

        await message.answer(
            "❌ Сумма должна быть числом.",
            reply_markup=back_keyboard()
        )

        return

    user_data = await get_user_data(
        target_id
    )

    if not user_data:

        await message.answer(
            "❌ Пользователь не найден.",
            reply_markup=back_keyboard()
        )

        return

    async with db_pool.acquire() as db:

        await db.execute(
            """
            UPDATE users
            SET balance = balance + $1
            WHERE user_id = $2
            """,
            amount,
            int(target_id)
        )

    updated = await get_user_data(
        target_id
    )

    new_balance = float(
        updated.get("balance", 0)
    )

    try:

        action = (
            f"+{amount:.2f}"
            if amount >= 0
            else f"{amount:.2f}"
        )

        await bot.send_message(
            int(target_id),
            f"🔔 <b>Ваш баланс изменён</b>\n\n"
            f"Изменение: "
            f"<b>{action} ⭐</b>\n"
            f"Новый баланс: "
            f"<code>{new_balance:.2f} ⭐</code>",
            parse_mode="HTML"
        )

    except Exception:
        pass

    await message.answer(
        f"✅ <b>Успешно!</b>\n\n"
        f"Пользователь: "
        f"<code>{target_id}</code>\n"
        f"Баланс: "
        f"<code>{new_balance:.2f} ⭐</code>",
        reply_markup=admin_keyboard(),
        parse_mode="HTML"
    )

    await state.clear()


# =========================================================
# ВЫДАТЬ РЕФЕРАЛОВ
# =========================================================

@dp.callback_query(
    F.data == "admin_give_refs"
)
async def cb_admin_give_refs(
    call: types.CallbackQuery,
    state: FSMContext
):

    if call.from_user.id != SUPPORT_ID:
        return

    await state.set_state(
        AdminStates.waiting_for_give_refs
    )

    text = (
        "➕ <b>Начислить рефералов</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Введите данные строкой:\n"
        "<code>ID Количество</code>\n\n"
        "Пример:\n"
        "<code>6662093609 10</code>"
    )

    try:
        await call.message.delete()
    except Exception:
        pass

    await bot.send_message(
        call.from_user.id,
        text,
        reply_markup=back_keyboard(),
        parse_mode="HTML"
    )

    await call.answer()


@dp.message(
    AdminStates.waiting_for_give_refs
)
async def process_admin_give_refs(
    message: types.Message,
    state: FSMContext
):

    if message.from_user.id != SUPPORT_ID:
        return

    parts = message.text.strip().split()

    if len(parts) != 2:

        await message.answer(
            "❌ Неверный формат:\n"
            "<code>ID Количество</code>",
            reply_markup=back_keyboard(),
            parse_mode="HTML"
        )

        return

    target_id = parts[0]

    try:

        amount = int(parts[1])

    except ValueError:

        await message.answer(
            "❌ Количество должно быть целым числом.",
            reply_markup=back_keyboard()
        )

        return

    if amount <= 0:

        await message.answer(
            "❌ Количество должно быть больше нуля.",
            reply_markup=back_keyboard()
        )

        return

    user_data = await get_user_data(
        target_id
    )

    if not user_data:

        await message.answer(
            "❌ Пользователь не найден.",
            reply_markup=back_keyboard()
        )

        return

    async with db_pool.acquire() as db:

        await db.execute(
            """
            UPDATE users
            SET refs = refs + $1
            WHERE user_id = $2
            """,
            amount,
            int(target_id)
        )

    updated = await get_user_data(
        target_id
    )

    new_refs = updated.get(
        "refs",
        0
    )

    # Обновить таблицу лидеров для этого пользователя
    await update_leader(int(target_id))

    await message.answer(
        f"✅ <b>Рефералы добавлены!</b>\n\n"
        f"🆔 ID: <code>{target_id}</code>\n"
        f"➕ Добавлено: <b>{amount}</b>\n"
        f"👥 Всего: <code>{new_refs}</code>",
        reply_markup=admin_keyboard(),
        parse_mode="HTML"
    )

    await state.clear()


# =========================================================
# УДАЛИТЬ РЕФЕРАЛОВ
# =========================================================

@dp.callback_query(
    F.data == "admin_delete_refs"
)
async def cb_admin_delete_refs(
    call: types.CallbackQuery,
    state: FSMContext
):

    if call.from_user.id != SUPPORT_ID:
        return

    await state.set_state(
        AdminStates.waiting_for_delete_refs
    )

    text = (
        "➖ <b>Списать рефералов</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Введите данные строкой:\n"
        "<code>ID Количество</code>\n\n"
        "Пример:\n"
        "<code>6662093609 5</code>"
    )

    try:
        await call.message.delete()
    except Exception:
        pass

    await bot.send_message(
        call.from_user.id,
        text,
        reply_markup=back_keyboard(),
        parse_mode="HTML"
    )

    await call.answer()


@dp.message(
    AdminStates.waiting_for_delete_refs
)
async def process_admin_delete_refs(
    message: types.Message,
    state: FSMContext
):

    if message.from_user.id != SUPPORT_ID:
        return

    parts = message.text.strip().split()

    if len(parts) != 2:

        await message.answer(
            "❌ Неверный формат:\n"
            "<code>ID Количество</code>",
            reply_markup=back_keyboard(),
            parse_mode="HTML"
        )

        return

    target_id = parts[0]

    try:

        amount = int(parts[1])

    except ValueError:

        await message.answer(
            "❌ Количество должно быть целым числом.",
            reply_markup=back_keyboard()
        )

        return

    if amount <= 0:

        await message.answer(
            "❌ Количество должно быть больше нуля.",
            reply_markup=back_keyboard()
        )

        return

    user_data = await get_user_data(
        target_id
    )

    if not user_data:

        await message.answer(
            "❌ Пользователь не найден.",
            reply_markup=back_keyboard()
        )

        return

    current_refs = int(
        user_data.get("refs", 0)
    )

    new_refs = max(
        0,
        current_refs - amount
    )

    async with db_pool.acquire() as db:

        await db.execute(
            """
            UPDATE users
            SET refs = $1
            WHERE user_id = $2
            """,
            new_refs,
            int(target_id)
        )

    # Обновить таблицу лидеров для этого пользователя
    await update_leader(int(target_id))

    await message.answer(
        f"✅ <b>Рефералы списаны!</b>\n\n"
        f"🆔 ID: <code>{target_id}</code>\n"
        f"➖ Удалено: <b>{amount}</b>\n"
        f"👥 Осталось: <code>{new_refs}</code>",
        reply_markup=admin_keyboard(),
        parse_mode="HTML"
    )

    await state.clear()


# =========================================================
# ДОБАВИТЬ КАНАЛ
# =========================================================

@dp.callback_query(
    F.data == "admin_add_channel"
)
async def cb_admin_add_channel(
    call: types.CallbackQuery,
    state: FSMContext
):

    if call.from_user.id != SUPPORT_ID:
        return

    await state.set_state(
        AdminStates.waiting_for_new_channel
    )

    text = (
        "➕ <b>Добавление канала/чата</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Отправьте юзернейм канала:\n"
        "<code>@channelname</code>\n\n"
        "⚠️ Бот должен быть администратором "
        "в подключаемом канале!"
    )

    try:
        await call.message.delete()
    except Exception:
        pass

    await bot.send_message(
        call.from_user.id,
        text,
        reply_markup=back_keyboard(),
        parse_mode="HTML"
    )

    await call.answer()


@dp.message(
    AdminStates.waiting_for_new_channel
)
async def process_add_channel(
    message: types.Message,
    state: FSMContext
):

    if message.from_user.id != SUPPORT_ID:
        return

    chat_id = message.text.strip()

    if not chat_id.startswith("@"):
        chat_id = "@" + chat_id

    try:

        chat = await bot.get_chat(chat_id)

        title = chat.title or chat_id

    except Exception as e:

        await message.answer(
            f"❌ Ошибка подключения канала: {e}\n\n"
            "Убедитесь, что бот назначен админом.",
            reply_markup=back_keyboard()
        )

        return

    async with db_pool.acquire() as db:

        await db.execute(
            """
            INSERT INTO required_chats
            (chat_id, title)
            VALUES ($1, $2)
            ON CONFLICT (chat_id)
            DO UPDATE SET title = EXCLUDED.title
            """,
            chat_id,
            title
        )

    await message.answer(
        "✅ Канал добавлен в обязательную подписку!\n\n"
        f"📢 <b>{html.escape(title)}</b> "
        f"(<code>{chat_id}</code>)",
        reply_markup=admin_keyboard(),
        parse_mode="HTML"
    )

    await state.clear()


# =========================================================
# УДАЛИТЬ КАНАЛ
# =========================================================

@dp.callback_query(F.data == "admin_delete_channel")
async def cb_admin_delete_channel(call: types.CallbackQuery):
    if call.from_user.id != SUPPORT_ID:
        return

    chats = await get_required_chats()
    if not chats:
        await call.answer("Список каналов пуст.", show_alert=True)
        return

    buttons = []
    for chat in chats:
        buttons.append([
            InlineKeyboardButton(
                text=f"❌ {chat['title']} ({chat['chat_id']})",
                callback_data=f"delete_channel:{chat['id']}"
            )
        ])
    buttons.append([
        InlineKeyboardButton(
            text="🔙 Назад",
            callback_data="admin_panel"
        )
    ])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await bot.send_message(
        call.from_user.id,
        "🗑️ <b>Выберите канал для удаления:</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await call.answer()


@dp.callback_query(F.data.startswith("delete_channel:"))
async def process_delete_channel(call: types.CallbackQuery):
    if call.from_user.id != SUPPORT_ID:
        return

    channel_id = int(call.data.split(":")[1])
    async with db_pool.acquire() as db:
        await db.execute("DELETE FROM required_chats WHERE id = $1", channel_id)

    await call.answer("✅ Канал удалён из обязательной подписки!", show_alert=True)
    await call.message.delete()
    # Показываем обновлённый список
    await cb_admin_delete_channel(call)


# =========================================================
# СПИСОК КАНАЛОВ
# =========================================================

@dp.callback_query(
    F.data == "admin_list_channels"
)
async def cb_admin_list_channels(
    call: types.CallbackQuery
):

    if call.from_user.id != SUPPORT_ID:
        return

    chats = await get_required_chats()

    if not chats:

        text = (
            "📋 Список обязательных каналов пуст."
        )

    else:

        lines = [
            "📋 <b>Обязательные каналы "
            "для подписки:</b>\n"
        ]

        for i, chat in enumerate(
            chats,
            1
        ):

            lines.append(
                f"{i}. "
                f"<b>{html.escape(chat['title'])}</b> — "
                f"<code>{chat['chat_id']}</code>"
            )

        text = "\n".join(lines)

    try:
        await call.message.delete()
    except Exception:
        pass

    await bot.send_message(
        call.from_user.id,
        text,
        reply_markup=admin_keyboard(),
        parse_mode="HTML"
    )

    await call.answer()


# =========================================================
# РАССЫЛКА
# =========================================================

@dp.callback_query(
    F.data == "admin_broadcast"
)
async def cb_admin_broadcast(
    call: types.CallbackQuery,
    state: FSMContext
):

    if call.from_user.id != SUPPORT_ID:
        return

    await state.set_state(
        AdminStates.waiting_for_broadcast_msg
    )

    text = (
        "📢 <b>Массовая рассылка</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Отправьте текст сообщения "
        "для рассылки всем пользователям."
    )

    try:
        await call.message.delete()
    except Exception:
        pass

    await bot.send_message(
        call.from_user.id,
        text,
        reply_markup=back_keyboard(),
        parse_mode="HTML"
    )

    await call.answer()


@dp.message(
    AdminStates.waiting_for_broadcast_msg
)
async def process_admin_broadcast(
    message: types.Message,
    state: FSMContext
):

    if message.from_user.id != SUPPORT_ID:
        return

    broadcast_text = message.text

    if not broadcast_text:

        await message.answer(
            "❌ Сообщение не может быть пустым.",
            reply_markup=back_keyboard()
        )

        return

    async with db_pool.acquire() as db:

        users = await db.fetch(
            "SELECT user_id FROM users"
        )

    total = len(users)

    await message.answer(
        "🚀 <b>Запуск рассылки...</b>\n\n"
        f"Получателей: <code>{total}</code>",
        parse_mode="HTML"
    )

    success = 0
    failed = 0

    for row in users:

        uid = row["user_id"]

        try:

            await bot.send_message(
                int(uid),
                broadcast_text
            )

            success += 1

            await asyncio.sleep(0.05)

        except Exception as e:

            failed += 1

            logger.warning(
                f"Не удалось отправить {uid}: {e}"
            )

    await message.answer(
        "✅ <b>РАССЫЛКА ЗАВЕРШЕНА!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Всего: <code>{total}</code>\n"
        f"✅ Доставлено: <code>{success}</code>\n"
        f"❌ Ошибок: <code>{failed}</code>",
        reply_markup=admin_keyboard(),
        parse_mode="HTML"
    )

    await state.clear()


# =========================================================
# ЗАПУСК
# =========================================================

async def main():

    logger.info(
        "Запуск GiftsMMS..."
    )

    await init_db()

    web_runner = await start_web_server()

    me = await bot.get_me()

    logger.info(
        f"Бот @{me.username} успешно запущен"
    )

    try:

        await bot.set_my_description(
            "💎 GiftsMMS Bot — "
            "рулетка, рефералы и вывод ⭐"
        )

    except Exception as e:

        logger.warning(
            f"Не удалось установить описание: {e}"
        )

    try:

        await dp.start_polling(bot)

    finally:

        await close_db()

        await web_runner.cleanup()

        await bot.session.close()


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":

    try:

        asyncio.run(main())

    except (KeyboardInterrupt, SystemExit):

        logger.info(
            "Бот остановлен"
        )

    except Exception as e:

        logger.error(
            f"Критическая ошибка: {e}"
        )

        raise
