import asyncio
import logging
import os
from decimal import Decimal, InvalidOperation

import asyncpg
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

BOT_TOKEN = os.environ["BOT_TOKEN"]
DATABASE_URL = os.environ["DATABASE_URL"]
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
CHANNEL = "@Xoylis"
ADMIN_USERNAME = "@Dlr0r04"
REF_BONUS = Decimal("0.50")
MIN_WITHDRAW = Decimal("15")

bot = Bot(BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
pool = None

class Withdraw(StatesGroup):
    amount = State()

def fmt(x):
    return f"{Decimal(str(x)):.2f}".rstrip("0").rstrip(".")

def menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Вывод", callback_data="withdraw")],
        [InlineKeyboardButton(text="👥 Приглашать", callback_data="refs")],
    ])

def subscribe_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Подписаться на @Xoylis", url="https://t.me/Xoylis")],
        [InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check")],
    ])

def back():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="menu")]])

async def init_db():
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    async with pool.acquire() as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS referral_users (
                user_id BIGINT PRIMARY KEY,
                username TEXT NOT NULL DEFAULT '',
                full_name TEXT NOT NULL DEFAULT '',
                balance NUMERIC(12,2) NOT NULL DEFAULT 0,
                referrals INTEGER NOT NULL DEFAULT 0,
                referred_by BIGINT,
                referral_paid BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS referral_withdrawals (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                username TEXT NOT NULL DEFAULT '',
                amount NUMERIC(12,2) NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

async def subscribed(user_id):
    try:
        member = await bot.get_chat_member(CHANNEL, user_id)
        return member.status not in {"left", "kicked"}
    except Exception as e:
        log.warning("subscription check: %s", e)
        return False

async def save_user(user: types.User, referrer=None):
    async with pool.acquire() as db:
        exists = await db.fetchval("SELECT 1 FROM referral_users WHERE user_id=$1", user.id)
        if exists:
            await db.execute("UPDATE referral_users SET username=$2, full_name=$3 WHERE user_id=$1", user.id, user.username or "", user.full_name or "")
            return
        if referrer == user.id:
            referrer = None
        await db.execute("INSERT INTO referral_users(user_id,username,full_name,referred_by) VALUES($1,$2,$3,$4)", user.id, user.username or "", user.full_name or "", referrer)

async def credit_referral(user_id):
    async with pool.acquire() as db:
        async with db.transaction():
            row = await db.fetchrow("SELECT referred_by, referral_paid FROM referral_users WHERE user_id=$1 FOR UPDATE", user_id)
            if not row or not row["referred_by"] or row["referral_paid"]:
                return
            referrer = row["referred_by"]
            await db.execute("UPDATE referral_users SET balance=balance+$1, referrals=referrals+1 WHERE user_id=$2", REF_BONUS, referrer)
            await db.execute("UPDATE referral_users SET referral_paid=TRUE WHERE user_id=$1", user_id)
    try:
        await bot.send_message(referrer, f"🎉 Новый реферал! Вам начислено +{fmt(REF_BONUS)} ⭐")
    except Exception:
        pass

async def show_menu(target):
    row = await pool.fetchrow("SELECT balance FROM referral_users WHERE user_id=$1", target.from_user.id)
    balance = row["balance"] if row else Decimal("0")
    await target.answer(f"⭐ <b>Реферальный бот</b>\n\nБаланс: <b>{fmt(balance)} ⭐</b>\n\n1 реферал = <b>0.50 ⭐</b>", parse_mode="HTML", reply_markup=menu())

@dp.message(CommandStart())
async def start(message: types.Message):
    ref = None
    if message.text and " " in message.text:
        payload = message.text.split(" ", 1)[1]
        if payload.startswith("ref_"):
            try: ref = int(payload[4:])
            except ValueError: pass
    await save_user(message.from_user, ref)
    if not await subscribed(message.from_user.id):
        await message.answer("🔒 <b>Чтобы пользоваться ботом, нужно подписаться на @Xoylis.</b>", parse_mode="HTML", reply_markup=subscribe_menu())
        return
    await credit_referral(message.from_user.id)
    await show_menu(message)

@dp.callback_query(F.data == "check")
async def check(call: types.CallbackQuery):
    if not await subscribed(call.from_user.id):
        await call.answer("❌ Подписка не найдена", show_alert=True)
        return
    await credit_referral(call.from_user.id)
    await call.answer("✅ Подписка подтверждена")
    await call.message.edit_text("✅ <b>Подписка подтверждена!</b>", parse_mode="HTML", reply_markup=menu())

@dp.callback_query(F.data == "menu")
async def main_menu(call: types.CallbackQuery):
    if not await subscribed(call.from_user.id):
        await call.message.edit_text("🔒 Сначала подпишитесь на @Xoylis.", reply_markup=subscribe_menu())
        return
    await call.answer()
    await show_menu(call)

@dp.callback_query(F.data == "refs")
async def refs(call: types.CallbackQuery):
    if not await subscribed(call.from_user.id):
        await call.message.edit_text("🔒 Сначала подпишитесь на @Xoylis.", reply_markup=subscribe_menu())
        return
    await call.answer()
    await credit_referral(call.from_user.id)
    row = await pool.fetchrow("SELECT referrals FROM referral_users WHERE user_id=$1", call.from_user.id)
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start=ref_{call.from_user.id}"
    await call.message.edit_text(f"👥 <b>Приглашать</b>\n\nРефералов: <b>{row['referrals']}</b>\nНачисление: <b>0.50 ⭐</b> за каждого\n\n🔗 <code>{link}</code>", parse_mode="HTML", reply_markup=back())

@dp.callback_query(F.data == "withdraw")
async def withdraw(call: types.CallbackQuery, state: FSMContext):
    if not await subscribed(call.from_user.id):
        await call.message.edit_text("🔒 Сначала подпишитесь на @Xoylis.", reply_markup=subscribe_menu())
        return
    await call.answer()
    row = await pool.fetchrow("SELECT balance FROM referral_users WHERE user_id=$1", call.from_user.id)
    await state.set_state(Withdraw.amount)
    await call.message.edit_text(f"💰 <b>Вывод</b>\n\nБаланс: <b>{fmt(row['balance'])} ⭐</b>\nМинимум: <b>15 ⭐</b>\n\nВведите сумму:", parse_mode="HTML", reply_markup=back())

@dp.message(Withdraw.amount)
async def withdraw_amount(message: types.Message, state: FSMContext):
    try: amount = Decimal((message.text or "").replace(",", ".").strip())
    except InvalidOperation:
        await message.answer("❌ Введите число, например 15")
        return
    if amount < MIN_WITHDRAW:
        await message.answer("❌ Минимальный вывод — 15 ⭐")
        return
    async with pool.acquire() as db:
        async with db.transaction():
            row = await db.fetchrow("SELECT balance FROM referral_users WHERE user_id=$1 FOR UPDATE", message.from_user.id)
            if not row or row["balance"] < amount:
                await message.answer("❌ Недостаточно звёзд.")
                return
            await db.execute("UPDATE referral_users SET balance=balance-$1 WHERE user_id=$2", amount, message.from_user.id)
            req = await db.fetchrow("INSERT INTO referral_withdrawals(user_id,username,amount) VALUES($1,$2,$3) RETURNING id", message.from_user.id, message.from_user.username or "", amount)
    await state.clear()
    text = f"💸 <b>Заявка на вывод #{req['id']}</b>\n\n👤 {message.from_user.full_name}\n🆔 <code>{message.from_user.id}</code>\n🔗 @{message.from_user.username or 'нет'}\n⭐ Сумма: <b>{fmt(amount)} ⭐</b>"
    if ADMIN_ID:
        try: await bot.send_message(ADMIN_ID, text, parse_mode="HTML")
        except Exception as e: log.error("admin notification: %s", e)
    await message.answer(f"✅ Заявка #{req['id']} создана. Она передана администратору {ADMIN_USERNAME}.", reply_markup=menu())

async def health(request):
    return web.Response(text="OK")

async def main():
    await init_db()
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", "10000"))).start()
    try:
        await dp.start_polling(bot)
    finally:
        await runner.cleanup()
        await pool.close()
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
