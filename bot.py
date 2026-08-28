import os
import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
)

from database import (
    init_db,
    create_user,
    get_user,
    add_balance,
)


BOT_TOKEN = os.getenv("BOT_TOKEN")

BOT_USERNAME = os.getenv(
    "BOT_USERNAME",
    "GiftsEz_bot"
)

CHANNEL = os.getenv(
    "CHANNEL",
    "@eclipsedlf"
)

WEBAPP_URL = os.getenv(
    "WEBAPP_URL",
    ""
)

SUPPORT_USERNAME = os.getenv(
    "SUPPORT_USERNAME",
    "Eclipsed_consult"
)


logging.basicConfig(
    level=logging.INFO
)

bot = Bot(
    token=BOT_TOKEN
)

dp = Dispatcher()


# =========================
# КЛАВИАТУРА
# =========================

def main_keyboard():

    buttons = [
        [
            InlineKeyboardButton(
                text="🚀 Открыть GiftsEz",
                web_app=WebAppInfo(
                    url=WEBAPP_URL
                )
            )
        ],
        [
            InlineKeyboardButton(
                text="📢 Наш канал",
                url=f"https://t.me/{CHANNEL.lstrip('@')}"
            )
        ],
        [
            InlineKeyboardButton(
                text="💬 Поддержка",
                url=f"https://t.me/{SUPPORT_USERNAME}"
            )
        ]
    ]

    return InlineKeyboardMarkup(
        inline_keyboard=buttons
    )


# =========================
# ПРОВЕРКА ПОДПИСКИ
# =========================

async def is_subscribed(user_id: int):

    try:

        member = await bot.get_chat_member(
            chat_id=CHANNEL,
            user_id=user_id
        )

        return member.status in {
            "member",
            "administrator",
            "creator"
        }

    except Exception as error:

        logging.error(
            "Ошибка проверки подписки: %s",
            error
        )

        return False


# =========================
# START
# =========================

@dp.message(CommandStart())
async def start_handler(message: Message):

    user = message.from_user

    if not user:
        return

    # Реферальный параметр
    args = message.text.split(maxsplit=1)

    invited_by = None

    if len(args) > 1:

        payload = args[1]

        if payload.startswith("ref_"):

            try:

                invited_by = int(
                    payload.replace(
                        "ref_",
                        "",
                        1
                    )
                )

            except ValueError:
                invited_by = None

    # Нельзя пригласить самого себя
    if invited_by == user.id:
        invited_by = None

    existing = get_user(
        user.id
    )

    if not existing:

        create_user(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            invited_by=invited_by
        )

        # Начисляем рефереру только
        # при первой регистрации пользователя
        if invited_by:

            inviter = get_user(
                invited_by
            )

            if inviter:

                add_balance(
                    invited_by,
                    0.85
                )

                # Обновляем количество рефералов
                from database import get_connection

                conn = get_connection()
                cur = conn.cursor()

                cur.execute("""
                    UPDATE users
                    SET referrals = referrals + 1
                    WHERE user_id = %s
                """, (
                    invited_by,
                ))

                conn.commit()

                cur.close()
                conn.close()

    # Проверяем подписку
    subscribed = await is_subscribed(
        user.id
    )

    if not subscribed:

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📢 Подписаться",
                        url=f"https://t.me/{CHANNEL.lstrip('@')}"
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

        await message.answer(
            "🔒 Чтобы пользоваться GiftsEz, "
            "сначала подпишись на наш канал.",
            reply_markup=keyboard
        )

        return

    await message.answer(
        f"👋 Привет, {user.first_name}!\n\n"
        "Добро пожаловать в GiftsEz 💜\n\n"
        "Открой приложение ниже:",
        reply_markup=main_keyboard()
    )


# =========================
# ПРОВЕРКА ПОДПИСКИ
# =========================

@dp.callback_query(
    F.data == "check_sub"
)
async def check_subscription(callback):

    user = callback.from_user

    subscribed = await is_subscribed(
        user.id
    )

    if not subscribed:

        await callback.answer(
            "❌ Ты ещё не подписался.",
            show_alert=True
        )

        return

    await callback.message.edit_text(
        "✅ Подписка подтверждена!\n\n"
        "Теперь можешь открыть GiftsEz 💜",
        reply_markup=main_keyboard()
    )

    await callback.answer()


# =========================
# ЗАПУСК
# =========================

async def main():

    if not BOT_TOKEN:

        raise RuntimeError(
            "BOT_TOKEN не установлен"
        )

    init_db()

    logging.info(
        "GiftsEz bot started"
    )

    await dp.start_polling(
        bot
    )


if __name__ == "__main__":

    asyncio.run(
        main()
    )
