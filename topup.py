from aiogram import F, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


TOPUP_OPTIONS = {
    "15": (15, "🧸 Мишка"),
    "25": (25, "🌹 Роза"),
    "100": (100, "💎 Алмаз"),
}


def topup_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧸 Мишка — 15 ⭐", callback_data="topup:15")],
        [InlineKeyboardButton(text="🌹 Роза — 25 ⭐", callback_data="topup:25")],
        [InlineKeyboardButton(text="💎 Алмаз — 100 ⭐", callback_data="topup:100")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="menu")],
    ])


def topup_payment_keyboard(request_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Открыть @HuskyTelegram", url="https://t.me/HuskyTelegram")],
        [InlineKeyboardButton(text="✅ Я отправил подарок", callback_data=f"topup_sent:{request_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="topup")],
    ])


def topup_admin_keyboard(request_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Зачислить", callback_data=f"topup_approve:{request_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"topup_reject:{request_id}"),
        ]
    ])


def register_topup_handlers(dp, bot, db_pool_getter, support_id):
    async def open_topup(message_or_call):
        if isinstance(message_or_call, types.CallbackQuery):
            await message_or_call.answer()
            await message_or_call.message.edit_text(
                "⭐ <b>Пополнение баланса</b>\n\nВыберите подарок для пополнения:",
                parse_mode="HTML",
                reply_markup=topup_menu_keyboard(),
            )
        else:
            await message_or_call.answer(
                "⭐ <b>Пополнение баланса</b>\n\nВыберите подарок для пополнения:",
                parse_mode="HTML",
                reply_markup=topup_menu_keyboard(),
            )

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
            row = await db.fetchrow(
                """
                INSERT INTO topup_requests (user_id, username, full_name, amount, gift_name)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                call.from_user.id,
                call.from_user.username or "",
                call.from_user.full_name or "",
                amount,
                gift_name,
            )

        await call.message.edit_text(
            f"🎁 <b>{gift_name}</b> — <b>{amount} ⭐</b>\n\n"
            "1. Нажмите кнопку ниже.\n"
            "2. Отправьте выбранный подарок пользователю <b>@HuskyTelegram</b>.\n"
            "3. Вернитесь в бота и нажмите «Я отправил подарок».\n\n"
            "После проверки администратором сумма будет зачислена на ваш внутренний баланс.",
            parse_mode="HTML",
            reply_markup=topup_payment_keyboard(row["id"]),
        )

    @dp.callback_query(F.data.startswith("topup_sent:"))
    async def topup_sent(call: types.CallbackQuery):
        await call.answer("Заявка отправлена администратору", show_alert=True)
        request_id = int(call.data.split(":", 1)[1])
        pool = db_pool_getter()
        async with pool.acquire() as db:
            row = await db.fetchrow(
                "SELECT * FROM topup_requests WHERE id = $1 AND user_id = $2",
                request_id, call.from_user.id
            )
            if not row:
                return
            if row["status"] != "pending":
                await call.message.edit_text(
                    "ℹ️ Эта заявка уже обработана.",
                    reply_markup=topup_menu_keyboard(),
                )
                return
            await db.execute(
                "UPDATE topup_requests SET status = 'waiting_admin', updated_at = NOW() WHERE id = $1",
                request_id,
            )

        username = f"@{call.from_user.username}" if call.from_user.username else "без username"
        await bot.send_message(
            support_id,
            f"💳 <b>Новая заявка на пополнение</b>\n\n"
            f"ID заявки: <code>{request_id}</code>\n"
            f"Пользователь: {html_escape(call.from_user.full_name)}\n"
            f"Username: {html_escape(username)}\n"
            f"User ID: <code>{call.from_user.id}</code>\n"
            f"Подарок: <b>{html_escape(row['gift_name'])}</b>\n"
            f"Сумма: <b>+{row['amount']} ⭐</b>",
            parse_mode="HTML",
            reply_markup=topup_admin_keyboard(request_id),
        )
        await call.message.edit_text(
            "⏳ <b>Заявка отправлена на проверку.</b>\n\n"
            "После подтверждения администратором Stars появятся на балансе.",
            parse_mode="HTML",
            reply_markup=topup_menu_keyboard(),
        )

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
                row = await db.fetchrow(
                    "SELECT * FROM topup_requests WHERE id = $1 FOR UPDATE",
                    request_id,
                )
                if not row or row["status"] == "approved":
                    await call.message.edit_reply_markup(reply_markup=None)
                    return
                if row["status"] == "rejected":
                    return
                await db.execute(
                    "UPDATE users SET balance = balance + $1 WHERE user_id = $2",
                    row["amount"], row["user_id"]
                )
                await db.execute(
                    "UPDATE topup_requests SET status = 'approved', updated_at = NOW(), processed_by = $1 WHERE id = $2",
                    call.from_user.id, request_id
                )

        await call.message.edit_text(
            call.message.text + "\n\n✅ <b>Зачислено.</b>",
            parse_mode="HTML",
        )
        try:
            await bot.send_message(
                row["user_id"],
                f"✅ <b>Пополнение подтверждено!</b>\n\n⭐ На баланс зачислено: <b>+{row['amount']} ⭐</b>",
                parse_mode="HTML",
            )
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
            row = await db.fetchrow(
                "SELECT * FROM topup_requests WHERE id = $1",
                request_id,
            )
            if not row or row["status"] in ("approved", "rejected"):
                return
            await db.execute(
                "UPDATE topup_requests SET status = 'rejected', updated_at = NOW(), processed_by = $1 WHERE id = $2",
                call.from_user.id, request_id,
            )

        await call.message.edit_text(
            call.message.text + "\n\n❌ <b>Отклонено.</b>",
            parse_mode="HTML",
        )
        try:
            await bot.send_message(
                row["user_id"],
                "❌ <b>Заявка на пополнение отклонена.</b>",
                parse_mode="HTML",
            )
        except Exception:
            pass


def html_escape(value):
    import html
    return html.escape(str(value or ""))
