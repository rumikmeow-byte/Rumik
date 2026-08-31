import asyncio
import logging
import os
import random
from datetime import datetime, timedelta

import aiosqlite
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# ==================== НАСТРОЙКИ И ЛОГИ ====================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPPORT_ID = int(os.getenv("SUPPORT_ID", "0"))

# Наш канал
CHANNEL_ID = os.getenv("CHANNEL_ID", "@eclipsedlf")

CHAT_ID = os.getenv("CHAT_ID", "")

MIN_WITHDRAW = 10

# Бонус за каждого реферала
REF_BONUS = 0.85

DB_FILE = "database.db"


# ==================== РАБОТА С БАЗОЙ ДАННЫХ ====================

async def init_db() -> None:
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


async def ensure_user(user_id: str, username: str = "") -> None:
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute(
            "SELECT user_id FROM users WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()

        if not row:
            await db.execute(
                "INSERT INTO users (user_id, username) VALUES (?, ?)",
                (user_id, username)
            )
        elif username:
            await db.execute(
                "UPDATE users SET username = ? WHERE user_id = ?",
                (username, user_id)
            )

        await db.commit()


async def get_user_data(user_id: str) -> dict:
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            "SELECT * FROM users WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()

            return dict(row) if row else {}


# ==================== ИНИЦИАЛИЗАЦИЯ БОТА ====================

if not BOT_TOKEN:
    raise ValueError("Переменная BOT_TOKEN не задана!")

bot = Bot(token=BOT_TOKEN)

storage = MemoryStorage()
dp = Dispatcher(storage=storage)


# ==================== СОСТОЯНИЯ FSM ====================

class WithdrawStates(StatesGroup):
    waiting_for_amount = State()


class AdminStates(StatesGroup):
    waiting_for_give_data = State()
    waiting_for_broadcast_msg = State()


# ==================== КЛАВИАТУРЫ ====================

def sub_keyboard() -> InlineKeyboardMarkup:
    buttons = []

    if CHANNEL_ID:
        buttons.append([
            InlineKeyboardButton(
                text="📢 Наш канал",
                url=f"https://t.me/{CHANNEL_ID.replace('@', '')}"
            )
        ])

    if CHAT_ID:
        buttons.append([
            InlineKeyboardButton(
                text="💬 Наш чат",
                url=f"https://t.me/{CHAT_ID.replace('@', '')}"
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            text="✅ Проверить подписку",
            callback_data="check_sub"
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def main_menu_keyboard(user_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text="🎰 Рулетка",
                callback_data="roulette"
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
                text="🏆 Топ лидеров",
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


def back_keyboard() -> InlineKeyboardMarkup:
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


def admin_keyboard() -> InlineKeyboardMarkup:
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
                    text="◀️ Назад в меню",
                    callback_data="menu"
                )
            ]
        ]
    )


# ==================== ПРОВЕРКА ПОДПИСКИ ====================

async def check_subscription(user_id: int) -> bool:
    for chat in [CHANNEL_ID, CHAT_ID]:

        if not chat:
            continue

        try:
            member = await bot.get_chat_member(
                chat_id=chat,
                user_id=user_id
            )

            if member.status in ["left", "kicked"]:
                return False

        except Exception as e:
            logger.warning(
                f"Ошибка проверки подписки в {chat}: {e}"
            )
            return False

    return True


# ==================== ГЛАВНОЕ МЕНЮ ====================

async def show_menu(
    target: types.Message | types.CallbackQuery
) -> None:

    user = target.from_user

    user_id = str(user.id)

    await ensure_user(
        user_id,
        user.username or f"User_{user_id[:6]}"
    )

    user_data = await get_user_data(user_id)

    balance = user_data.get("balance", 0.0)

    text = (
        f"👋 Привет, <b>{user.full_name}</b>!\n\n"
        f"💎 Твой баланс: <code>{balance:.2f} ⭐</code>\n\n"
        f"Выбирай раздел в меню ниже:"
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
async def cmd_start(message: types.Message) -> None:

    user_id = str(message.from_user.id)

    await ensure_user(
        user_id,
        message.from_user.username or f"User_{user_id[:6]}"
    )

    args = message.text.split()

    # ==================== РЕФЕРАЛ ====================

    if len(args) > 1:

        ref_id = args[1]

        if ref_id != user_id:

            async with aiosqlite.connect(DB_FILE) as db:

                async with db.execute(
                    "SELECT referred_by FROM users WHERE user_id = ?",
                    (user_id,)
                ) as cursor:

                    user_row = await cursor.fetchone()

                async with db.execute(
                    "SELECT user_id FROM users WHERE user_id = ?",
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
                                f"🎉 По вашей ссылке "
                                f"зарегистрировался новый пользователь!\n\n"
                                f"💎 Вам начислено "
                                f"<b>+{REF_BONUS:.2f} ⭐</b>"
                            ),
                            parse_mode="HTML"
                        )

                    except Exception:
                        pass

    # ==================== ПРОВЕРКА ПОДПИСКИ ====================

    if (
        CHANNEL_ID
        or CHAT_ID
    ) and not await check_subscription(
        message.from_user.id
    ):

        await message.answer(
            "⚠️ Для использования бота подпишитесь на наш канал и чат!",
            reply_markup=sub_keyboard()
        )

        return

    await show_menu(message)


# ==================== ПРОВЕРКА ПОДПИСКИ ====================

@dp.callback_query(F.data == "check_sub")
async def cb_check_sub(call: types.CallbackQuery) -> None:

    if await check_subscription(call.from_user.id):

        await call.answer(
            "✅ Подписка подтверждена!"
        )

        await show_menu(call)

    else:

        await call.answer(
            "❌ Вы ещё не подписались на канал и чат!",
            show_alert=True
        )


# ==================== НАЗАД ====================

@dp.callback_query(F.data == "menu")
async def cb_menu(
    call: types.CallbackQuery,
    state: FSMContext
) -> None:

    await state.clear()

    await show_menu(call)


# ==================== РУЛЕТКА ====================

@dp.callback_query(F.data == "roulette")
async def cb_roulette(call: types.CallbackQuery) -> None:

    user_id = str(call.from_user.id)

    await ensure_user(
        user_id,
        call.from_user.username or f"User_{user_id[:6]}"
    )

    user_data = await get_user_data(user_id)

    last = user_data.get("last_daily")

    if last:

        try:

            last_dt = datetime.fromisoformat(last)

            if last_dt > datetime.now() - timedelta(days=1):

                await call.answer(
                    "⏳ Ты уже крутил сегодня! Жди завтра.",
                    show_alert=True
                )

                return

        except ValueError:
            pass

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

    now_str = datetime.now().isoformat()

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
                now_str,
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
        f"🎰 <b>Результат рулетки</b>\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"Вы выиграли: <code>{win} ⭐</code>\n"
        f"Новый баланс: <code>{new_balance:.2f} ⭐</code>\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"<i>Приходи завтра снова!</i>"
    )

    try:
        await call.message.delete()
    except Exception:
        pass

    await bot.send_message(
        chat_id=call.from_user.id,
        text=text,
        reply_markup=back_keyboard(),
        parse_mode="HTML"
    )

    await call.answer()


# ==================== РЕФЕРАЛЫ ====================

@dp.callback_query(F.data == "referrals")
async def cb_referrals(call: types.CallbackQuery) -> None:

    user_id = str(call.from_user.id)

    await ensure_user(
        user_id,
        call.from_user.username or f"User_{user_id[:6]}"
    )

    bot_info = await bot.get_me()

    ref_link = (
        f"https://t.me/{bot_info.username}?start={user_id}"
    )

    user_data = await get_user_data(user_id)

    refs_count = user_data.get(
        "refs",
        0
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📤 Поделиться",
                    switch_inline_query=ref_link
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
        f"👥 <b>Реферальная система</b>\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"Твоя ссылка:\n"
        f"<code>{ref_link}</code>\n\n"
        f"💎 За каждого приглашённого ты получаешь "
        f"<b>{REF_BONUS:.2f} ⭐</b>\n"
        f"👥 Всего рефералов: "
        f"<code>{refs_count}</code>\n\n"
        f"<i>Приглашай друзей и получай ⭐</i>"
    )

    try:
        await call.message.delete()
    except Exception:
        pass

    await bot.send_message(
        chat_id=call.from_user.id,
        text=text,
        reply_markup=kb,
        parse_mode="HTML"
    )

    await call.answer()


# ==================== ВЫВОД ====================

@dp.callback_query(F.data == "withdraw")
async def cb_withdraw(
    call: types.CallbackQuery,
    state: FSMContext
) -> None:

    await state.set_state(
        WithdrawStates.waiting_for_amount
    )

    text = (
        f"💸 <b>Вывод звёзд</b>\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"Минимальная сумма: "
        f"<b>{MIN_WITHDRAW} ⭐</b>\n\n"
        f"Введите количество звёзд для вывода:"
    )

    try:
        await call.message.delete()
    except Exception:
        pass

    await bot.send_message(
        chat_id=call.from_user.id,
        text=text,
        reply_markup=back_keyboard(),
        parse_mode="HTML"
    )

    await call.answer()


@dp.message(WithdrawStates.waiting_for_amount)
async def process_withdraw(
    message: types.Message,
    state: FSMContext
) -> None:

    user_id = str(message.from_user.id)

    await ensure_user(
        user_id,
        message.from_user.username or f"User_{user_id[:6]}"
    )

    try:

        amount = float(
            message.text.replace(",", ".").strip()
        )

    except ValueError:

        await message.answer(
            "❌ Введите число!",
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

    user_data = await get_user_data(user_id)

    balance = user_data.get(
        "balance",
        0.0
    )

    if balance < amount:

        await message.answer(
            "❌ Недостаточно средств!",
            reply_markup=back_keyboard()
        )

        return

    async with aiosqlite.connect(DB_FILE) as db:

        await db.execute(
            """
            UPDATE users
            SET balance = balance - ?
            WHERE user_id = ?
            """,
            (
                amount,
                user_id
            )
        )

        await db.commit()

    if SUPPORT_ID and SUPPORT_ID != 0:

        try:

            await bot.send_message(
                SUPPORT_ID,
                (
                    f"💰 <b>Заявка на вывод</b>\n"
                    f"━━━━━━━━━━━━━━━━━\n"
                    f"👤 Пользователь: "
                    f"{message.from_user.full_name}\n"
                    f"🆔 ID: <code>{user_id}</code>\n"
                    f"⭐ Сумма: "
                    f"<code>{amount:.2f}</code>\n"
                    f"📅 Дата: "
                    f"{datetime.now().strftime('%d.%m.%Y %H:%M')}"
                ),
                parse_mode="HTML"
            )

        except Exception as e:

            logger.error(
                f"Не удалось отправить заявку саппорту: {e}"
            )

    await message.answer(
        (
            f"✅ Заявка на "
            f"<code>{amount:.2f} ⭐</code> отправлена!\n"
            f"Ожидайте обработки."
        ),
        reply_markup=back_keyboard(),
        parse_mode="HTML"
    )

    await state.clear()


# ==================== ЛИДЕРЫ ====================

@dp.callback_query(F.data == "leaders")
async def cb_leaders(call: types.CallbackQuery) -> None:

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

            sorted_users = await cursor.fetchall()

    if not sorted_users:

        text = (
            "🏆 <b>ТОП РЕФЕРАЛОВ</b>\n"
            "━━━━━━━━━━━━━━━━━\n"
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
            "🏆 <b>ТОП РЕФЕРАЛОВ</b>",
            "━━━━━━━━━━━━━━━━━"
        ]

        buttons = []

        for i, row in enumerate(sorted_users):

            uid = row["user_id"]

            username = (
                row["username"]
                or f"User_{uid[:6]}"
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
        chat_id=call.from_user.id,
        text=text,
        reply_markup=kb,
        parse_mode="HTML"
    )

    await call.answer()


# ==================== АДМИН-ПАНЕЛЬ ====================

@dp.callback_query(F.data == "admin_panel")
@dp.message(Command("admin"))
async def show_admin_panel(
    event: types.Message | types.CallbackQuery
) -> None:

    user_id = event.from_user.id

    if (
        user_id != SUPPORT_ID
        or SUPPORT_ID == 0
    ):

        if isinstance(
            event,
            types.CallbackQuery
        ):

            await event.answer(
                "❌ У вас нет прав доступа!",
                show_alert=True
            )

        return

    async with aiosqlite.connect(DB_FILE) as db:

        async with db.execute(
            "SELECT COUNT(*), SUM(balance) FROM users"
        ) as cursor:

            row = await cursor.fetchone()

            total_users = (
                row[0]
                if row
                else 0
            )

            total_balance = (
                row[1]
                if row and row[1]
                else 0.0
            )

    text = (
        f"⚙️ <b>Панель администратора</b>\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"👥 Всего пользователей: "
        f"<code>{total_users}</code>\n"
        f"💰 Балансов в системе: "
        f"<code>{total_balance:.2f} ⭐</code>\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"Выберите действие:"
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
            chat_id=user_id,
            text=text,
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
) -> None:

    if call.from_user.id != SUPPORT_ID:
        return

    await state.set_state(
        AdminStates.waiting_for_give_data
    )

    text = (
        "💰 <b>Изменение баланса</b>\n\n"
        "Введите ID пользователя и сумму через пробел.\n\n"
        "<i>Добавление:</i> "
        "<code>123456789 15</code>\n"
        "<i>Списание:</i> "
        "<code>123456789 -10</code>"
    )

    try:
        await call.message.delete()
    except Exception:
        pass

    await bot.send_message(
        chat_id=call.from_user.id,
        text=text,
        reply_markup=back_keyboard(),
        parse_mode="HTML"
    )

    await call.answer()


@dp.message(AdminStates.waiting_for_give_data)
async def process_admin_give(
    message: types.Message,
    state: FSMContext
) -> None:

    if message.from_user.id != SUPPORT_ID:
        return

    parts = message.text.strip().split()

    if len(parts) != 2:

        await message.answer(
            "❌ Неверный формат!\n"
            "Введите: <code>ID Сумма</code>",
            reply_markup=back_keyboard(),
            parse_mode="HTML"
        )

        return

    target_id = parts[0]
    amount_str = parts[1]

    try:

        amount = float(
            amount_str.replace(",", ".")
        )

    except ValueError:

        await message.answer(
            "❌ Сумма должна быть числом!",
            reply_markup=back_keyboard()
        )

        return

    user_data = await get_user_data(
        target_id
    )

    if not user_data:

        await message.answer(
            "❌ Пользователь с таким ID "
            "не найден в базе!",
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

    updated_user = await get_user_data(
        target_id
    )

    new_bal = updated_user.get(
        "balance",
        0.0
    )

    try:

        action_str = (
            f"+{amount:.2f}"
            if amount > 0
            else f"{amount:.2f}"
        )

        await bot.send_message(
            int(target_id),
            (
                f"🔔 Ваш баланс был изменён "
                f"администратором: "
                f"<b>{action_str} ⭐</b>\n"
                f"Текущий баланс: "
                f"<code>{new_bal:.2f} ⭐</code>"
            ),
            parse_mode="HTML"
        )

    except Exception:
        pass

    await message.answer(
        (
            f"✅ Успешно!\n"
            f"Новый баланс пользователя "
            f"<code>{target_id}</code>: "
            f"<code>{new_bal:.2f} ⭐</code>"
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
) -> None:

    if call.from_user.id != SUPPORT_ID:
        return

    await state.set_state(
        AdminStates.waiting_for_broadcast_msg
    )

    text = (
        "📢 <b>Рассылка сообщений</b>\n\n"
        "Введите сообщение, которое нужно "
        "отправить всем пользователям:"
    )

    try:
        await call.message.delete()
    except Exception:
        pass

    await bot.send_message(
        chat_id=call.from_user.id,
        text=text,
        reply_markup=back_keyboard(),
        parse_mode="HTML"
    )

    await call.answer()


@dp.message(AdminStates.waiting_for_broadcast_msg)
async def process_admin_broadcast(
    message: types.Message,
    state: FSMContext
) -> None:

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
            f"✅ <b>Рассылка завершена!</b>\n\n"
            f"Успешно доставлено: "
            f"<code>{success}</code>\n"
            f"Не доставлено: "
            f"<code>{failed}</code>"
        ),
        reply_markup=admin_keyboard(),
        parse_mode="HTML"
    )

    await state.clear()


# ==================== ЗАПУСК ====================

async def main() -> None:

    logger.info(
        "Инициализация базы данных..."
    )

    await init_db()

    logger.info(
        "Запуск бота..."
    )

    me = await bot.get_me()

    logger.info(
        f"Бот @{me.username} успешно запущен"
    )

    try:

        await bot.set_my_description(
            "💎 GiftsEzz Bot — рулетка, "
            "рефералы, вывод ⭐"
        )

    except Exception as e:

        logger.warning(
            f"Не удалось установить описание: {e}"
        )

    await dp.start_polling(bot)


# ==================== START ====================

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
