import os
import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
)

from database import (
    init_db,
    create_user,
    get_user,
    process_referral,
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

dp = Dispatcher()


# =========================
# КЛАВИАТУРА
# =========================

def main_keyboard():

    return InlineKeyboardMarkup(
        inline_keyboard=[
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
    )


# =========================
# КЛАВИАТУРА ПОДПИСКИ
# =========================

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
                    text="✅ Проверить подписку",
                    callback_data="check_sub"
                )
            ]
        ]
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

    invited_by = None

    # Получаем /start ref_ID
    args = message.text.split(
        maxsplit=1
    )

    if len(args) > 1:

        payload = args[1].strip()

        if payload.startswith("ref_"):

            try:

                invited_by = int(
                    payload[4:]
                )

            except ValueError:

                invited_by = None

    # Сам себя приглашать нельзя
    if invited_by == user.id:
        invited_by = None

    # Проверяем существующего пользователя
    existing = get_user(
        user.id
    )

    # Новый пользователь
    if not existing:

        # Сначала создаём пользователя
        # с балансом 0 ⭐
        create_user(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name
        )

        # Затем безопасно обрабатываем
        # реферала и +0.85 ⭐
        if invited_by:

            try:

                rewarded = process_referral(
                    inviter_id=invited_by,
                    invited_user_id=user.id,
                    reward=0.85
                )

                if rewarded:

                    logging.info(
                        "Реферал: %s пригласил %s, +0.85 ⭐",
                        invited_by,
                        user.id
                    )

            except Exception as error:

                logging.error(
                    "Ошибка реферала: %s",
                    error
                )

    # Проверяем подписку
    subscribed = await is_subscribed(
        user.id
    )

    if not subscribed:

        await message.answer(
            "🔒 <b>Доступ к GiftsEz</b>\n\n"
            "Чтобы пользоваться приложением, "
            "сначала подпишись на наш канал.\n\n"
            "После подписки нажми "
            "«Проверить подписку».",
            reply_markup=subscription_keyboard(),
            parse_mode="HTML"
        )

        return

    # Пользователь подписан
    await message.answer(
        f"👋 <b>Привет, {user.first_name}!</b>\n\n"
        "💜 Добро пожаловать в <b>GiftsEz</b>!\n\n"
        "Открой приложение, чтобы посмотреть "
        "баланс, рефералов, рулетку и другие функции.",
        reply_markup=main_keyboard(),
        parse_mode="HTML"
    )


# =========================
# ПРОВЕРКА ПОДПИСКИ
# =========================

@dp.callback_query(
    F.data == "check_sub"
)
async def check_subscription(
    callback: CallbackQuery
):

    user = callback.from_user

    subscribed = await is_subscribed(
        user.id
    )

    if not subscribed:

        await callback.answer(
            "❌ Ты ещё не подписался на канал.",
            show_alert=True
        )

        return

    try:

        await callback.message.edit_text(
            "✅ <b>Подписка подтверждена!</b>\n\n"
            "Теперь можешь открыть GiftsEz 💜",
            reply_markup=main_keyboard(),
            parse_mode="HTML"
        )

    except Exception:

        await callback.message.answer(
            "✅ Подписка подтверждена!\n\n"
            "Теперь можешь открыть GiftsEz 💜",
            reply_markup=main_keyboard()
        )

    await callback.answer()


# =========================
# ЗАПУСК
# =========================

async def main():

    global bot

    if not BOT_TOKEN:

        raise RuntimeError(
            "BOT_TOKEN не установлен в Environment Variables"
        )

    bot = Bot(
        token=BOT_TOKEN
    )

    init_db()

    logging.info(
        "GiftsEz bot started"
    )

    try:

        await dp.start_polling(
            bot
        )

    finally:

        await bot.session.close()


if __name__ == "__main__":

    asyncio.run(
        main()
    )
