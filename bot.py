import asyncio
import json
import logging
import os
import random
from datetime import datetime, timedelta
from typing import Any, Dict

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
SUPPORT_ID = int(os.getenv("SUPPORT_ID", "0"))  # Ваш Telegram ID для заявок
CHANNEL_ID = os.getenv("CHANNEL_ID", "")        # ID или юзернейм канала (напр. @mychannel)
CHAT_ID = os.getenv("CHAT_ID", "")              # ID или юзернейм чата

MIN_WITHDRAW = 10  # Минимальная сумма вывода
REF_BONUS = 0.5    # Бонус за реферала

DATA_FILE = "data.json"

# ==================== РАБОТА С ДАННЫМИ ====================
def load_data() -> Dict[str, Any]:
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка чтения {DATA_FILE}: {e}")
    return {"users": {}, "daily": {}}

def save_data(data: Dict[str, Any]) -> None:
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения {DATA_FILE}: {e}")

data = load_data()

def ensure_user(user_id: str, username: str = "") -> None:
    if "users" not in data:
        data["users"] = {}
    if user_id not in data["users"]:
        data["users"][user_id] = {
            "balance": 0.0,
            "refs": 0,
            "referred_by": None,
            "username": username,
        }
    else:
        if username:
            data["users"][user_id]["username"] = username
    if "daily" not in data:
        data["daily"] = {}
    save_data(data)

# ==================== ИНИЦИАЛИЗАЦИЯ БОТА И ДИСПЕТЧЕРА ====================
if not BOT_TOKEN:
    raise ValueError("Переменная BOT_TOKEN не задана!")

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ==================== СОСТОЯНИЯ FSM ====================
class WithdrawStates(StatesGroup):
    waiting_for_amount = State()

# ==================== КЛАВИАТУРЫ ====================
def sub_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    if CHANNEL_ID:
        buttons.append([InlineKeyboardButton(text="📢 Канал", url=f"https://t.me/{CHANNEL_ID.replace('@', '')}")])
    if CHAT_ID:
        buttons.append([InlineKeyboardButton(text="💬 Чат", url=f"https://t.me/{CHAT_ID.replace('@', '')}")])
    buttons.append([InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_sub")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎰 Рулетка", callback_data="roulette")],
            [
                InlineKeyboardButton(text="👥 Рефералы", callback_data="referrals"),
                InlineKeyboardButton(text="💸 Вывод", callback_data="withdraw"),
            ],
            [InlineKeyboardButton(text="🏆 Топ лидеров", callback_data="leaders")],
        ]
    )

def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="menu")]
        ]
    )

# ==================== ВЕРИФИКАЦИЯ ПОДПИСКИ ====================
async def check_subscription(user_id: int) -> bool:
    for chat in [CHANNEL_ID, CHAT_ID]:
        if not chat:
            continue
        try:
            member = await bot.get_chat_member(chat_id=chat, user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception as e:
            logger.warning(f"Ошибка проверки подписки в {chat}: {e}")
            return False
    return True

async def show_menu(target: types.Message | types.CallbackQuery) -> None:
    user = target.from_user
    user_id = str(user.id)
    ensure_user(user_id, user.username or f"User_{user_id[:6]}")

    balance = data["users"][user_id].get("balance", 0.0)

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
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )
    else:
        await target.answer(
            text,
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )

# ==================== ХЕНДЛЕРЫ ====================
@dp.message(CommandStart())
async def cmd_start(message: types.Message) -> None:
    user_id = str(message.from_user.id)
    ensure_user(user_id, message.from_user.username or f"User_{user_id[:6]}")

    # Проверка реферального кода
    args = message.text.split()
    if len(args) > 1:
        ref_id = args[1]
        if ref_id != user_id and ref_id in data["users"]:
            if data["users"][user_id].get("referred_by") is None:
                data["users"][user_id]["referred_by"] = ref_id
                data["users"][ref_id]["refs"] = data["users"][ref_id].get("refs", 0) + 1
                data["users"][ref_id]["balance"] = (
                    data["users"][ref_id].get("balance", 0.0) + REF_BONUS
                )
                save_data(data)
                try:
                    await bot.send_message(
                        int(ref_id),
                        f"🎉 По вашей ссылке зарегистрировался новый пользователь! Вам начислено +{REF_BONUS} ⭐",
                    )
                except Exception:
                    pass

    if (CHANNEL_ID or CHAT_ID) and not await check_subscription(message.from_user.id):
        await message.answer(
            "⚠️ Для использования бота подпишитесь на наш канал и чат!",
            reply_markup=sub_keyboard(),
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
    weights = [50, 30, 15, 5]
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

    if SUPPORT_ID:
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
