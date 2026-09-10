from aiogram import F, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


TOPUP_OPTIONS = {
    "15": (15, "🧸 Мишка"),
    "25": (25, "🌹 Роза"),
    "100": (100, "💎 Алмаз"),
}

# 🎁 КЕЙСЫ
# Призы кейса за 15 ⭐: 5, 7, 15, 25, 30 ⭐.
CASE_OPTIONS = {
    15: {"prizes": [5, 7, 15, 25, 30]},
    25: {"small": 10, "medium": 28, "big": 100},
    50: {"small": 20, "medium": 55, "big": 150},
    75: {"small": 30, "medium": 83, "big": 250},
    100: {"small": 40, "medium": 110, "big": 350},
    150: {"small": 60, "medium": 165, "big": 500},
    250: {"small": 100, "medium": 275, "big": 850},
    500: {"small": 200, "medium": 550, "big": 1500},
}


def topup_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧸 Мишка — 15 ⭐", callback_data="topup:15")],
        [InlineKeyboardButton(text="🌹 Роза — 25 ⭐", callback_data="topup:25")],
        [InlineKeyboardButton(text="💎 Алмаз — 100 ⭐", callback_data="topup:100")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="menu")],
    ])


def topup_payment_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Открыть @HuskyTelegram", url="https://t.me/HuskyTelegram")],
        [InlineKeyboardButton(text="✅ Я отправил подарок", callback_data="topup_sent")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="topup")],
    ])


def topup_admin_keyboard(request_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Зачислить", callback_data=f"topup_approve:{request_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"topup_reject:{request_id}"),
        ]
    ])


def cases_keyboard():
    prices = list(CASE_OPTIONS.keys())
    buttons = []
    for i in range(0, len(prices), 3):
        buttons.append([
            InlineKeyboardButton(text=f"🎁 {price} ⭐", callback_data=f"case:{price}")
            for price in prices[i:i + 3]
        ])
    buttons.append([InlineKeyboardButton(text="🔙 Назад в меню", callback_data="menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def case_open_keyboard(price: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✨ Открыть кейс", callback_data=f"case_open:{price}")],
        [InlineKeyboardButton(text="🔙 К кейсам", callback_data="cases")],
        [InlineKeyboardButton(text="🏠 В меню", callback_data="menu")],
    ])


async def replace_message(call: types.CallbackQuery, text: str, reply_markup):
    try:
        await call.message.delete()
    except Exception:
        pass
    await call.message.answer(text, parse_mode="HTML", reply_markup=reply_markup)


def register_topup_handlers(dp, bot, db_pool_getter, support_id):
    async def open_topup(message_or_call):
        text = "⭐ <b>Пополнение баланса</b>\n\nВыберите подарок для пополнения:"
        if isinstance(message_or_call, types.CallbackQuery):
            await message_or_call.answer()
            await replace_message(message_or_call, text, topup_menu_keyboard())
        else:
            await message_or_call.answer(text, parse_mode="HTML", reply_markup=topup_menu_keyboard())

    @dp.callback_query(F.data == "topup")
    async def topup_menu(call: types.CallbackQuery):
        await open_topup(call)

    @dp.callback_query(F.data.startswith("topup:"))
    async def create_topup(call: types.CallbackQuery):
        await call.answer()
        key = call.data.split(":", 1)[1]
        if key not in TOPUP_OPTIONS:
            return
        amount, gift_name = TOPUP_OPTIONS[key]
        pool = db_pool_getter()
        async with pool.acquire() as db:
            existing = await db.fetchrow(
                "SELECT id FROM topup_requests WHERE user_id = $1 AND status = 'waiting_admin' ORDER BY id DESC LIMIT 1",
                call.from_user.id,
            )
            if existing:
                await replace_message(call, "⏳ <b>У вас уже есть заявка на проверке.</b>\n\nДождитесь решения администратора.", topup_menu_keyboard())
                return
            row = await db.fetchrow(
                "INSERT INTO topup_requests (user_id, username, full_name, amount, gift_name, status) VALUES ($1, $2, $3, $4, $5, 'pending') RETURNING id",
                call.from_user.id, call.from_user.username or "", call.from_user.full_name or "", amount, gift_name,
            )
        await replace_message(
            call,
            f"🎁 <b>{gift_name}</b> — <b>{amount} ⭐</b>\n\n1. Нажмите кнопку ниже.\n2. Отправьте выбранный подарок пользователю <b>@HuskyTelegram</b>.\n3. Вернитесь в бота и нажмите «Я отправил подарок».\n\n⚠️ Заявка администратору отправится только после нажатия этой кнопки.",
            topup_payment_keyboard(),
        )

    @dp.callback_query(F.data == "topup_sent")
    async def topup_sent(call: types.CallbackQuery):
        pool = db_pool_getter()
        async with pool.acquire() as db:
            row = await db.fetchrow(
                "SELECT * FROM topup_requests WHERE user_id = $1 AND status = 'pending' ORDER BY id DESC LIMIT 1",
                call.from_user.id,
            )
            if not row:
                await call.answer("Сначала выберите подарок", show_alert=True)
                return
            await db.execute("UPDATE topup_requests SET status = 'waiting_admin', updated_at = NOW() WHERE id = $1", row["id"])
        await call.answer("Заявка отправлена администратору", show_alert=True)
        username = f"@{call.from_user.username}" if call.from_user.username else "без username"
        await bot.send_message(
            support_id,
            f"💳 <b>Новая заявка на пополнение</b>\n\nID заявки: <code>{row['id']}</code>\nПользователь: {html_escape(call.from_user.full_name)}\nUsername: {html_escape(username)}\nUser ID: <code>{call.from_user.id}</code>\nПодарок: <b>{html_escape(row['gift_name'])}</b>\nСумма: <b>+{row['amount']} ⭐</b>\n\nПроверьте подарок, отправленный пользователем в @HuskyTelegram.",
            parse_mode="HTML", reply_markup=topup_admin_keyboard(row["id"]),
        )
        await replace_message(call, "⏳ <b>Заявка отправлена на проверку.</b>\n\nАдминистратор проверит подарок у @HuskyTelegram и подтвердит или отклонит заявку.", topup_menu_keyboard())

    @dp.callback_query(F.data.startswith("topup_approve:"))
    async def approve_topup(call: types.CallbackQuery):
        if call.from_user.id != support_id:
            await call.answer("Нет доступа", show_alert=True)
            return
        await call.answer()
        request_id = int(call.data.split(":", 1)[1])
        pool = db_pool_getter()
        async with pool.acquire() as db:
            async with db.transaction():
                row = await db.fetchrow("SELECT * FROM topup_requests WHERE id = $1 FOR UPDATE", request_id)
                if not row or row["status"] == "approved":
                    await call.message.edit_reply_markup(reply_markup=None)
                    return
                if row["status"] == "rejected":
                    return
                await db.execute("UPDATE users SET balance = balance + $1 WHERE user_id = $2", row["amount"], row["user_id"])
                await db.execute("UPDATE topup_requests SET status = 'approved', updated_at = NOW(), processed_by = $1 WHERE id = $2", call.from_user.id, request_id)
        await call.message.edit_text(call.message.text + "\n\n✅ <b>Зачислено.</b>", parse_mode="HTML")
        try:
            await bot.send_message(row["user_id"], f"✅ <b>Пополнение подтверждено!</b>\n\n⭐ На баланс зачислено: <b>+{row['amount']} ⭐</b>", parse_mode="HTML")
        except Exception:
            pass

    @dp.callback_query(F.data.startswith("topup_reject:"))
    async def reject_topup(call: types.CallbackQuery):
        if call.from_user.id != support_id:
            await call.answer("Нет доступа", show_alert=True)
            return
        await call.answer()
        request_id = int(call.data.split(":", 1)[1])
        pool = db_pool_getter()
        async with pool.acquire() as db:
            row = await db.fetchrow("SELECT * FROM topup_requests WHERE id = $1", request_id)
            if not row or row["status"] in ("approved", "rejected"):
                return
            await db.execute("UPDATE topup_requests SET status = 'rejected', updated_at = NOW(), processed_by = $1 WHERE id = $2", call.from_user.id, request_id)
        await call.message.edit_text(call.message.text + "\n\n❌ <b>Отклонено.</b>", parse_mode="HTML")
        try:
            await bot.send_message(row["user_id"], "❌ <b>Заявка на пополнение отклонена.</b>", parse_mode="HTML")
        except Exception:
            pass

    # =====================================================
    # КЕЙСЫ
    # =====================================================

    @dp.callback_query(F.data == "cases")
    async def open_cases(call: types.CallbackQuery):
        text = (
            "🎁 <b>КЕЙСЫ</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Открывай кейсы и выигрывай ⭐\n\n"
            "💎 Чем дороже кейс — тем выше возможный приз.\n"
            "🍀 Удачи!"
        )
        await call.answer()
        await replace_message(call, text, cases_keyboard())

    @dp.callback_query(F.data.startswith("case:") & ~F.data.startswith("case_open:"))
    async def case_preview(call: types.CallbackQuery):
        try:
            price = int(call.data.split(":", 1)[1])
        except (ValueError, IndexError):
            await call.answer("Ошибка кейса", show_alert=True)
            return
        if price not in CASE_OPTIONS:
            await call.answer("Такого кейса нет", show_alert=True)
            return
        data = CASE_OPTIONS[price]
        if price == 15:
            prizes_text = "\n".join(f"⭐ {prize} звёзд" for prize in data["prizes"])
            text = f"🎁 <b>Кейс за 15 ⭐</b>\n━━━━━━━━━━━━━━━━━━━━\n\n<b>Возможные призы:</b>\n{prizes_text}\n\n━━━━━━━━━━━━━━━━━━━━\nНажми кнопку ниже, чтобы открыть кейс."
        else:
            text = (
                f"🎁 <b>Кейс за {price} ⭐</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🪙 Обычный приз: <b>{data['small']} ⭐</b>\n"
                f"✨ Средний приз: <b>{data['medium']} ⭐</b>\n"
                f"💎 Большой приз: <b>{data['big']} ⭐</b>\n\n"
                "━━━━━━━━━━━━━━━━━━━━\nНажми кнопку ниже, чтобы открыть кейс."
            )
        await call.answer()
        await replace_message(call, text, case_open_keyboard(price))

    @dp.callback_query(F.data.startswith("case_open:"))
    async def case_open(call: types.CallbackQuery):
        try:
            price = int(call.data.split(":", 1)[1])
        except (ValueError, IndexError):
            await call.answer("Ошибка кейса", show_alert=True)
            return
        if price not in CASE_OPTIONS:
            await call.answer("Такого кейса нет", show_alert=True)
            return
        pool = db_pool_getter()
        prizes = CASE_OPTIONS[price]
        import random
        if price == 15:
            # Равный шанс на каждый из 5 призов.
            prize = random.choice(prizes["prizes"])
        else:
            roll = random.random()
            if roll < 0.70:
                prize = prizes["small"]
            elif roll < 0.90:
                prize = prizes["medium"]
            else:
                prize = prizes["big"]
        async with pool.acquire() as db:
            async with db.transaction():
                row = await db.fetchrow("SELECT balance FROM users WHERE user_id = $1 FOR UPDATE", call.from_user.id)
                balance = float(row["balance"]) if row else 0.0
                if balance < price:
                    await call.answer(f"❌ Недостаточно ⭐. Нужно {price} ⭐", show_alert=True)
                    return
                await db.execute("UPDATE users SET balance = balance - $1 + $2 WHERE user_id = $3", price, prize, call.from_user.id)
        new_data = await pool.fetchrow("SELECT balance FROM users WHERE user_id = $1", call.from_user.id)
        new_balance = float(new_data["balance"]) if new_data else 0.0
        await call.answer(f"🎉 Вы выиграли {prize} ⭐!", show_alert=True)
        await replace_message(
            call,
            f"🎉 <b>Кейс открыт!</b>\n\n🎁 Кейс: <b>{price} ⭐</b>\n⭐ Ваш приз: <b>{prize} ⭐</b>\n💰 Баланс: <b>{new_balance:.2f} ⭐</b>",
            case_open_keyboard(price),
        )


def html_escape(value: str) -> str:
    import html
    return html.escape(value or "")
