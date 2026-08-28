import os
import asyncio
import logging
from decimal import Decimal, InvalidOperation

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
)
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest

from database import (
    init_db,
    create_user,
    get_user,
    add_balance,
    remove_balance,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")

CHANNEL = os.getenv("CHANNEL", "@eclipsedlf")
SUPPORT = "@Eclipsed_consult"

WEBAPP_URL = os.getenv("WEBAPP_URL", "")

REFERRAL_REWARD = Decimal("0.85")
MIN_WITHDRAW = Decimal("15")

dp = Dispatcher()


# =========================
# КНОПКИ
# =========================

def main_menu():
    buttons = []

    if WEBAPP_URL:
        buttons.append([
            InlineKeyboardButton(
                text="🚀 Открыть GiftsEz",
                web_app=WebAppInfo(url=WEBAPP_URL)
            )
        ])

    buttons += [
        [
            InlineKeyboardButton(
                text="👤 Профиль",
                callback_data="profile"
            ),
            InlineKeyboardButton(
                text="👥 Рефералы",
                callback_data="referrals"
            )
        ],
        [
            InlineKeyboardButton(
                text="🎰 Рулетка",
                callback_data="roulette"
            ),
            InlineKeyboardButton(
                text="🎁 Промокод",
                callback_data="promo"
            )
        ],
        [
            InlineKeyboardButton(
                text="⭐ Вывести Stars",
                callback_data="withdraw"
            )
        ],
        [
            InlineKeyboardButton(
                text="🏆 Лидеры",
                callback_data="leaders"
            )
        ],
        [
            InlineKeyboardButton(
                text="📢 Наш канал",
                url=f"https://t.me/{CHANNEL.lstrip('@')}"
            ),
            InlineKeyboardButton(
                text="💬 Поддержка",
                url=f"https://t.me/{SUPPORT.lstrip('@')}"
            )
        ],
    ]

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def back_button():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="menu"
                )
            ]
        ]
    )


# =========================
# ПРОВЕРКА ПОДПИСКИ
# =========================

async def check_subscription(bot: Bot, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(
            chat_id=CHANNEL,
            user_id=user_id
        )

        return member.status in {
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR,
        }

    except TelegramBadRequest:
        return False
    except Exception:
        return False


def subscription_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📢 Подписаться",
                    url=f"https://t.me/{CHANNEL.lstrip('@')}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="✅ Я подписался",
                    callback_data="check_subscription"
                )
            ]
        ]
    )


# =========================
# START
# =========================

@dp.message(CommandStart())
async def start(message: Message, bot: Bot):

    user_id = message.from_user.id

    existing_user = get_user(user_id)

    if not existing_user:

        invited_by = None

        args = message.text.split(maxsplit=1)

        if len(args) > 1:
            start_arg = args[1]

            if start_arg.startswith("ref_"):
                try:
                    inviter_id = int(
                        start_arg.replace("ref_", "")
                    )

                    if inviter_id != user_id:
                        inviter = get_user(inviter_id)

                        if inviter:
                            invited_by = inviter_id

                except ValueError:
                    pass

        create_user(
            user_id=user_id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            invited_by=invited_by
        )

        # Реферальный бонус начисляется только
        # при первом создании пользователя.
        if invited_by:
            add_balance(
                invited_by,
                REFERRAL_REWARD
            )

            # Увеличиваем счётчик рефералов
            from database import get_connection

            conn = get_connection()
            cur = conn.cursor()

            cur.execute(
                """
                UPDATE users
                SET referrals = referrals + 1
                WHERE user_id = %s
                """,
                (invited_by,)
            )

            conn.commit()
            cur.close()
            conn.close()

    subscribed = await check_subscription(
        bot,
        user_id
    )

    if not subscribed:
        await message.answer(
            "🔒 <b>Доступ к GiftsEz закрыт</b>\n\n"
            "Чтобы пользоваться ботом, сначала подпишись "
            "на наш канал.",
            reply_markup=subscription_keyboard(),
            parse_mode="HTML"
        )
        return

    await message.answer(
        "💜 <b>Добро пожаловать в GiftsEz!</b>\n\n"
        "Здесь ты можешь получать Stars, "
        "приглашать друзей и участвовать в ежедневной рулетке.\n\n"
        "⭐ Начальный баланс: <b>0.00 Stars</b>",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )


# =========================
# ПРОВЕРКА ПОДПИСКИ
# =========================

@dp.callback_query(F.data == "check_subscription")
async def check_subscription_callback(
    callback: CallbackQuery,
    bot: Bot
):

    subscribed = await check_subscription(
        bot,
        callback.from_user.id
    )

    if not subscribed:
        await callback.answer(
            "❌ Ты ещё не подписан на канал.",
            show_alert=True
        )
        return

    await callback.message.edit_text(
        "💜 <b>Подписка подтверждена!</b>\n\n"
        "Добро пожаловать в GiftsEz ⭐",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )

    await callback.answer()


# =========================
# ГЛАВНОЕ МЕНЮ
# =========================

@dp.callback_query(F.data == "menu")
async def menu_callback(callback: CallbackQuery):

    await callback.message.edit_text(
        "💜 <b>GiftsEz</b>\n\n"
        "Выбери нужный раздел:",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )

    await callback.answer()


# =========================
# ПРОФИЛЬ
# =========================

@dp.callback_query(F.data == "profile")
async def profile_callback(callback: CallbackQuery):

    user = get_user(callback.from_user.id)

    if not user:
        await callback.answer(
            "Сначала нажми /start",
            show_alert=True
        )
        return

    balance = Decimal(str(user["balance"]))

    username = (
        f"@{user['username']}"
        if user["username"]
        else "не указан"
    )

    text = (
        "👤 <b>Твой профиль</b>\n\n"
        f"🆔 ID: <code>{user['user_id']}</code>\n"
        f"👤 Username: {username}\n\n"
        f"⭐ Баланс: <b>{balance:.2f}</b>\n"
        f"👥 Рефералов: <b>{user['referrals']}</b>"
    )

    await callback.message.edit_text(
        text,
        reply_markup=back_button(),
        parse_mode="HTML"
    )

    await callback.answer()


# =========================
# РЕФЕРАЛЫ
# =========================

@dp.callback_query(F.data == "referrals")
async def referrals_callback(callback: CallbackQuery):

    user = get_user(callback.from_user.id)

    if not user:
        await callback.answer(
            "Сначала нажми /start",
            show_alert=True
        )
        return

    bot_info = await callback.bot.get_me()

    referral_link = (
        f"https://t.me/{bot_info.username}"
        f"?start=ref_{callback.from_user.id}"
    )

    text = (
        "👥 <b>Реферальная система</b>\n\n"
        "Приглашай друзей и получай:\n"
        "⭐ <b>+0.85 Stars</b> за нового пользователя.\n\n"
        f"👥 Приглашено: <b>{user['referrals']}</b>\n\n"
        "🔗 <b>Твоя ссылка:</b>\n"
        f"<code>{referral_link}</code>"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📤 Поделиться ссылкой",
                    switch_inline_query=referral_link
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="menu"
                )
            ]
        ]
    )

    await callback.message.edit_text(
        text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    await callback.answer()


# =========================
# ПРОМОКОД
# =========================

@dp.callback_query(F.data == "promo")
async def promo_callback(callback: CallbackQuery):

    await callback.message.edit_text(
        "🎁 <b>Активация промокода</b>\n\n"
        "Отправь промокод отдельным сообщением.\n\n"
        "⚠️ Бот не показывает список доступных промокодов.",
        reply_markup=back_button(),
        parse_mode="HTML"
    )

    await callback.answer()


# =========================
# ВЫВОД
# =========================

@dp.callback_query(F.data == "withdraw")
async def withdraw_callback(callback: CallbackQuery):

    user = get_user(callback.from_user.id)

    balance = Decimal(str(user["balance"]))

    await callback.message.edit_text(
        "⭐ <b>Вывод Stars</b>\n\n"
        f"Твой баланс: <b>{balance:.2f} ⭐</b>\n\n"
        f"Минимальная сумма: <b>{MIN_WITHDRAW} ⭐</b>\n\n"
        "✍️ Напиши сумму, которую хочешь вывести.",
        reply_markup=back_button(),
        parse_mode="HTML"
    )

    await callback.answer()


# =========================
# ЛИДЕРЫ
# =========================

@dp.callback_query(F.data == "leaders")
async def leaders_callback(callback: CallbackQuery):

    from database import get_connection

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT username, first_name, referrals
        FROM users
        ORDER BY referrals DESC
        LIMIT 5
        """
    )

    leaders = cur.fetchall()

    cur.close()
    conn.close()

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]

    text = "🏆 <b>Топ-5 рефералов</b>\n\n"

    if not leaders:
        text += "Пока никто не приглашал друзей."
    else:
        for i, row in enumerate(leaders):
            username, first_name, referrals = row

            name = (
                f"@{username}"
                if username
                else first_name or "Пользователь"
            )

            text += (
                f"{medals[i]} <b>{name}</b> — "
                f"{referrals} реф.\n"
            )

    await callback.message.edit_text(
        text,
        reply_markup=back_button(),
        parse_mode="HTML"
    )

    await callback.answer()


# =========================
# РУЛЕТКА
# =========================

@dp.callback_query(F.data == "roulette")
async def roulette_callback(callback: CallbackQuery):

    await callback.message.edit_text(
        "🎰 <b>Ежедневная рулетка</b>\n\n"
        "Доступна 1 раз в день.\n\n"
        "🎁 Возможные награды:\n"
        "⭐ 0.5\n"
        "⭐ 5\n"
        "⭐ 10\n"
        "⭐ 15",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🎰 Крутить",
                        callback_data="spin"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="⬅️ Назад",
                        callback_data="menu"
                    )
                ]
            ]
        ),
        parse_mode="HTML"
    )

    await callback.answer()


@dp.callback_query(F.data == "spin")
async def spin_callback(callback: CallbackQuery):

    from database import get_connection
    from datetime import date
    import random

    today = date.today()

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT reward
        FROM roulette_uses
        WHERE user_id = %s AND play_date = %s
        """,
        (callback.from_user.id, today)
    )

    already_used = cur.fetchone()

    if already_used:
        cur.close()
        conn.close()

        await callback.answer(
            "🎰 Ты уже крутил сегодня.",
            show_alert=True
        )
        return

    # Веса нормализуются автоматически.
    rewards = [
        (Decimal("0.5"), 50),
        (Decimal("5"), 30),
        (Decimal("10"), 15),
        (Decimal("15"), 10),
    ]

    reward = random.choices(
        [r[0] for r in rewards],
        weights=[r[1] for r in rewards],
        k=1
    )[0]

    cur.execute(
        """
        INSERT INTO roulette_uses
            (user_id, play_date, reward)
        VALUES
            (%s, %s, %s)
        """,
        (
            callback.from_user.id,
            today,
            reward
        )
    )

    conn.commit()
    cur.close()
    conn.close()

    add_balance(
        callback.from_user.id,
        reward
    )

    await callback.message.edit_text(
        "🎰 <b>Рулетка</b>\n\n"
        f"🎉 Тебе выпало:\n"
        f"⭐ <b>{reward}</b> Stars\n\n"
        "Возвращайся завтра!",
        reply_markup=back_button(),
        parse_mode="HTML"
    )

    await callback.answer()


# =========================
# ВВОД СУММЫ ВЫВОДА
# =========================

@dp.message()
async def text_handler(message: Message):

    text = message.text.strip()

    try:
        amount = Decimal(text.replace(",", "."))
    except (InvalidOperation, AttributeError):
        return

    if amount < MIN_WITHDRAW:
        await message.answer(
            f"❌ Минимальная сумма вывода — "
            f"<b>{MIN_WITHDRAW} ⭐</b>.",
            parse_mode="HTML"
        )
        return

    user = get_user(message.from_user.id)

    if not user:
        return

    balance = Decimal(str(user["balance"]))

    if amount > balance:
        await message.answer(
            f"❌ Недостаточно Stars.\n\n"
            f"Твой баланс: <b>{balance:.2f} ⭐</b>",
            parse_mode="HTML"
        )
        return

    # Пока создаём заявку только после проверки.
    # Списание произойдёт здесь.
    success = remove_balance(
        message.from_user.id,
        amount
    )

    if not success:
        await message.answer(
            "❌ Не удалось создать заявку. "
            "Попробуй ещё раз."
        )
        return

    from database import get_connection

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO withdrawals
            (user_id, amount, status)
        VALUES
            (%s, %s, 'pending')
        RETURNING id
        """,
        (
            message.from_user.id,
            amount
        )
    )

    request_id = cur.fetchone()[0]

    conn.commit()
    cur.close()
    conn.close()

    await message.answer(
        "✅ <b>Заявка создана</b>\n\n"
        f"🆔 Заявка: <code>#{request_id}</code>\n"
        f"⭐ Сумма: <b>{amount:.2f}</b>\n\n"
        "📨 Заявка отправлена в поддержку.",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )

    # Отправляем заявку в поддержку
    try:
        await message.bot.send_message(
            chat_id=SUPPORT,
            text=(
                "💸 <b>Новая заявка на вывод</b>\n\n"
                f"🆔 Заявка: <code>#{request_id}</code>\n"
                f"👤 Пользователь: "
                f"<code>{message.from_user.id}</code>\n"
                f"👤 Username: "
                f"@{message.from_user.username}"
                if message.from_user.username
                else f"👤 Username: не указан"
            ),
            parse_mode="HTML"
        )

        await message.bot.send_message(
            chat_id=SUPPORT,
            text=(
                f"⭐ Сумма: <b>{amount:.2f} Stars</b>\n"
                f"📊 Статус: pending"
            ),
            parse_mode="HTML"
        )

    except Exception as e:
        logging.error(
            "Ошибка отправки заявки в поддержку: %s",
            e
        )


# =========================
# ЗАПУСК
# =========================

async def main():

    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN не установлен"
        )

    logging.basicConfig(
        level=logging.INFO
    )

    init_db()

    bot = Bot(
        token=BOT_TOKEN
    )

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
