import base64
import io
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
REQUIRED_CHANNEL = os.getenv("REQUIRED_CHANNEL", "@Xoylis")
REQUIRED_CHANNEL_URL = os.getenv("REQUIRED_CHANNEL_URL", "https://t.me/Xoylis")
MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-2")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """Ты — умный русскоязычный AI-помощник в Telegram.
Твоя задача — решать задачи и объяснять решение понятным языком.
Правила:
1. Сначала дай правильный итоговый ответ, затем объясни ход решения.
2. Для математики показывай вычисления и проверку результата.
3. Для программирования давай рабочий код и объясняй, почему он работает.
4. Если вопрос зависит от актуальных данных, не выдумывай факты; используй доступный веб-поиск и указывай, что именно проверено.
5. Если данных недостаточно, честно скажи, чего не хватает.
6. Не утверждай, что ответ абсолютно безошибочен: при сложных вопросах укажи возможные ограничения.
7. Отвечай структурировано и без лишней воды.
"""


def subscribe_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Подписаться на @Xoylis", url=REQUIRED_CHANNEL_URL)],
        [InlineKeyboardButton(text="✅ Я подписался — проверить", callback_data="check_subscription")],
    ])


async def is_subscribed(user_id: int) -> bool:
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
        "🔒 Чтобы пользоваться AI-помощником, сначала подпишись на @Xoylis.",
        reply_markup=subscribe_keyboard(),
    )
    return False


@dp.message(CommandStart())
async def start(message: types.Message):
    if not await require_subscription(message):
        return
    await message.answer(
        "🤖 <b>AI-помощник</b>\n\n"
        "Решаю задачи, объясняю решения, помогаю с кодом и отвечаю на вопросы.\n\n"
        "🎨 Для картинки напиши: <code>/image кот в космосе</code>",
        parse_mode="HTML",
    )


@dp.callback_query(F.data == "check_subscription")
async def check_subscription_callback(call: types.CallbackQuery):
    if await is_subscribed(call.from_user.id):
        await call.answer("Подписка подтверждена!", show_alert=True)
        await call.message.edit_text("✅ Подписка подтверждена. Теперь можешь задавать вопросы!")
    else:
        await call.answer("Подписка пока не найдена. Подпишись и попробуй ещё раз.", show_alert=True)


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
        await message.answer("Не удалось сгенерировать изображение. Проверь настройки OPENAI_API_KEY и доступ к модели.")


@dp.message(F.text)
async def answer(message: types.Message):
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
        # Telegram has a message length limit; split long answers safely.
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
