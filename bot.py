import asyncio
import random
import json
import os
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = "@eclipsedlf"
CHAT_ID = "@GiftsEzzChat"
SUPPORT_ID = 8644223884  # Ваш ID

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

DATA_FILE = "data.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"users": {}, "refers": {}, "daily": {}}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"users": {}, "refers": {}, "daily": {}}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

data = load_data()

class WithdrawStates(StatesGroup):
    waiting_for_amount = State()

# ========== КЛАВИАТУРЫ ==========
def main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎰 РУЛЕТКА", callback_data="roulette")],
        [
            InlineKeyboardButton(text="👥 Рефералы", callback_data="referrals"),
            InlineKeyboardButton(text="⭐ Вывод", callback_data="withdraw")
        ],
        [
            InlineKeyboardButton(text="🏆 Лидеры", callback_data="leaders"),
            InlineKeyboardButton(text="🆘 Поддержка", url="https://t.me/Eclipsed_consult"),
            InlineKeyboardButton(text="📢 Канал", url="https://t.me/eclipsedlf")
        ]
    ])

def back_button():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="menu")]
    ])

# ========== ПРОВЕРКА ПОДПИСКИ ==========
async def check_sub(user_id):
    try:
        member_ch = await bot.get_chat_member(CHANNEL_ID, user_id)
        member_chat = await bot.get_chat_member(CHAT_ID, user_id)
        return member_ch.status in ["member", "administrator", "creator"] and \
               member_chat.status in ["member", "administrator", "creator"]
    except:
        return False

# ========== СТАРТ ==========
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    args = message.text.split()
    ref_id = args[1] if len(args) > 1 else None

    user_id = str(message.from_user.id)
    username = message.from_user.username or f"User_{user_id[:6]}"
    
    if user_id not in data["users"]:
        data["users"][user_id] = {
            "balance": 0.0,
            "refs": 0,
            "username": username
        }
        data["refers"][user_id] = []
        data["daily"][user_id] = None
        save_data(data)
    else:
        data["users"][user_id]["username"] = username
        save_data(data)

    if ref_id and ref_id != user_id and ref_id in data["users"]:
        if user_id not in data["refers"].get(ref_id, []):
            data["users"][ref_id]["balance"] += 0.85
            data["users"][ref_id]["refs"] += 1
            data["refers"][ref_id].append(user_id)
            save_data(data)
            await bot.send_message(ref_id, f"🎉 Новый реферал! +0.85 ⭐")

    if not await check_sub(user_id):
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 ПОДПИСАТЬСЯ НА КАНАЛ", url="https://t.me/eclipsedlf")],
            [InlineKeyboardButton(text="💬 ПОДПИСАТЬСЯ НА ЧАТ", url="https://t.me/GiftsEzzChat")],
            [InlineKeyboardButton(text="✅ Я ПОДПИСАЛСЯ!", callback_data="check_sub")]
        ])
        await message.answer(
            "🌸 <b>ДОБРО ПОЖАЛОВАТЬ!</b>\n\n"
            "❕ Подпишитесь на канал и чат, чтобы получить доступ:\n"
            "• 🎰 Ежедневная рулетка\n"
            "• 👥 Рефералы (+0.85 ⭐)\n"
            "• 💰 Вывод от 15 ⭐\n"
            "• 🏆 Топ лидеров\n\n"
            "⚠️ <i>Без подписки бот не работает!</i>",
            reply_markup=kb,
            parse_mode="HTML"
        )
        return

    await show_menu(message)

@dp.callback_query(F.data == "check_sub")
async def check_sub_cb(call: types.CallbackQuery):
    if await check_sub(call.from_user.id):
        await call.message.delete()
        await show_menu(call.message)
    else:
        await call.answer("❌ Вы ещё не подписались!", show_alert=True)

# ========== ГЛАВНОЕ МЕНЮ С КАРТИНКОЙ ==========
async def show_menu(msg):
    user_id = str(msg.from_user.id)
    balance = data["users"].get(user_id, {}).get("balance", 0)
    profile_text = (
        f"Добро пожаловать в GiftsEzz !\n"
        f"🌟 <b>Ваш профиль</b>\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"⭐ Баланс: <code>{balance:.2f}</code>\n"
        f"👥 Рефералов: <code>{data['users'].get(user_id, {}).get('refs', 0)}</code>\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"💎 GiftsEzz <3"
    )
    
    photo_url = "https://i.ibb.co/q8K47k3/9275.png"
    
    try:
        if isinstance(msg, types.CallbackQuery):
            await msg.message.delete()
            await bot.send_photo(
                chat_id=msg.from_user.id,
                photo=photo_url,
                caption=profile_text,
                reply_markup=main_keyboard(),
                parse_mode="HTML"
            )
        else:
            await msg.answer_photo(
                photo=photo_url,
                caption=profile_text,
                reply_markup=main_keyboard(),
                parse_mode="HTML"
            )
    except Exception:
        if isinstance(msg, types.CallbackQuery):
            await bot.send_message(
                chat_id=msg.from_user.id,
                text=profile_text,
                reply_markup=main_keyboard(),
                parse_mode="HTML"
            )
        else:
            await msg.answer(
                profile_text,
                reply_markup=main_keyboard(),
                parse_mode="HTML"
            )

@dp.callback_query(F.data == "menu")
async def menu_cb(call: types.CallbackQuery):
    await call.message.delete()
    await show_menu(call.message)

# ========== РУЛЕТКА ==========
@dp.callback_query(F.data == "roulette")
async def roulette_cmd(call: types.CallbackQuery):
    user_id = str(call.from_user.id)
    last = data["daily"].get(user_id)
    if last and datetime.fromisoformat(last) > datetime.now() - timedelta(days=1):
        await call.answer("⏳ Ты уже крутил сегодня! Жди завтра.", show_alert=True)
        return

    prizes = [0.5, 5, 6, 10]
    weights = [50, 30, 15, 10]
    win = random.choices(prizes, weights=weights)[0]

    data["users"][user_id]["balance"] += win
    data["daily"][user_id] = datetime.now().isoformat()
    save_data(data)

    await call.message.edit_text(
        f"🎰 <b>Результат рулетки</b>\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"Вы выиграли: <code>{win} ⭐</code>\n"
        f"Новый баланс: <code>{data['users'][user_id]['balance']:.2f} ⭐</code>\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"<i>Приходи завтра снова!</i>",
        reply_markup=back_button(),
        parse_mode="HTML"
    )

# ========== РЕФЕРАЛЫ ==========
@dp.callback_query(F.data == "referrals")
async def referrals_cmd(call: types.CallbackQuery):
    user_id = str(call.from_user.id)
    ref_link = f"https://t.me/{bot.username}?start={user_id}"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Копировать ссылку", callback_data=f"copy_{user_id}")],
        [InlineKeyboardButton(text="📤 Отправить в чат", switch_inline_query=ref_link)],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="menu")]
    ])

    await call.message.edit_text(
        f"👥 <b>Реферальная система</b>\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"Твоя ссылка:\n<code>{ref_link}</code>\n\n"
        f"За каждого приглашённого ты получаешь <b>0.85 ⭐</b>\n"
        f"Всего рефералов: <code>{data['users'].get(user_id, {}).get('refs', 0)}</code>",
        reply_markup=kb,
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("copy_"))
async def copy_ref(call: types.CallbackQuery):
    await call.answer("🔗 Ссылка скопирована в буфер!", show_alert=True)

# ========== ВЫВОД ==========
@dp.callback_query(F.data == "withdraw")
async def withdraw_start(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        "💸 <b>Вывод звёзд</b>\n"
        "━━━━━━━━━━━━━━━━━\n"
        "Минимальная сумма: <b>15 ⭐</b>\n"
        "Введите количество звёзд для вывода:",
        reply_markup=back_button(),
        parse_mode="HTML"
    )
    await state.set_state(WithdrawStates.waiting_for_amount)

@dp.message(WithdrawStates.waiting_for_amount)
async def withdraw_process(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    try:
        amount = float(message.text)
        if amount < 15:
            await message.answer("❌ Минимальный вывод — 15 ⭐")
            return
        if data["users"][user_id]["balance"] < amount:
            await message.answer("❌ Недостаточно средств!")
            return

        data["users"][user_id]["balance"] -= amount
        save_data(data)

        await bot.send_message(
            SUPPORT_ID,
            f"💰 <b>Заявка на вывод</b>\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"👤 Пользователь: {message.from_user.full_name}\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"⭐ Сумма: <code>{amount:.2f}</code>\n"
            f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            parse_mode="HTML"
        )

        await message.answer(
            f"✅ Заявка на <code>{amount:.2f} ⭐</code> отправлена!\nОжидайте обработки.",
            reply_markup=back_button(),
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer("❌ Введите число!")
    await state.clear()

# ========== ЛИДЕРЫ (ТОП-3) ==========
@dp.callback_query(F.data == "leaders")
async def leaders_cmd(call: types.CallbackQuery):
    sorted_users = sorted(data["users"].items(), key=lambda x: x[1]["refs"], reverse=True)[:3]
    
    if not sorted_users:
        await call.message.edit_text(
            "🏆 <b>ТОП РЕФЕРАЛОВ</b>\n━━━━━━━━━━━━━━━━━\nПока нет рефералов 😔",
            reply_markup=back_button(),
            parse_mode="HTML"
        )
        return
    
    medals = ["🥇", "🥈", "🥉"]
    lines = ["🏆 <b>ТОП РЕФЕРАЛОВ</b>\n━━━━━━━━━━━━━━━━━"]
    keyboard = []
    
    for i, (uid, info) in enumerate(sorted_users):
        refs = info["refs"]
        username = info.get("username", f"User_{uid[:6]}")
        lines.append(f"{medals[i]} <b>{username}</b> — {refs} реф.")
        keyboard.append([InlineKeyboardButton(text=f"{medals[i]} {username}", url=f"tg://user?id={uid}")])
    
    keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="menu")])
    kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await call.message.edit_text(
        "\n".join(lines),
        reply_markup=kb,
        parse_mode="HTML"
    )

# ========== ЗАПУСК ==========
async def main():
    bot_info = await bot.get_me()
    bot.username = bot_info.username
    
    await bot.set_my_description("💎 GiftsEzz Bot")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
