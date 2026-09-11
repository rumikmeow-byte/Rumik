from aiogram import F, types, BaseMiddleware
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


TOPUP_OPTIONS = {
    "15": (15, "🧸 Мишка"),
    "25": (25, "🌹 Роза"),
    "100": (100, "💎 Алмаз"),
}

# 🎁 КЕЙСЫ
# Призы кейса за 15 ⭐: 5, 7, 15, 25, 30 ⭐.
CASE_OPTIONS = {
    15: {"prizes": [5, 7, 15, 25, 30], "weights": [96, 1, 1, 1, 1]},
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


class GlobalSubscriptionGuard(BaseMiddleware):
    """Глобально блокирует сообщения/callbacks от отписавшихся пользователей."""

    def __init__(self, bot, db_pool_getter, support_id):
        self.bot = bot
        self.db_pool_getter = db_pool_getter
        self.support_id = support_id

    async def _is_subscribed(self, user_id: int) -> bool:
        pool = self.db_pool_getter()
        if pool is None:
            # Не блокируем пользователя до готовности БД.
            return True

        async with pool.acquire() as db:
            chats = await db.fetch(
                "SELECT chat_id FROM required_chats ORDER BY id"
            )

        if not chats:
            return True

        for row in chats:
            try:
                member = await self.bot.get_chat_member(
                    chat_id=row["chat_id"],
                    user_id=user_id,
                )
                if member.status in ("left", "kicked"):
                    return False
            except Exception:
                return False

        return True

    async def _subscription_keyboard(self):
        pool = self.db_pool_getter()
        buttons = []

        if pool is not None:
            async with pool.acquire() as db:
                chats = await db.fetch(
                    "SELECT chat_id, title FROM required_chats ORDER BY id"
                )

            for row in chats:
                chat_id = str(row["chat_id"])
                if chat_id.startswith("@"):
                    username = chat_id[1:]
                else:
                    username = chat_id

                buttons.append([
                    InlineKeyboardButton(
                        text=f"📢 {row['title']}",
                        url=f"https://t.me/{username}",
                    )
                ])

        buttons.append([
            InlineKeyboardButton(
                text="✅ Проверить подписку",
                callback_data="check_sub",
            )
        ])
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    async def __call__(self, handler, event, data):
        user = getattr(event, "from_user", None)
        if not user:
            return await handler(event, data)

        if self.support_id and user.id == self.support_id:
            return await handler(event, data)

        # /start и /menu должны проходить, чтобы пользователь мог получить
        # экран обязательной подписки и сохранить реферальный параметр.
        if isinstance(event, types.Message):
            text = (event.text or "").strip()
            if text.startswith("/start") or text.startswith("/menu"):
                return await handler(event, data)

        # Без этого пользователь не сможет восстановить доступ.
        if isinstance(event, types.CallbackQuery) and event.data == "check_sub":
            return await handler(event, data)

        try:
            if await self._is_subscribed(user.id):
                return await handler(event, data)
        except Exception:
            pass

        keyboard = await self._subscription_keyboard()
        text = (
            "🔒 <b>ДОСТУП ЗАКРЫТ</b>\n\n"
            "Чтобы пользоваться <b>GiftsMMS</b>, подпишитесь на все "
            "обязательные каналы.\n\n"
            "После подписки нажмите:\n"
            "✅ <b>Проверить подписку</b>"
        )

        if isinstance(event, types.CallbackQuery):
            await event.answer(
                "🔒 Сначала подпишитесь на обязательные каналы.",
                show_alert=True,
            )
            if event.message:
                await event.message.answer(
                    text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
        elif isinstance(event, types.Message):
            await event.answer(
                text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )

        return None


def register_topup_handlers(dp, bot, db_pool_getter, support_id):
    # Глобальный guard ставится на уровне Dispatcher и поэтому защищает
    # не только пополнение/кейсы, но и остальные handlers bot.py, FSM и callbacks.
    dp.message.outer_middleware(
        GlobalSubscriptionGuard(bot, db_pool_getter, support_id)
    )
    dp.callback_query.outer_middleware(
        GlobalSubscriptionGuard(bot, db_pool_getter, support_id)
    )

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
        await call.answer()
        pool = db_pool_getter()
        async with pool.acquire() as db:
            row = await db.fetchrow(
                "SELECT id, amount, gift_name, status FROM topup_requests WHERE user_id = $1 AND status = 'pending' ORDER BY id DESC LIMIT 1",
                call.from_user.id,
            )
        if not row:
            await replace_message(call, "❌ <b>Активная заявка не найдена.</b>", topup_menu_keyboard())
            return
        async with pool.acquire() as db:
            await db.execute(
                "UPDATE topup_requests SET status = 'waiting_admin', updated_at = NOW() WHERE id = $1",
                row["id"],
            )
        try:
            await bot.send_message(
                support_id,
                f"📥 <b>Новая заявка на пополнение</b>\n\n"
                f"👤 <b>User ID:</b> <code>{call.from_user.id}</code>\n"
                f"⭐ <b>Сумма:</b> {row['amount']}\n"
                f"🎁 <b>Подарок:</b> {row['gift_name']}\n"
                f"🧾 <b>Заявка:</b> #{row['id']}",
                parse_mode="HTML",
                reply_markup=topup_admin_keyboard(row["id"]),
            )
        except Exception:
            pass
        await replace_message(call, "⏳ <b>Заявка отправлена администратору.</b>\n\nОжидайте решения.", topup_menu_keyboard())

    @dp.callback_query(F.data.startswith("topup_approve:"))
    async def approve_topup(call: types.CallbackQuery):
        if call.from_user.id != support_id:
            await call.answer("❌ Нет доступа!", show_alert=True)
            return
        request_id = int(call.data.split(":", 1)[1])
        pool = db_pool_getter()
        async with pool.acquire() as db:
            row = await db.fetchrow(
                "SELECT user_id, amount, status FROM topup_requests WHERE id = $1",
                request_id,
            )
            if not row or row["status"] != "waiting_admin":
                await call.answer("Заявка уже обработана.", show_alert=True)
                return
            await db.execute(
                "UPDATE users SET balance = balance + $1 WHERE user_id = $2",
                row["amount"], row["user_id"],
            )
            await db.execute(
                "UPDATE topup_requests SET status = 'approved', processed_by = $1, updated_at = NOW() WHERE id = $2",
                support_id, request_id,
            )
        try:
            await bot.send_message(row["user_id"], f"✅ <b>Пополнение подтверждено!</b>\n\n⭐ Начислено: <b>+{row['amount']} ⭐</b>", parse_mode="HTML")
        except Exception:
            pass
        await call.message.edit_text("✅ <b>Заявка зачислена.</b>", parse_mode="HTML")
        await call.answer("Зачислено!")

    @dp.callback_query(F.data.startswith("topup_reject:"))
    async def reject_topup(call: types.CallbackQuery):
        if call.from_user.id != support_id:
            await call.answer("❌ Нет доступа!", show_alert=True)
            return
        request_id = int(call.data.split(":", 1)[1])
        pool = db_pool_getter()
        async with pool.acquire() as db:
            row = await db.fetchrow(
                "SELECT user_id, status FROM topup_requests WHERE id = $1",
                request_id,
            )
            if not row or row["status"] != "waiting_admin":
                await call.answer("Заявка уже обработана.", show_alert=True)
                return
            await db.execute(
                "UPDATE topup_requests SET status = 'rejected', processed_by = $1, updated_at = NOW() WHERE id = $2",
                support_id, request_id,
            )
        try:
            await bot.send_message(row["user_id"], "❌ <b>Заявка на пополнение отклонена.</b>", parse_mode="HTML")
        except Exception:
            pass
        await call.message.edit_text("❌ <b>Заявка отклонена.</b>", parse_mode="HTML")
        await call.answer("Отклонено")

    @dp.callback_query(F.data == "cases")
    async def cases_menu(call: types.CallbackQuery):
        await call.answer()
        await replace_message(call, "🎁 <b>Кейсы</b>\n\nВыберите кейс:", cases_keyboard())

    @dp.callback_query(F.data.startswith("case:"))
    async def case_preview(call: types.CallbackQuery):
        await call.answer()
        price = int(call.data.split(":", 1)[1])
        if price not in CASE_OPTIONS:
            return
        await replace_message(call, f"🎁 <b>Кейс за {price} ⭐</b>\n\nНажмите «Открыть кейс».", case_open_keyboard(price))

    @dp.callback_query(F.data.startswith("case_open:"))
    async def case_open(call: types.CallbackQuery):
        import random
        await call.answer("🎁 Открываем...")
        price = int(call.data.split(":", 1)[1])
        options = CASE_OPTIONS.get(price)
        if not options:
            return
        pool = db_pool_getter()
        async with pool.acquire() as db:
            row = await db.fetchrow("SELECT balance FROM users WHERE user_id = $1 FOR UPDATE", call.from_user.id)
            balance = float(row["balance"]) if row else 0
            if balance < price:
                await replace_message(call, f"❌ <b>Недостаточно ⭐</b>\n\nНужно: {price} ⭐\nБаланс: {balance:.2f} ⭐", cases_keyboard())
                return
            if price == 15:
                prize = random.choices(options["prizes"], weights=options["weights"])[0]
            else:
                prize = random.choice(list(options.values()))
            await db.execute("UPDATE users SET balance = balance - $1 + $2 WHERE user_id = $3", price, prize, call.from_user.id)
        await replace_message(call, f"🎉 <b>Кейс открыт!</b>\n\n⭐ Вы выиграли: <b>+{prize} ⭐</b>\n💰 Баланс обновлён.", cases_keyboard())

