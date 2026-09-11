"""GiftsMMS premium UI extension loaded automatically by Python."""

import functools
import html
import os
import sys
from urllib.parse import quote


def _install_giftsmms_ui(dp):
    from aiogram import types, F
    from aiogram.types import (
        InlineKeyboardButton,
        InlineKeyboardMarkup,
        ReplyKeyboardMarkup,
        KeyboardButton,
    )

    main = sys.modules.get("__main__")
    if main is None or getattr(main, "_GIFTSMMS_UI_INSTALLED", False):
        return

    main._GIFTSMMS_UI_INSTALLED = True
    bot = main.bot

    def bottom_keyboard():
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🎁 Кейсы"), KeyboardButton(text="👥 Рефералы")],
                [KeyboardButton(text="💰 Баланс"), KeyboardButton(text="💳 Пополнить баланс")],
                [KeyboardButton(text="📢 Канал"), KeyboardButton(text="🆘 Поддержка")],
                [KeyboardButton(text="📣 Купить рекламу")],
            ],
            resize_keyboard=True,
            is_persistent=True,
            input_field_placeholder="✨ Выберите раздел…",
        )

    def home_inline():
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🎁 Открыть кейсы", callback_data="ui_cases"),
                InlineKeyboardButton(text="💰 Баланс", callback_data="ui_balance"),
            ],
            [
                InlineKeyboardButton(text="👥 Рефералы", callback_data="ui_refs"),
                InlineKeyboardButton(text="💳 Пополнить", callback_data="ui_topup"),
            ],
            [
                InlineKeyboardButton(text="📢 Канал", url="https://t.me/eclipsedlf"),
                InlineKeyboardButton(text="🆘 Поддержка", url="https://t.me/Eclipsed_consult"),
            ],
        ])

    async def profile_text(user):
        data = await main.get_user_data(str(user.id)) or {}
        balance = float(data.get("balance", 0) or 0)
        refs = int(data.get("refs", 0) or 0)
        username = f"@{html.escape(user.username)}" if user.username else "не указан"
        return (
            "👤 <b>ТВОЙ ПРОФИЛЬ</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"🪪 ID: <code>{user.id}</code>\n"
            f"💬 Username: {username}\n"
            f"⭐ Баланс: <b>{balance:.2f} ⭐</b>\n"
            f"👥 Рефералов: <b>{refs}</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "✨ <i>Приглашай друзей и увеличивай баланс!</i>"
        )

    async def show_home(chat_id, user):
        await main.credit_referral_if_needed(user.id)
        name = html.escape(user.first_name or "друг")
        text = (
            f"✨ <b>ПРИВЕТ, {name.upper()}!</b>\n\n"
            "🎁 <b>GiftsMMS</b> — твой мир подарков, кейсов и звёзд.\n\n"
            "💎 Открывай кейсы\n"
            "👥 Приглашай друзей\n"
            "⭐ Получай и трать звёзды\n"
            "🚀 Пользуйся всеми возможностями бота\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "👇 <b>Выбирай, что сделать:</b>"
        )
        try:
            await bot.send_message(chat_id, text, reply_markup=home_inline(), parse_mode="HTML")
        except Exception:
            await bot.send_message(chat_id, text, parse_mode="HTML")
        await bot.send_message(chat_id, "✨ <b>Быстрое меню</b>", reply_markup=bottom_keyboard(), parse_mode="HTML")

    async def custom_show_menu(target):
        user = target.from_user
        user_id = str(user.id)
        await main.ensure_user(user_id, user.username or f"User_{user_id[:6]}", user.full_name or "")

        if user.id != main.SUPPORT_ID and not await main.check_subscription(user.id):
            if isinstance(target, types.CallbackQuery):
                await target.answer("🔒 Сначала подпишитесь на канал и чат", show_alert=True)
            await bot.send_message(
                user.id,
                "🔒 <b>ДОСТУП ПОКА ЗАКРЫТ</b>\n\n"
                "Чтобы открыть GiftsMMS, нужно:\n\n"
                "📢 подписаться на канал\n"
                "💬 вступить в чат\n\n"
                "После этого нажмите кнопку проверки 👇",
                reply_markup=await main.subscription_keyboard(),
                parse_mode="HTML",
            )
            return

        if isinstance(target, types.CallbackQuery):
            try:
                await target.message.delete()
            except Exception:
                pass
            await target.answer()
            chat_id = user.id
        else:
            chat_id = target.chat.id
        await show_home(chat_id, user)

    main.show_menu = custom_show_menu
    main.main_menu_keyboard = bottom_keyboard

    @dp.message(F.text == "📢 Канал")
    async def reply_channel(message: types.Message):
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Открыть канал", url="https://t.me/eclipsedlf")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="ui_home")],
        ])
        await message.answer("📢 <b>Наш канал</b>\n\nНовости, обновления и важные объявления.", reply_markup=kb, parse_mode="HTML")

    @dp.message(F.text == "🆘 Поддержка")
    async def reply_support(message: types.Message):
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🆘 Написать в поддержку", url="https://t.me/Eclipsed_consult")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="ui_home")],
        ])
        await message.answer("🆘 <b>Поддержка</b>\n\nЕсли что-то не работает — напишите нам.", reply_markup=kb, parse_mode="HTML")

    @dp.message(F.text == "📣 Купить рекламу")
    async def reply_ads(message: types.Message):
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📣 Заказать рекламу", url="https://t.me/huskytelegram")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="ui_home")],
        ])
        await message.answer("📣 <b>Реклама в GiftsMMS</b>\n\nСвяжитесь с менеджером для размещения рекламы.", reply_markup=kb, parse_mode="HTML")

    @dp.message(F.text == "💰 Баланс")
    async def reply_balance(message: types.Message):
        await message.answer(await profile_text(message.from_user), reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Пополнить баланс", callback_data="ui_topup")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="ui_home")],
        ]), parse_mode="HTML")

    @dp.message(F.text == "💳 Пополнить баланс")
    async def reply_topup(message: types.Message):
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🧸 Мишка · 15 ⭐", callback_data="topup:15")],
            [InlineKeyboardButton(text="🌹 Роза · 25 ⭐", callback_data="topup:25")],
            [InlineKeyboardButton(text="💎 Алмаз · 100 ⭐", callback_data="topup:100")],
            [InlineKeyboardButton(text="🏠 Назад", callback_data="ui_home")],
        ])
        await message.answer(
            "💳 <b>ПОПОЛНЕНИЕ БАЛАНСА</b>\n\n"
            "Выберите подарок и сумму ⭐\n\n"
            "🔐 Безопасная обработка\n⚡ Быстрое зачисление",
            reply_markup=kb, parse_mode="HTML"
        )

    @dp.message(F.text == "🎁 Кейсы")
    async def reply_cases(message: types.Message):
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎁 15 ⭐", callback_data="case:15"), InlineKeyboardButton(text="🎁 25 ⭐", callback_data="case:25"), InlineKeyboardButton(text="🎁 50 ⭐", callback_data="case:50")],
            [InlineKeyboardButton(text="🎁 75 ⭐", callback_data="case:75"), InlineKeyboardButton(text="🎁 100 ⭐", callback_data="case:100"), InlineKeyboardButton(text="🎁 150 ⭐", callback_data="case:150")],
            [InlineKeyboardButton(text="🎁 250 ⭐", callback_data="case:250"), InlineKeyboardButton(text="🎁 500 ⭐", callback_data="case:500")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="ui_home")],
        ])
        await message.answer(
            "🎁 <b>ВЫБЕРИ КЕЙС</b>\n\n"
            "Открывай кейсы за ⭐ и испытай удачу!\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💡 Чем больше кейс — тем больше потенциальная награда.",
            reply_markup=kb, parse_mode="HTML"
        )

    @dp.message(F.text == "👥 Рефералы")
    async def reply_referrals(message: types.Message):
        user_id = str(message.from_user.id)
        await main.ensure_user(user_id, message.from_user.username or f"User_{user_id[:6]}", message.from_user.full_name or "")
        me = await bot.get_me()
        ref_link = f"https://t.me/{me.username}?start=ref_{user_id}"
        data = await main.get_user_data(user_id) or {}
        refs = int(data.get("refs", 0) or 0)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📨 ПРИГЛАСИТЬ ДРУГА", url="https://t.me/share/url?url=" + quote(ref_link, safe="") + "&text=" + quote("Приглашай друзей и зарабатывай звёзды в GiftsMMS!", safe=""))],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="ui_home")],
        ])
        await message.answer(
            "👥 <b>РЕФЕРАЛЬНАЯ СИСТЕМА</b>\n\n"
            "Приглашай друзей и получай звёзды за каждого!\n\n"
            f"⭐ Награда: <b>+{main.REF_BONUS:.2f} ⭐</b>\n"
            f"👥 Приглашено: <b>{refs}</b>\n\n"
            f"🔗 Твоя ссылка:\n<code>{html.escape(ref_link)}</code>",
            reply_markup=kb, parse_mode="HTML"
        )

    @dp.callback_query(F.data == "ui_home")
    async def ui_home(call: types.CallbackQuery):
        await call.answer()
        try:
            await call.message.delete()
        except Exception:
            pass
        await show_home(call.from_user.id, call.from_user)

    @dp.callback_query(F.data == "ui_balance")
    async def ui_balance(call: types.CallbackQuery):
        await call.answer()
        await call.message.edit_text(await profile_text(call.from_user), reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Пополнить", callback_data="ui_topup")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="ui_home")],
        ]), parse_mode="HTML")

    @dp.callback_query(F.data == "ui_refs")
    async def ui_refs(call: types.CallbackQuery):
        await call.answer()
        me = await bot.get_me()
        uid = str(call.from_user.id)
        ref_link = f"https://t.me/{me.username}?start=ref_{uid}"
        data = await main.get_user_data(uid) or {}
        refs = int(data.get("refs", 0) or 0)
        await call.message.edit_text(
            "👥 <b>РЕФЕРАЛЫ</b>\n\n"
            f"👥 Приглашено: <b>{refs}</b>\n"
            f"⭐ За друга: <b>+{main.REF_BONUS:.2f} ⭐</b>\n\n"
            f"🔗 <code>{html.escape(ref_link)}</code>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📨 Пригласить друга", url="https://t.me/share/url?url=" + quote(ref_link, safe=""))],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="ui_home")],
            ]), parse_mode="HTML"
        )

    @dp.callback_query(F.data == "ui_topup")
    async def ui_topup(call: types.CallbackQuery):
        await call.answer()
        await call.message.edit_text(
            "💳 <b>ПОПОЛНЕНИЕ БАЛАНСА</b>\n\nВыберите вариант ⭐",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🧸 15 ⭐", callback_data="topup:15"), InlineKeyboardButton(text="🌹 25 ⭐", callback_data="topup:25")],
                [InlineKeyboardButton(text="💎 100 ⭐", callback_data="topup:100")],
                [InlineKeyboardButton(text="🏠 Назад", callback_data="ui_home")],
            ]), parse_mode="HTML"
        )

    @dp.callback_query(F.data == "ui_cases")
    async def ui_cases(call: types.CallbackQuery):
        await call.answer()
        await call.message.edit_text(
            "🎁 <b>КЕЙСЫ</b>\n\nВыбери кейс и попробуй получить награду ⭐",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎁 15 ⭐", callback_data="case:15"), InlineKeyboardButton(text="🎁 25 ⭐", callback_data="case:25"), InlineKeyboardButton(text="🎁 50 ⭐", callback_data="case:50")],
                [InlineKeyboardButton(text="🎁 75 ⭐", callback_data="case:75"), InlineKeyboardButton(text="🎁 100 ⭐", callback_data="case:100"), InlineKeyboardButton(text="🎁 150 ⭐", callback_data="case:150")],
                [InlineKeyboardButton(text="🎁 250 ⭐", callback_data="case:250"), InlineKeyboardButton(text="🎁 500 ⭐", callback_data="case:500")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="ui_home")],
            ]), parse_mode="HTML"
        )

    async def patched_cmd_start(message: types.Message):
        user_id = str(message.from_user.id)
        await main.ensure_user(user_id, message.from_user.username or f"User_{user_id[:6]}", message.from_user.full_name or "")
        args = (message.text or "").split()
        if len(args) > 1:
            ref_id = args[1]
            if ref_id.startswith("ref_"):
                ref_id = ref_id[4:]
            if ref_id != user_id and ref_id.isdigit():
                async with main.db_pool.acquire() as db:
                    async with db.transaction():
                        user_row = await db.fetchrow("SELECT referred_by FROM users WHERE user_id = $1 FOR UPDATE", int(user_id))
                        ref_exists = await db.fetchrow("SELECT user_id FROM users WHERE user_id = $1", int(ref_id))
                        if ref_exists and user_row and user_row["referred_by"] is None:
                            await db.execute("UPDATE users SET referred_by = $1 WHERE user_id = $2 AND referred_by IS NULL", int(ref_id), int(user_id))
        await custom_show_menu(message)

    for handler in getattr(dp.message, "handlers", []):
        callback = getattr(handler, "callback", None)
        if getattr(callback, "__name__", "") == "cmd_start":
            handler.callback = patched_cmd_start

    main.logger.info("GiftsMMS premium UI loaded")


def _patch_dispatcher():
    try:
        from aiogram import Dispatcher
        original_start_polling = Dispatcher.start_polling

        @functools.wraps(original_start_polling)
        async def patched_start_polling(self, *bots, **kwargs):
            _install_giftsmms_ui(self)
            return await original_start_polling(self, *bots, **kwargs)

        Dispatcher.start_polling = patched_start_polling
    except Exception:
        pass


_patch_dispatcher()
