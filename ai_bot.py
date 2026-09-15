import base64
import logging
import os

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandStart
from aiogram.types import BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from openai import AsyncOpenAI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai_bot")

BOT_TOKEN = os.environ["AI_BOT_TOKEN"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
REQUIRED_CHANNEL = os.getenv("REQUIRED_CHANNEL", "@Hoylis")
REQUIRED_CHANNEL_URL = os.getenv("REQUIRED_CHANNEL_URL", "https://t.me/Hoylis")
MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-2")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """Ты — умный русскоязычный AI-помощник в Telegram.
Решай задачи и объясняй решение понятным языком.
1. Сначала дай итоговый ответ, затем объясни ход решения.
2. Для математики показывай вычисления и проверку результата.
3. Для программирования давай рабочий код и объясняй, почему он работает.
4. Для актуальных вопросов используй веб-поиск и не выдумывай факты.
5. Если данных недостаточно, честно скажи, чего не хватает.
6. Отвечай структурировано и без лишней воды.
"""


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Задать вопрос", callback_data="ask")],
        [InlineKeyboardButton(text="🎨 Создать изображение", callback_data="image_help")],
        [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")],
    ])


def subscribe_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Подписаться на @Hoylis", url=REQUIRED_CHANNEL_URL)],
        [InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_subscription")],
    ])


async def is_subscribed(user_id: int) -> bool:
    """Проверяется заново при каждом действии. После отписки доступ закрывается."""
    try:
        member = await bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in {"creator", "administrator", "member"} or (
            member.status == "restricted" and getattr(member, "is_member", False)
        )
    except Exception as exc:
        logger.warning("Subscription check failed: %s", exc)
        return False


async def require_subscription(message: types.Message) -> bool:
    if await is_subscribed(message.from_user.id):
        return True
    await message.answer(
        "🔒 <b>Доступ закрыт</b>\n\n"
        "Чтобы пользоваться ботом, подпишись на <b>@Hoylis</b>.\n"
        "После подписки нажми «Проверить подписку».",
        parse_mode="HTML",
        reply_markup=subscribe_keyboard(),
    )
    return False


@dp.message(CommandStart())
async def start(message: types.Message):
    if not await require_subscription(message):
        return
    await message.answer(
        "🤖 <b>AI-ПОМОЩНИК</b>\n\n"
        "Решаю задачи, объясняю решения, помогаю с кодом и отвечаю на вопросы.\n\n"
        "🎨 Для картинки: <code>/image кот в космосе</code>",
        parse_mode="HTML",
        reply_markup=main_menu(),
    )


@dp.callback_query(F.data == "check_subscription")
async def check_subscription_callback(call: types.CallbackQuery):
    if await is_subscribed(call.from_user.id):
        await call.answer("Подписка подтверждена!", show_alert=True)
        await call.message.edit_text(
            "✅ <b>Подписка подтверждена!</b>\n\nТеперь бот доступен.",
            parse_mode="HTML",
            reply_markup=main_menu(),
        )
    else:
        await call.answer("Подписка не найдена. Подпишись на @Hoylis.", show_alert=True)


@dp.callback_query(F.data == "ask")
async def ask_callback(call: types.CallbackQuery):
    if not await is_subscribed(call.from_user.id):
        await call.answer("Сначала подпишись на @Hoylis.", show_alert=True)
        return
    await call.answer()
    await call.message.answer("💬 Напиши свой вопрос или задачу следующим сообщением.")


@dp.callback_query(F.data == "image_help")
async def image_help_callback(call: types.CallbackQuery):
    if not await is_subscribed(call.from_user.id):
        await call.answer("Сначала подпишись на @Hoylis.", show_alert=True)
        return
    await call.answer()
    await call.message.answer(
        "🎨 <b>Генерация изображения</b>\n\n"
        "Используй:\n<code>/image описание картинки</code>\n\n"
        "Например: <code>/image неоновый город будущего ночью</code>",
        parse_mode="HTML",
    )


@dp.callback_query(F.data == "help")
async def help_callback(call: types.CallbackQuery):
    if not await is_subscribed(call.from_user.id):
        await call.answer("Сначала подпишись на @Hoylis.", show_alert=True)
        return
    await call.answer()
    await call.message.answer(
        "ℹ️ <b>Что умеет бот</b>\n\n"
        "• решать задачи;\n"
        "• объяснять решение по шагам;\n"
        "• помогать с программированием;\n"
        "• отвечать на вопросы;\n"
        "• генерировать изображения.\n\n"
        "Просто напиши вопрос обычным сообщением.",
        parse_mode="HTML",
        reply_markup=main_menu(),
    )


@dp.message(Command("image"))
async def image_command(message: types.Message):
    if not await require_subscription(message):
        return
    prompt = message.text.partition(" ")[2].strip()
    if not prompt:
        await message.answer("Пример: <code>/image футуристический город ночью</code>", parse_mode="HTML")
        return
    await message.answer("🎨 Генерирую изображение…")
    try:
        result = await client.images.generate(
            model=IMAGE_MODEL,
            prompt=prompt,
            size="1024x1024",
            quality="auto",
            n=1,
        )
        image_bytes = base64.b64decode(result.data[0].b64_json)
        await message.answer_photo(
            BufferedInputFile(image_bytes, filename="generated.png"),
            caption=f"🎨 {prompt}",
        )
    except Exception:
        logger.exception("Image generation failed")
        await message.answer("Не удалось сгенерировать изображение. Проверь OPENAI_API_KEY и доступ к модели.")


@dp.message(F.text)
async def answer(message: types.Message):
    # Критично: подписка проверяется перед каждым сообщением.
    # Если пользователь отписался, бот больше не отвечает ему.
    if not await require_subscription(message):
        return
    text = message.text.strip()
    if not text:
        return
    await message.bot.send_chat_action(message.chat.id, "typing")
    try:
        response = await client.responses.create(
            model=MODEL,
            instructions=SYSTEM_PROMPT,
            input=text,
            tools=[{"type": "web_search"}],
        )
        answer_text = response.output_text or "Не удалось получить ответ."
        for i in range(0, len(answer_text), 4000):
            await message.answer(answer_text[i:i + 4000])
    except Exception:
        logger.exception("AI response failed")
        await message.answer("Произошла ошибка при обработке запроса. Попробуй ещё раз.")


async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
