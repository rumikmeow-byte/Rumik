import asyncio
import html
import logging
import os
import random
from datetime import date

import aiosqlite
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# ==================== НАСТРОЙКИ ====================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPPORT_ID = int(os.getenv("SUPPORT_ID", "0"))

CHANNEL_ID = "@eclipsedlf"
SUPPORT_USERNAME = "@Eclipsed_consult"

# Минимальный вывод
MIN_WITHDRAW = 15

# Бонус за реферала
REF_BONUS = 0.85

DB_FILE = "database.db"


# ==================== БОТ ====================

if not BOT_TOKEN:
    raise ValueError("Переменная BOT_TOKEN не задана!")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# ==================== СОСТОЯНИЯ ====================

class WithdrawStates(StatesGroup):
    waiting_for_amount = State()


class AdminStates(StatesGroup):
    waiting_for_give_data = State()
    waiting_for_broadcast_msg = State()


# ==================== БАЗА ====================

async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT,
                balance REAL DEFAULT 0.0,
                refs INTEGER DEFAULT 0,
                referred_by TEXT DEFAULT NULL,
                last_daily TEXT DEFAULT NULL
            )
        """)

        await db.commit()


async def ensure_user(user_id: str, username: str = ""):
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute(
            "SELECT user_id FROM users WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()

        if not row:
            await db.execute(
                """
                INSERT INTO users (user_id, username)
                VALUES (?, ?)
                """,
                (user_id, username)
            )

        elif username:
            await db.execute(
                """
                UPDATE users
                SET username = ?
                WHERE user_id = ?
                """,
                (username, user_id)
            )

        await db.commit()


async def get_user_data(user_id: str):
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            "SELECT * FROM users WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()

            return dict(row) if row else {}


# ==================== КЛАВИАТУРЫ ====================

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

    return InlineKeyboardMarkup(inline_keyboard=buttons)


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
                    text="📢 Рассылка",
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


# ==================== ПРОВЕРКА ПОДПИСКИ ====================

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


# ==================== ГЛАВНОЕ МЕНЮ ====================

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

    balance = data.get("balance", 0.0)

    name = html.escape(user.full_name)

    text = (
        f"👋 Привет, <b>{name}</b>!\n\n"
        f"💎 Твой баланс: "
        f"<code>{balance:.2f} ⭐</code>\n\n"
        f"Выбирай раздел:"
    )

    if isinstance(target, types.CallbackQuery):

        try:
            await target.message.delete()
        except Exception:
            pass

        await bot.send_message(
            chat_id=user.id,
            text=text,
            reply_markup=main_menu_keyboard(user.id),
            parse_mode="HTML"
        )

    else:

        await target.answer(
            text,
            reply_markup=main_menu_keyboard(user.id),
            parse_mode="HTML"
        )


# ==================== START ====================

@dp.message(CommandStart())
async def cmd_start(message: types.Message):

    user_id = str(message.from_user.id)

    await ensure_user(
        user_id,
        message.from_user.username or f"User_{user_id[:6]}"
    )

    args = message.text.split()

    # ---------- РЕФЕРАЛ ----------

    if len(args) > 1:

        ref_id = args[1]

        if ref_id != user_id:

            async with aiosqlite.connect(DB_FILE) as db:

                async with db.execute(
                    """
                    SELECT referred_by
                    FROM users
                    WHERE user_id = ?
                    """,
                    (user_id,)
                ) as cursor:
                    user_row = await cursor.fetchone()

                async with db.execute(
                    """
                    SELECT user_id
                    FROM users
                    WHERE user_id = ?
                    """,
                    (ref_id,)
                ) as cursor:
                    ref_exists = await cursor.fetchone()

                if (
                    ref_exists
                    and user_row
                    and user_row[0] is None
                ):

                    await db.execute(
                        """
                        UPDATE users
                        SET referred_by = ?
                        WHERE user_id = ?
                        """,
                        (ref_id, user_id)
                    )

                    await db.execute(
                        """
                        UPDATE users
                        SET refs = refs + 1,
                            balance = balance + ?
                        WHERE user_id = ?
                        """,
                        (REF_BONUS, ref_id)
                    )

                    await db.commit()

                    try:
                        await bot.send_message(
                            int(ref_id),
                            (
                                "🎉 Новый реферал!\n\n"
                                f"💎 Вам начислено "
                                f"<b>+{REF_BONUS:.2f} ⭐</b>"
                            ),
                            parse_mode="HTML"
                        )
                    except Exception:
                        pass

    # ---------- ПОДПИСКА ----------

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


# ==================== ПРОВЕРКА ПОДПИСКИ ====================

@dp.callback_query(F.data == "check_sub")
async def cb_check_sub(call: types.CallbackQuery):

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


# ==================== НАЗАД ====================

@dp.callback_query(F.data == "menu")
async def cb_menu(
    call: types.CallbackQuery,
    state: FSMContext
):

    await state.clear()

    await show_menu(call)


# ==================== РУЛЕТКА ====================

@dp.callback_query(F.data == "roulette")
async def cb_roulette(call: types.CallbackQuery):

    user_id = str(call.from_user.id)

    await ensure_user(
        user_id,
        call.from_user.username or f"User_{user_id[:6]}"
    )

    data = await get_user_data(user_id)

    today = date.today().isoformat()

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

    async with aiosqlite.connect(DB_FILE) as db:

        await db.execute(
            """
            UPDATE users
            SET balance = balance + ?,
                last_daily = ?
            WHERE user_id = ?
            """,
            (
                win,
                today,
                user_id
            )
        )

        await db.commit()

    new_data = await get_user_data(user_id)

    new_balance = new_data.get(
        "balance",
        0.0
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


# ==================== РЕФЕРАЛЫ ====================

@dp.callback_query(F.data == "referrals")
async def cb_referrals(call: types.CallbackQuery):

    user_id = str(call.from_user.id)

    await ensure_user(
        user_id,
        call.from_user.username or f"User_{user_id[:6]}"
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
        f"👥 Рефералов: <code>{refs}</code>\n\n"
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


# ==================== ВЫВОД ====================

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


@dp.message(WithdrawStates.waiting_for_amount)
async def process_withdraw(
    message: types.Message,
    state: FSMContext
):

    user_id = str(message.from_user.id)

    await ensure_user(
        user_id,
        message.from_user.username or f"User_{user_id[:6]}"
    )

    try:

        amount = float(
            message.text.replace(",", ".").strip()
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

    data = await get_user_data(user_id)

    balance = data.get("balance", 0.0)

    if balance < amount:

        await message.answer(
            f"❌ Недостаточно средств.\n\n"
            f"Ваш баланс: "
            f"<code>{balance:.2f} ⭐</code>",
            reply_markup=back_keyboard(),
            parse_mode="HTML"
        )

        return

    # Сначала отправляем заявку админу.
    # Баланс списываем только после успешной отправки.

    if not SUPPORT_ID:

        await message.answer(
            "❌ Администратор не настроен.",
            reply_markup=back_keyboard()
        )

        await state.clear()

        return

    try:

        username = (
            f"@{message.from_user.username}"
            if message.from_user.username
            else "нет username"
        )

        admin_text = (
            "💰 <b>НОВАЯ ЗАЯВКА НА ВЫВОД</b>\n"
            "━━━━━━━━━━━━━━━━━\n"
            f"👤 Имя: "
            f"{html.escape(message.from_user.full_name)}\n"
            f"🔗 Username: {username}\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"⭐ Сумма: <b>{amount:.2f} ⭐</b>\n"
            f"💎 Баланс: <code>{balance:.2f} ⭐</code>\n"
            f"📅 Дата: "
            f"{__import__('datetime').datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )

        await bot.send_message(
            SUPPORT_ID,
            admin_text,
            parse_mode="HTML"
        )

    except Exception as e:

        logger.error(
            f"Ошибка отправки заявки админу: {e}"
        )

        await message.answer(
            "❌ Не удалось отправить заявку "
            "администратору.\n"
            "Баланс не изменён.",
            reply_markup=back_keyboard()
        )

        await state.clear()

        return

    # Только после успешной отправки заявки списываем баланс.

    async with aiosqlite.connect(DB_FILE) as db:

        await db.execute(
            """
            UPDATE users
            SET balance = balance - ?
            WHERE user_id = ?
              AND balance >= ?
            """,
            (
                amount,
                user_id,
                amount
            )
        )

        await db.commit()

    await message.answer(
        (
            "✅ <b>Заявка отправлена!</b>\n\n"
            f"⭐ Сумма: <code>{amount:.2f} ⭐</code>\n"
            "⏳ Ожидайте обработки."
        ),
        reply_markup=back_keyboard(),
        parse_mode="HTML"
    )

    await state.clear()


# ==================== ТОП ====================

@dp.callback_query(F.data == "leaders")
async def cb_leaders(call: types.CallbackQuery):

    async with aiosqlite.connect(DB_FILE) as db:

        db.row_factory = aiosqlite.Row

        async with db.execute(
            """
            SELECT user_id, username, refs
            FROM users
            WHERE refs > 0
            ORDER BY refs DESC
            LIMIT 10
            """
        ) as cursor:

            users = await cursor.fetchall()

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

            uid = row["user_id"]

            username = (
                row["username"]
                or f"User_{uid[:6]}"
            )

            username = html.escape(username)

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


# ==================== АДМИН ====================

@dp.callback_query(F.data == "admin_panel")
@dp.message(Command("admin"))
async def show_admin_panel(
    event: types.Message | types.CallbackQuery
):

    if event.from_user.id != SUPPORT_ID:

        if isinstance(event, types.CallbackQuery):

            await event.answer(
                "❌ Нет доступа!",
                show_alert=True
            )

        return

    async with aiosqlite.connect(DB_FILE) as db:

        async with db.execute(
            "SELECT COUNT(*), SUM(balance) FROM users"
        ) as cursor:

            row = await cursor.fetchone()

    total_users = row[0] if row else 0
    total_balance = (
        row[1]
        if row and row[1]
        else 0
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

    if isinstance(event, types.CallbackQuery):

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


# ==================== ИЗМЕНЕНИЕ БАЛАНСА ====================

@dp.callback_query(F.data == "admin_give_balance")
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
        "💰 <b>Изменение баланса</b>\n\n"
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


@dp.message(AdminStates.waiting_for_give_data)
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

    async with aiosqlite.connect(DB_FILE) as db:

        await db.execute(
            """
            UPDATE users
            SET balance = balance + ?
            WHERE user_id = ?
            """,
            (
                amount,
                target_id
            )
        )

        await db.commit()

    updated = await get_user_data(
        target_id
    )

    new_balance = updated.get(
        "balance",
        0.0
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
            "✅ Готово!\n\n"
            f"Пользователь: "
            f"<code>{target_id}</code>\n"
            f"Баланс: "
            f"<code>{new_balance:.2f} ⭐</code>"
        ),
        reply_markup=admin_keyboard(),
        parse_mode="HTML"
    )

    await state.clear()


# ==================== РАССЫЛКА ====================

@dp.callback_query(F.data == "admin_broadcast")
async def cb_admin_broadcast(
    call: types.CallbackQuery,
    state: FSMContext
):

    if call.from_user.id != SUPPORT_ID:
        return

    await state.set_state(
        AdminStates.waiting_for_broadcast_msg
    )

    try:
        await call.message.delete()
    except Exception:
        pass

    await bot.send_message(
        call.from_user.id,
        (
            "📢 <b>Рассылка</b>\n\n"
            "Отправьте сообщение, "
            "которое нужно разослать."
        ),
        reply_markup=back_keyboard(),
        parse_mode="HTML"
    )

    await call.answer()


@dp.message(AdminStates.waiting_for_broadcast_msg)
async def process_admin_broadcast(
    message: types.Message,
    state: FSMContext
):

    if message.from_user.id != SUPPORT_ID:
        return

    broadcast_text = message.text

    await message.answer(
        "🚀 Начинаю рассылку..."
    )

    async with aiosqlite.connect(DB_FILE) as db:

        async with db.execute(
            "SELECT user_id FROM users"
        ) as cursor:

            users = await cursor.fetchall()

    success = 0
    failed = 0

    for row in users:

        uid = row[0]

        try:

            await bot.send_message(
                int(uid),
                broadcast_text
            )

            success += 1

            await asyncio.sleep(0.05)

        except Exception:

            failed += 1

    await message.answer(
        (
            "✅ <b>Рассылка завершена!</b>\n\n"
            f"Доставлено: <code>{success}</code>\n"
            f"Не доставлено: <code>{failed}</code>"
        ),
        reply_markup=admin_keyboard(),
        parse_mode="HTML"
    )

    await state.clear()


# ==================== ЗАПУСК ====================

async def main():

    logger.info(
        "Инициализация базы данных..."
    )

    await init_db()

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

    await dp.start_polling(bot)


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
