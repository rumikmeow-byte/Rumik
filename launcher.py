import asyncio
import html

import bot as app
from aiogram import F, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# Награда за одного подтверждённого реферала.
app.REF_BONUS = 0.50


def simple_menu_keyboard(user_id: int, support_id=None) -> InlineKeyboardMarkup:
    support_id = app.SUPPORT_ID if support_id is None else support_id
    rows = [
        [InlineKeyboardButton(text="👥 Рефералы", callback_data="referrals")],
        [InlineKeyboardButton(text="💰 Баланс", callback_data="balance")],
        [InlineKeyboardButton(text="🛒 Купить рекламу", callback_data="buy_ads")],
        [InlineKeyboardButton(text="💸 Вывод", callback_data="withdraw")],
    ]
    if user_id == support_id and support_id:
        rows.append([InlineKeyboardButton(text="⚙️ Админ-панель", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# show_menu() в bot.py обращается к main_menu_keyboard через globals() модуля bot.
app.main_menu_keyboard = simple_menu_keyboard


@app.dp.callback_query(F.data == "profile")
async def profile_callback(call: types.CallbackQuery):
    if not await app.require_subscription(call):
        return

    user_id = str(call.from_user.id)
    await app.ensure_user(
        user_id,
        call.from_user.username or f"User_{user_id[:6]}",
        call.from_user.full_name or "",
    )
    data = await app.get_user_data(user_id)
    balance = float(data.get("balance", 0))
    refs = int(data.get("refs", 0))
    username = f"@{call.from_user.username}" if call.from_user.username else "нет username"

    text = (
        "👤 <b>Профиль</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"👤 Имя: <b>{html.escape(call.from_user.full_name)}</b>\n"
        f"🔗 Username: <b>{html.escape(username)}</b>\n"
        f"⭐ Баланс: <b>{balance:.2f} ⭐</b>\n"
        f"👥 Рефералы: <b>{refs}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )

    try:
        await call.message.delete()
    except Exception:
        pass

    await app.bot.send_message(
        call.from_user.id,
        text,
        reply_markup=app.back_keyboard(),
        parse_mode="HTML",
    )
    await call.answer()


@app.dp.callback_query(F.data == "buy_ads")
async def buy_ads_callback(call: types.CallbackQuery):
    if not await app.require_subscription(call):
        return

    try:
        await call.message.delete()
    except Exception:
        pass

    await app.bot.send_message(
        call.from_user.id,
        "🛒 <b>Покупка рекламы</b>\n\n"
        "Для размещения рекламы напишите администратору: @Eclipsed_consult",
        reply_markup=app.back_keyboard(),
        parse_mode="HTML",
    )
    await call.answer()


if __name__ == "__main__":
    try:
        asyncio.run(app.main())
    except (KeyboardInterrupt, SystemExit):
        pass
