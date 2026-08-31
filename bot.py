import asyncio
import html
import logging
import os
import random
from datetime import date, datetime

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

CHANNEL_ID = "@eclipsedlf"
SUPPORT_USERNAME = "@Eclipsed_consult"

MIN_WITHDRAW = 15
REF_BONUS = 0.85


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
    waiting_for_broadcast_msg = State()


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
                balance NUMERIC(12, 2) NOT NULL DEFAULT 0,
                refs INTEGER NOT NULL DEFAULT 0,
                referred_by BIGINT DEFAULT NULL,
                last_daily DATE DEFAULT NULL
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

    logger.info("PostgreSQL успешно подключён!")


async def close_db():

    global db_pool

    if db_pool:
        await db_pool.close()
        logger.info("Соединение с PostgreSQL закрыто.")


async def ensure_user(user_id: str, username: str = ""):

    async with db_pool.acquire() as db:

        await db.execute(
            """
            INSERT INTO users (user_id, username)
            VALUES ($1, $2)
            ON CONFLICT (user_id)
            DO UPDATE SET username = EXCLUDED.username
            WHERE EXCLUDED.username IS NOT NULL
              AND EXCLUDED.username <> ''
            """,
            int(user_id),
            username
        )


async def get_user_data(user_id: str):

    async with db_pool.acquire() as db:

        row = await db.fetchrow(
            """
            SELECT *
            FROM users
            WHERE user_id = $1
            """,
            int(user_id)
        )

        if not row:
            return {}

        return dict(row)


# =========================================================
# WEB-SERVER ДЛЯ RENDER
# =========================================================

async def health_check(request):

    return web.Response(
        text="GiftsEzz Bot is running!"
    )


async def start_web_server():

    app = web.Application()

    app.router.add_get(
        "/",
        health_check
    )

    app.router.add_get(
        "/health",
        health_check
    )

    runner = web.AppRunner(app)

    await runner.setup()

    port = int(
        os.getenv("PORT", "10000")
    )

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

def main_menu_keyboard(user_id: int):

    buttons = [
        [
            InlineKeyboardButton(
                text="📢 Канал",
                url="https://t.me/eclipsedlf"
            ),
            InlineKeyboardButton(
                text="🛟 Поддержка",
                url="https://t.me/Eclipsed_consult"
            )
        ],
        [
            InlineKeyboardButton(
                text="👥 Рефералы",
                callback_data="referrals"
            ),
            InlineKeyboardButton(
                text="💸 Вывод",
                callback_data="withdraw"
            )
        ],
        [
            InlineKeyboardButton(
                text="🎰 Рулетка",
                callback_data="roulette"
            ),
            InlineKeyboardButton(
                text="🏆 ТОП лидеров",
                callback_data="leaders"
            )
        ]
    ]

    if user_id == SUPPORT_ID and SUPPORT_ID != 0:

        buttons.append([
            InlineKeyboardButton(
                text="⚙️ Админ-панель",
                callback_data="admin_panel"
            )
        ])

    return InlineKeyboardMarkup(
        inline_keyboard=buttons
    )


def back_keyboard():

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="◀️ Назад",
                    callback_data="menu"
                )
            ]
        ]
    )


def admin_keyboard():

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💰 Изменить баланс",
                    callback_data="admin_give_balance"
                )
            ],
            [
                InlineKeyboardButton(
                    text="👥 Выдать рефералов",
                    callback_data="admin_give_refs"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📢 Рассылка всем",
                    callback_data="admin_broadcast"
                )
            ],
            [
                InlineKeyboardButton(
                    text="◀️ Назад",
                    callback_data="menu"
                )
            ]
        ]
    )


# =========================================================
# КНОПКИ ЗАЯВКИ НА ВЫВОД
# =========================================================

def withdrawal_keyboard(withdrawal_id: int):

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
                )
            ]
        ]
    )


def subscription_keyboard():

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📢 Канал",
                    url="https://t.me/eclipsedlf"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🛟 Поддержка",
                    url="https://t.me/Eclipsed_consult"
                )
            ],
            [
                InlineKeyboardButton(
                    text="✅ Проверить подписку",
                    callback_data="check_sub"
                )
            ]
        ]
    )


# =========================================================
# ПРОВЕРКА ПОДПИСКИ
# =========================================================

async def check_subscription(user_id: int) -> bool:

    try:

        member = await bot.get_chat_member(
            chat_id=CHANNEL_ID,
            user_id=user_id
        )

        if member.status in ["left", "kicked"]:
            return False

        return True

    except Exception as e:

        logger.warning(
            f"Ошибка проверки подписки: {e}"
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
        user.username or f"User_{user_id[:6]}"
    )

    data = await get_user_data(user_id)

    balance = float(
        data.get("balance", 0)
    )

    name = html.escape(
        user.full_name
    )

    text = (
        f"🧊 <b>Привет, {name}!</b>\n\n"
        f"💎 <b>Твой баланс:</b> "
        f"<code>{balance:.2f} ⭐</code>\n\n"
        "🔹 ──────────────── 🔹\n"
        "🔹 <b>Выбирай раздел:</b>"
    )

    if isinstance(
        target,
        types.CallbackQuery
    ):

        try:
            await target.message.delete()
        except Exception:
            pass

        await bot.send_message(
            chat_id=user.id,
            text=text,
            reply_markup=main_menu_keyboard(
                user.id
            ),
            parse_mode="HTML"
        )

    else:

        await target.answer(
            text,
            reply_markup=main_menu_keyboard(
                user.id
            ),
            parse_mode="HTML"
        )


# =========================================================
# START
# =========================================================

@dp.message(CommandStart())
async def cmd_start(message: types.Message):

    user_id = str(
        message.from_user.id
    )

    await ensure_user(
        user_id,
        message.from_user.username
        or f"User_{user_id[:6]}"
    )

    args = message.text.split()

    # =====================================================
    # РЕФЕРАЛ
    # =====================================================

    if len(args) > 1:

        ref_id = args[1]

        if ref_id.startswith("ref_"):
            ref_id = ref_id[4:]

        if ref_id != user_id:

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

                        await db.execute(
                            """
                            UPDATE users
                            SET refs = refs + 1,
                                balance = balance + $1
                            WHERE user_id = $2
                            """,
                            REF_BONUS,
                            int(ref_id)
                        )

                        try:

                            await bot.send_message(
                                int(ref_id),
                                (
                                    "🎉 <b>Новый реферал!</b>\n\n"
                                    f"💎 Вам начислено "
                                    f"<b>+{REF_BONUS:.2f} ⭐</b>"
                                ),
                                parse_mode="HTML"
                            )

                        except Exception:
                            pass

    # =====================================================
    # ПОДПИСКА
    # =====================================================

    if not await check_subscription(
        message.from_user.id
    ):

        await message.answer(
            "⚠️ <b>Для использования бота "
            "подпишитесь на наш канал!</b>\n\n"
            "После подписки нажмите "
            "«Проверить подписку».",
            reply_markup=subscription_keyboard(),
            parse_mode="HTML"
        )

        return

    await show_menu(message)


# =========================================================
# ПРОВЕРКА ПОДПИСКИ
# =========================================================

@dp.callback_query(F.data == "check_sub")
async def cb_check_sub(
    call: types.CallbackQuery
):

    if await check_subscription(
        call.from_user.id
    ):

        await call.answer(
            "✅ Подписка подтверждена!"
        )

        await show_menu(call)

    else:

        await call.answer(
            "❌ Вы ещё не подписались!",
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
async def cb_roulette(
    call: types.CallbackQuery
):

    user_id = str(
        call.from_user.id
    )

    await ensure_user(
        user_id,
        call.from_user.username
        or f"User_{user_id[:6]}"
    )

    data = await get_user_data(
        user_id
    )

    today = date.today()

    if data.get("last_daily") == today:

        await call.answer(
            "⏳ Ты уже крутил сегодня!\n"
            "Возвращайся завтра.",
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
                "⏳ Ты уже крутил сегодня!",
                show_alert=True
            )

            return

    new_data = await get_user_data(
        user_id
    )

    new_balance = float(
        new_data.get("balance", 0)
    )

    text = (
        "🎰 <b>Результат рулетки</b>\n"
        "━━━━━━━━━━━━━━━━━\n"
        f"🎁 Вы выиграли: "
        f"<code>{win:.2f} ⭐</code>\n"
        f"💎 Баланс: "
        f"<code>{new_balance:.2f} ⭐</code>\n"
        "━━━━━━━━━━━━━━━━━\n"
        "<i>Приходи завтра снова!</i>"
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
async def cb_referrals(
    call: types.CallbackQuery
):

    user_id = str(
        call.from_user.id
    )

    await ensure_user(
        user_id,
        call.from_user.username
        or f"User_{user_id[:6]}"
    )

    me = await bot.get_me()

    ref_link = (
        f"https://t.me/{me.username}"
        f"?start={user_id}"
    )

    data = await get_user_data(
        user_id
    )

    refs = data.get(
        "refs",
        0
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📤 Поделиться",
                    url=(
                        "https://t.me/share/url"
                        f"?url={ref_link}"
                    )
                )
            ],
            [
                InlineKeyboardButton(
                    text="◀️ Назад",
                    callback_data="menu"
                )
            ]
        ]
    )

    text = (
        "👥 <b>Реферальная система</b>\n"
        "━━━━━━━━━━━━━━━━━\n"
        f"🔗 Твоя ссылка:\n"
        f"<code>{ref_link}</code>\n\n"
        f"💎 За каждого реферала: "
        f"<b>{REF_BONUS:.2f} ⭐</b>\n"
        f"👥 Рефералов: "
        f"<code>{refs}</code>\n\n"
        "<i>Приглашай друзей и получай ⭐</i>"
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

    await state.set_state(
        WithdrawStates.waiting_for_amount
    )

    text = (
        "💸 <b>Вывод ⭐</b>\n"
        "━━━━━━━━━━━━━━━━━\n"
        f"Минимальная сумма: "
        f"<b>{MIN_WITHDRAW} ⭐</b>\n\n"
        "Введите количество звёзд:"
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
# СОЗДАНИЕ ЗАЯВКИ
# =========================================================

@dp.message(
    WithdrawStates.waiting_for_amount
)
async def process_withdraw(
    message: types.Message,
    state: FSMContext
):

    user_id = str(
        message.from_user.id
    )

    await ensure_user(
        user_id,
        message.from_user.username
        or f"User_{user_id[:6]}"
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
            f"❌ Минимальный вывод — "
            f"{MIN_WITHDRAW} ⭐",
            reply_markup=back_keyboard()
        )

        return

    if amount <= 0:

        await message.answer(
            "❌ Сумма должна быть больше нуля.",
            reply_markup=back_keyboard()
        )

        return

    data = await get_user_data(
        user_id
    )

    balance = float(
        data.get("balance", 0)
    )

    if balance < amount:

        await message.answer(
            "❌ Недостаточно средств.\n\n"
            f"Ваш баланс: "
            f"<code>{balance:.2f} ⭐</code>",
            reply_markup=back_keyboard(),
            parse_mode="HTML"
        )

        return

    if not SUPPORT_ID:

        await message.answer(
            "❌ Администратор не настроен.",
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

    # =====================================================
    # СОЗДАЁМ ЗАЯВКУ И РЕЗЕРВИРУЕМ СРЕДСТВА
    # =====================================================

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

            if not row or float(row["balance"]) < amount:

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
                    $1, $2, $3, $4, $5, 'pending', $6
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
                    "Не удалось списать баланс."
                )

    # =====================================================
    # СООБЩЕНИЕ АДМИНУ
    # =====================================================

    admin_text = (
        "💰 <b>НОВАЯ ЗАЯВКА НА ВЫВОД</b>\n"
        "━━━━━━━━━━━━━━━━━\n"
        f"👤 Имя: "
        f"{html.escape(full_name)}\n"
        f"🔗 Username: "
        f"{html.escape(username)}\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"⭐ Сумма: "
        f"<b>{amount:.2f} ⭐</b>\n"
        f"💎 Баланс до вывода: "
        f"<code>{balance_before:.2f} ⭐</code>\n"
        f"📅 Дата: {created_at}\n"
        "━━━━━━━━━━━━━━━━━\n"
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
            "❌ Не удалось отправить заявку админу.\n"
            "💎 Средства возвращены.",
            reply_markup=back_keyboard()
        )

        await state.clear()

        return

    await message.answer(
        (
            "✅ <b>Заявка отправлена!</b>\n\n"
            f"⭐ Сумма: "
            f"<code>{amount:.2f} ⭐</code>\n"
            "⏳ Ожидайте обработки."
        ),
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
                    "⚠️ Эта заявка уже обработана.",
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
            (
                "✅ <b>Вывод подтверждён!</b>\n\n"
                f"⭐ Сумма: "
                f"<code>{float(withdrawal['amount']):.2f} ⭐</code>\n"
                f"📝 Заявка №"
                f"<code>{withdrawal_id}</code>\n\n"
                "💎 Заявка обработана администратором."
            ),
            parse_mode="HTML"
        )

    except Exception as e:

        logger.warning(
            f"Не удалось уведомить пользователя: {e}"
        )

    new_text = (
        "✅ <b>ЗАЯВКА ПОДТВЕРЖДЕНА</b>\n"
        "━━━━━━━━━━━━━━━━━\n"
        f"👤 Имя: "
        f"{html.escape(withdrawal['full_name'])}\n"
        f"🔗 Username: "
        f"{html.escape(withdrawal['username'])}\n"
        f"🆔 ID: "
        f"<code>{withdrawal['user_id']}</code>\n"
        f"⭐ Сумма: "
        f"<b>{float(withdrawal['amount']):.2f} ⭐</b>\n"
        f"💎 Баланс до вывода: "
        f"<code>{float(withdrawal['balance_before']):.2f} ⭐</code>\n"
        f"📅 Дата: "
        f"{withdrawal['created_at']}\n"
        "━━━━━━━━━━━━━━━━━\n"
        "✅ Средства списаны\n"
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
        "✅ Заявка подтверждена!"
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
                    "⚠️ Эта заявка уже обработана.",
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
            (
                "❌ <b>Вывод отменён</b>\n\n"
                f"⭐ Возвращено: "
                f"<code>{float(withdrawal['amount']):.2f} ⭐</code>\n"
                f"📝 Заявка №"
                f"<code>{withdrawal_id}</code>\n\n"
                "💎 Средства возвращены на баланс."
            ),
            parse_mode="HTML"
        )

    except Exception as e:

        logger.warning(
            f"Не удалось уведомить пользователя: {e}"
        )

    new_text = (
        "❌ <b>ЗАЯВКА ОТМЕНЕНА</b>\n"
        "━━━━━━━━━━━━━━━━━\n"
        f"👤 Имя: "
        f"{html.escape(withdrawal['full_name'])}\n"
        f"🔗 Username: "
        f"{html.escape(withdrawal['username'])}\n"
        f"🆔 ID: "
        f"<code>{withdrawal['user_id']}</code>\n"
        f"⭐ Сумма: "
        f"<b>{float(withdrawal['amount']):.2f} ⭐</b>\n"
        f"💎 Баланс до вывода: "
        f"<code>{float(withdrawal['balance_before']):.2f} ⭐</code>\n"
        f"📅 Дата: "
        f"{withdrawal['created_at']}\n"
        "━━━━━━━━━━━━━━━━━\n"
        "🔄 Средства возвращены\n"
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
        "❌ Заявка отменена, средства возвращены."
    )


# =========================================================
# ТОП ЛИДЕРОВ
# =========================================================

@dp.callback_query(F.data == "leaders")
async def cb_leaders(
    call: types.CallbackQuery
):

    async with db_pool.acquire() as db:

        users = await db.fetch(
            """
            SELECT user_id, username, refs
            FROM users
            WHERE refs > 0
            ORDER BY refs DESC, user_id ASC
            LIMIT 10
            """
        )

    if not users:

        text = (
            "🏆 <b>ТОП ЛИДЕРОВ</b>\n"
            "━━━━━━━━━━━━━━━━━\n\n"
            "Пока нет рефералов 😔"
        )

        kb = back_keyboard()

    else:

        medals = [
            "🥇",
            "🥈",
            "🥉"
        ] + ["🏅"] * 7

        lines = [
            "🏆 <b>ТОП ЛИДЕРОВ</b>",
            "━━━━━━━━━━━━━━━━━"
        ]

        buttons = []

        for i, row in enumerate(users):

            uid = str(row["user_id"])

            username = (
                row["username"]
                or f"User_{uid[:6]}"
            )

            username = html.escape(
                username
            )

            refs = row["refs"]

            medal = medals[i]

            lines.append(
                f"{medal} <b>{username}</b> — "
                f"{refs} реф."
            )

            buttons.append([
                InlineKeyboardButton(
                    text=f"{medal} {username}",
                    url=f"tg://user?id={uid}"
                )
            ])

        buttons.append([
            InlineKeyboardButton(
                text="◀️ Назад",
                callback_data="menu"
            )
        ])

        kb = InlineKeyboardMarkup(
            inline_keyboard=buttons
        )

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

    async with db_pool.acquire() as db:

        row = await db.fetchrow(
            """
            SELECT
                COUNT(*) AS total_users,
                COALESCE(SUM(balance), 0) AS total_balance
            FROM users
            """
        )

    total_users = row["total_users"]

    total_balance = float(
        row["total_balance"]
    )

    text = (
        "⚙️ <b>АДМИН-ПАНЕЛЬ</b>\n"
        "━━━━━━━━━━━━━━━━━\n"
        f"👥 Пользователей: "
        f"<code>{total_users}</code>\n"
        f"💰 Балансов: "
        f"<code>{total_balance:.2f} ⭐</code>\n"
        "━━━━━━━━━━━━━━━━━"
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
        "💰 <b>Изменение баланса</b>\n"
        "━━━━━━━━━━━━━━━━━\n\n"
        "Введите:\n"
        "<code>ID Сумма</code>\n\n"
        "Добавить:\n"
        "<code>123456789 15</code>\n\n"
        "Списать:\n"
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
            "❌ Формат:\n"
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
            (
                "🔔 <b>Баланс изменён</b>\n\n"
                f"Изменение: "
                f"<b>{action} ⭐</b>\n"
                f"Баланс: "
                f"<code>{new_balance:.2f} ⭐</code>"
            ),
            parse_mode="HTML"
        )

    except Exception:
        pass

    await message.answer(
        (
            "✅ <b>Готово!</b>\n\n"
            f"Пользователь: "
            f"<code>{target_id}</code>\n"
            f"Баланс: "
            f"<code>{new_balance:.2f} ⭐</code>"
        ),
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
        "👥 <b>Выдать рефералов</b>\n"
        "━━━━━━━━━━━━━━━━━\n\n"
        "Введите:\n"
        "<code>ID Количество</code>\n\n"
        "Например:\n"
        "<code>6662093609 10</code>\n\n"
        "⚠️ Рефералы добавятся "
        "только к счётчику.\n"
        "Бонус ⭐ за них не начисляется."
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
            "❌ Формат:\n"
            "<code>ID Количество</code>\n\n"
            "Например:\n"
            "<code>6662093609 10</code>",
            reply_markup=back_keyboard(),
            parse_mode="HTML"
        )

        return

    target_id = parts[0]

    try:

        amount = int(parts[1])

    except ValueError:

        await message.answer(
            "❌ Количество должно быть "
            "целым числом.",
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

    try:

        await bot.send_message(
            int(target_id),
            (
                "👥 <b>Количество рефералов изменено</b>\n\n"
                f"➕ Добавлено: "
                f"<b>{amount}</b> реф.\n"
                f"👥 Всего: "
                f"<code>{new_refs}</code>"
            ),
            parse_mode="HTML"
        )

    except Exception:
        pass

    await message.answer(
        (
            "✅ <b>Рефералы добавлены!</b>\n\n"
            f"🆔 ID: <code>{target_id}</code>\n"
            f"➕ Добавлено: <b>{amount}</b>\n"
            f"👥 Всего: <code>{new_refs}</code>"
        ),
        reply_markup=admin_keyboard(),
        parse_mode="HTML"
    )

    await state.clear()


# =========================================================
# РАССЫЛКА ВСЕМ
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
        "📢 <b>РАССЫЛКА ВСЕМ</b>\n"
        "━━━━━━━━━━━━━━━━━\n\n"
        "Отправь сообщение, которое "
        "нужно разослать всем пользователям.\n\n"
        "⚠️ Бот отправит его всем "
        "пользователям из базы."
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
            "❌ Сообщение пустое.",
            reply_markup=back_keyboard()
        )

        return

    async with db_pool.acquire() as db:

        users = await db.fetch(
            "SELECT user_id FROM users"
        )

    total = len(users)

    await message.answer(
        (
            "🚀 <b>Рассылка началась!</b>\n\n"
            f"👥 Получателей: <code>{total}</code>"
        ),
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
        (
            "✅ <b>РАССЫЛКА ЗАВЕРШЕНА!</b>\n"
            "━━━━━━━━━━━━━━━━━\n"
            f"👥 Всего: <code>{total}</code>\n"
            f"✅ Доставлено: <code>{success}</code>\n"
            f"❌ Не доставлено: <code>{failed}</code>"
        ),
        reply_markup=admin_keyboard(),
        parse_mode="HTML"
    )

    await state.clear()


# =========================================================
# ЗАПУСК
# =========================================================

async def main():

    logger.info(
        "Запуск GiftsEzz..."
    )

    # PostgreSQL
    await init_db()

    # Web-сервер для Render
    web_runner = await start_web_server()

    me = await bot.get_me()

    logger.info(
        f"Бот @{me.username} успешно запущен"
    )

    try:

        await bot.set_my_description(
            "💎 GiftsEzz Bot — "
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


if __name__ == "__main__":

    try:

        asyncio.run(main())

    except (
        KeyboardInterrupt,
        SystemExit
    ):

        logger.info(
            "Бот остановлен"
        )

    except Exception as e:

        logger.error(
            f"Критическая ошибка: {e}"
        )

        raise
