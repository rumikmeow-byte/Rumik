```python
import asyncio
import json
import logging
import os
import random
from datetime import datetime, timedelta
from pathlib import Path

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from dotenv import load_dotenv

load_dotenv()

# ==================== ЛОГИРОВАНИЕ ====================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ==================== КОНФИГ ====================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@eclipsedlf")
CHAT_ID = os.getenv("CHAT_ID", "@GiftsEzzChat")
SUPPORT_ID = int(os.getenv("SUPPORT_ID", "8644223884"))
MIN_WITHDRAW = float(os.getenv("MIN_WITHDRAW", "15"))
REF_BONUS = float(os.getenv("REF_BONUS", "0.85"))
PHOTO_URL = os.getenv(
    "PHOTO_URL",
    "https://ibb.co.com/LXpHddPF",  # обновлено
)

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан! Добавь переменную окружения BOT_TOKEN.")

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

DATA_FILE = Path("data.json")

# ==================== ХРАНИЛИЩЕ ====================
def load_data() -> dict:
    if not DATA_FILE.exists():
        return {"users": {}, "refers": {}, "daily": {}}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка чтения data.json: {e}")
        return {"users": {}, "refers": {}, "daily": {}}

def save_data(data: dict) -> None:
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Ошибка сохранения data.json: {e}")

data = load_data()

class WithdrawStates(StatesGroup):
    waiting_for_amount = State()

# ==================== КЛАВИАТУРЫ ====================
def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🟢 🎰 РУЛЕТКА", callback_data="roulette")],
            [
                InlineKeyboardButton(text="🔴 👥 Рефералы", callback_data="referrals"),
                InlineKeyboardButton(text="🔴 ⭐ Вывод", callback_data="withdraw"),
            ],
            [
                InlineKeyboardButton(text="🟢 🏆 Лидеры", callback_data="leaders"),
                InlineKeyboardButton(text="🟢 🆘 Поддержка", url="https://t.me/Eclipsed_consult"),
                InlineKeyboardButton(text="🟢 📢 Канал", url="https://t.me/eclipsedlf"),
            ],
        ]
    )

def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="menu")]
        ]
    )

def sub_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📢 ПОДПИСАТЬСЯ НА КАНАЛ",
                    url="https://t.me/eclipsedlf",
                )
            ],
            [
                InlineKeyboardButton(
                    text="💬 ПОДПИСАТЬСЯ НА ЧАТ",
                    url="https://t.me/GiftsEzzChat",
                )
            ],
            [
                InlineKeyboardButton(
                    text="✅ Я ПОДПИСАЛСЯ!",
                    callback_data="check_sub",
                )
            ],
        ]
    )

# ==================== ПРОВЕРКА ПОДПИСКИ ====================
async def check_subscription(user_id: int) -> bool:
    try:
        member_ch = await bot.get_chat_member(CHANNEL_ID, user_id)
        member_chat = await bot.get_chat_member(CHAT_ID, user_id)
        ok_statuses = {"member", "administrator", "creator"}
        return (
            member_ch.status in ok_statuses
            and member_chat.status in ok_statuses
        )
    except Exception as e:
        logger.warning(f"Ошибка проверки подписки {user_id}: {e}")
        return False

def ensure_user(user_id: str, username: str) -> None:
    if user_id not in data["users"]:
        data["users"][user_id] = {
            "balance": 0.0,
            "refs": 0,
            "username": username,
        }
        data["refers"][user_id] = []
        data["daily"][user_id] = None
        save_data(data)
    else:
        if data["users"][user_id].get("username") != username:
            data["users"][user_id]["username"] = username
            save_data(data)

# ==================== МЕНЮ ====================
async def show_menu(target: types.Message | types.CallbackQuery) -> None:
    if isinstance(target, types.CallbackQuery):
        user = target.from_user
        chat_id = target.from_user.id
        try:
            await target.message.delete()
        except Exception:
            pass
    else:
        user = target.from_user
        chat_id = target.chat.id

    user_id = str(user.id)
    user_data = data["users"].get(user_id, {"balance": 0.0, "refs": 0})
    balance = user_data.get("balance", 0.0)
    refs = user_data.get("refs", 0)

    text = (
        f"Добро пожаловать в <b>GiftsEzz</b>!\n\n"
        f"🌟 <b>Ваш профиль</b>\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"⭐ Баланс: <code>{balance:.2f}</code>\n"
        f"👥 Рефералов: <code>{refs}</code>\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"💎 GiftsEzz <3"
    )

    try:
        await bot.send_photo(
            chat_id=chat_id,
            photo=PHOTO_URL,
            caption=text,
            reply_markup=main_keyboard(),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning(f"Не удалось отправить фото: {e}")
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=main_keyboard(),
            parse_mode="HTML",
        )

# ==================== /start ====================
@dp.message(CommandStart())
async def cmd_start(message: types.Message) -> None:
    args = message.text.split(maxsplit=1)
    ref_id = args[1].strip() if len(args) > 1 else None

    user_id = str(message.from_user.id)
    username = message.from_user.username or f"User_{user_id[:6]}"
    ensure_user(user_id, username)

    if (
        ref_id
        and ref_id != user_id
        and ref_id in data["users"]
        and user_id not in data["refers"].get(ref_id, [])
    ):
        data["users"][ref_id]["balance"] = (
            data["users"][ref_id].get("balance", 0.0) + REF_BONUS
        )
        data["users"][ref_id]["refs"] = data["users"][ref_id].get("refs", 0) + 1
        data["refers"].setdefault(ref_id, []).append(user_id)
        save_data(data)
        try:
            await bot.send_message(
                int(ref_id),
                f"🎉 Новый реферал! +{REF_BONUS} ⭐",
            )
        except Exception as e:
            logger.warning(f"Не удалось уведомить реферера {ref_id}: {e}")

    if not await check_subscription(message.from_user.id):
        await message.answer(
            "🌸 <b>ДОБРО ПОЖАЛОВАТЬ!</b>\n\n"
            "❕ Подпишитесь на канал и чат, чтобы получить доступ:\n"
            "• 🎰 Ежедневная рулетка\n"
            f"• 👥 Рефералы (+{REF_BONUS} ⭐)\n"
            f"• 💰 Вывод от {MIN_WITHDRAW} ⭐\n"
            "• 🏆 Топ лидеров\n\n"
            "⚠️ <i>Без подписки бот не работает!</i>",
            reply_markup=sub_keyboard(),
            parse_mode="HTML",
        )
        return

    await show_menu(message)

@dp.callback_query(F.data == "check_sub")
async def cb_check_sub(call: types.CallbackQuery) -> None:
    if await check_subscription(call.from_user.id):
        await call.answer("✅ Подписка подтверждена!")
        await show_menu(call)
    else:
        await call.answer("❌ Вы ещё не подписались на канал и чат!", show_alert=True)

@dp.callback_query(F.data == "menu")
async def cb_menu(call: types.CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await show_menu(call)

# ==================== РУЛЕТКА ====================
@dp.callback_query(F.data == "roulette")
async def cb_roulette(call: types.CallbackQuery) -> None:
    user_id = str(call.from_user.id)
    ensure_user(user_id, call.from_user.username or f"User_{user_id[:6]}")

    last = data["daily"].get(user_id)
    if last:
        try:
            last_dt = datetime.fromisoformat(last)
            if last_dt > datetime.now() - timedelta(days=1):
                await call.answer(
                    "⏳ Ты уже крутил сегодня! Жди завтра.",
                    show_alert=True,
                )
                return
        except ValueError:
            pass

    prizes = [0.5, 5, 6, 10]
    weights = [50, 30, 15, 5]  # сумма 100
    win = random.choices(prizes, weights=weights)[0]

    data["users"][user_id]["balance"] = (
        data["users"][user_id].get("balance", 0.0) + win
    )
    data["daily"][user_id] = datetime.now().isoformat()
    save_data(data)

    text = (
        f"🎰 <b>Результат рулетки</b>\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"Вы выиграли: <code>{win} ⭐</code>\n"
        f"Новый баланс: <code>{data['users'][user_id]['balance']:.2f} ⭐</code>\n"
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
        parse_mode="HTML",
    )
    await call.answer()

# ==================== РЕФЕРАЛЫ ====================
@dp.callback_query(F.data == "referrals")
async def cb_referrals(call: types.CallbackQuery) -> None:
    user_id = str(call.from_user.id)
    ensure_user(user_id, call.from_user.username or f"User_{user_id[:6]}")

    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
    refs_count = data["users"].get(user_id, {}).get("refs", 0)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📤 Поделиться",
                    switch_inline_query=ref_link,
                )
            ],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="menu")],
        ]
    )

    text = (
        f"👥 <b>Реферальная система</b>\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"Твоя ссылка:\n<code>{ref_link}</code>\n\n"
        f"За каждого приглашённого ты получаешь <b>{REF_BONUS} ⭐</b>\n"
        f"Всего рефералов: <code>{refs_count}</code>\n\n"
        f"<i>Нажми на ссылку, чтобы скопировать</i>"
    )

    try:
        await call.message.delete()
    except Exception:
        pass
    await bot.send_message(
        chat_id=call.from_user.id,
        text=text,
        reply_markup=kb,
        parse_mode="HTML",
    )
    await call.answer()

# ==================== ВЫВОД ====================
@dp.callback_query(F.data == "withdraw")
async def cb_withdraw(call: types.CallbackQuery, state: FSMContext) -> None:
    await state.set_state(WithdrawStates.waiting_for_amount)

    text = (
        f"💸 <b>Вывод звёзд</b>\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"Минимальная сумма: <b>{MIN_WITHDRAW} ⭐</b>\n\n"
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
        parse_mode="HTML",
    )
    await call.answer()

@dp.message(WithdrawStates.waiting_for_amount)
async def process_withdraw(message: types.Message, state: FSMContext) -> None:
    user_id = str(message.from_user.id)
    ensure_user(user_id, message.from_user.username or f"User_{user_id[:6]}")

    try:
        amount = float(message.text.replace(",", ".").strip())
    except ValueError:
        await message.answer("❌ Введите число!", reply_markup=back_keyboard())
        return

    if amount < MIN_WITHDRAW:
        await message.answer(
            f"❌ Минимальный вывод — {MIN_WITHDRAW} ⭐",
            reply_markup=back_keyboard(),
        )
        return

    balance = data["users"][user_id].get("balance", 0.0)
    if balance < amount:
        await message.answer(
            "❌ Недостаточно средств!",
            reply_markup=back_keyboard(),
        )
        return

    data["users"][user_id]["balance"] = balance - amount
    save_data(data)

    try:
        await bot.send_message(
            SUPPORT_ID,
            f"💰 <b>Заявка на вывод</b>\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"👤 Пользователь: {message.from_user.full_name}\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"⭐ Сумма: <code>{amount:.2f}</code>\n"
            f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"Не удалось отправить заявку саппорту: {e}")

    await message.answer(
        f"✅ Заявка на <code>{amount:.2f} ⭐</code> отправлена!\n"
        f"Ожидайте обработки.",
        reply_markup=back_keyboard(),
        parse_mode="HTML",
    )
    await state.clear()

# ==================== ЛИДЕРЫ ====================
@dp.callback_query(F.data == "leaders")
async def cb_leaders(call: types.CallbackQuery) -> None:
    sorted_users = sorted(
        data["users"].items(),
        key=lambda x: x[1].get("refs", 0),
        reverse=True,
    )[:10]

    if not sorted_users or all(u[1].get("refs", 0) == 0 for u in sorted_users):
        text = (
            "🏆 <b>ТОП РЕФЕРАЛОВ</b>\n"
            "━━━━━━━━━━━━━━━━━\n"
            "Пока нет рефералов 😔"
        )
        kb = back_keyboard()
    else:
        medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
        lines = ["🏆 <b>ТОП РЕФЕРАЛОВ</b>\n━━━━━━━━━━━━━━━━━"]
        buttons = []
        for i, (uid, info) in enumerate(sorted_users):
            refs = info.get("refs", 0)
            if refs == 0:
                break
            username = info.get("username", f"User_{uid[:6]}")
            medal = medals[i] if i < len(medals) else "•"
            lines.append(f"{medal} <b>{username}</b> — {refs} реф.")
            buttons.append(
                [
                    InlineKeyboardButton(
                        text=f"{medal} {username}",
                        url=f"tg://user?id={uid}",
                    )
                ]
            )
        buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="menu")])
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        text = "\n".join(lines)

    try:
        await call.message.delete()
    except Exception:
        pass
    await bot.send_message(
        chat_id=call.from_user.id,
        text=text,
        reply_markup=kb,
        parse_mode="HTML",
    )
    await call.answer()

# ==================== ЗАПУСК ====================
async def main() -> None:
    logger.info("Запуск бота...")
    me = await bot.get_me()
    logger.info(f"Бот @{me.username} успешно запущен")

    try:
        await bot.set_my_description("💎 GiftsEzz Bot — рулетка, рефералы, вывод ⭐")
    except Exception as e:
        logger.warning(f"Не удалось установить описание: {e}")

    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        raise
```
