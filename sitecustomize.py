"""GiftsMMS UI extension loaded automatically by Python."""

import functools
import html
import os
import sys
from urllib.parse import quote

MENU_IMAGE_PATH = os.path.join(os.path.dirname(__file__), "menu_small.jpg")
REFERRAL_IMAGE_URL = "https://images.weserv.nl/?url=raw.githubusercontent.com/rumikmeow-byte/Rumik/main/assets/referral_card.svg&w=768"
ADS_CONTACT_URL = "https://t.me/huskytelegram"


def _install_giftsmms_ui(dp):
    from aiogram import types, F
    from aiogram.fsm.state import State, StatesGroup
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile, ReplyKeyboardMarkup, KeyboardButton

    main = sys.modules.get("__main__")
    if main is None or getattr(main, "_GIFTSMMS_UI_INSTALLED", False):
        return

    main._GIFTSMMS_UI_INSTALLED = True
    bot = main.bot

    class AdsStates(StatesGroup):
        waiting_for_text = State()

    def dark_menu_keyboard(user_id: int):
        # Обычная клавиатура Telegram внизу экрана.
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📢 Канал"), KeyboardButton(text="🆘 Поддержка")],
                [KeyboardButton(text="📣 Купить рекламу")],
                [KeyboardButton(text="💳 Пополнить баланс"), KeyboardButton(text="💰 Баланс")],
                [KeyboardButton(text="🎁 Кейсы"), KeyboardButton(text="👥 Рефералы")],
            ],
            resize_keyboard=True,
            is_persistent=True,
            input_field_placeholder="Выберите раздел 👇",
        )

    async def custom_show_menu(target):
        user = target.from_user
        user_id = str(user.id)
        await main.ensure_user(
            user_id,
            user.username or f"User_{user_id[:6]}",
            user.full_name or "",
        )

        if user.id != main.SUPPORT_ID and not await main.check_subscription(user.id):
            if isinstance(target, types.CallbackQuery):
                await target.answer("🔒 Подпишитесь на каналы!", show_alert=True)
            await bot.send_message(
                user.id,
                "🔒 <b>Для доступа к боту подпишитесь на наши каналы!</b>\n\n"
                "После подписки нажмите «✨ Проверить подписку».",
                reply_markup=await main.subscription_keyboard(),
                parse_mode="HTML",
            )
            return

        await main.credit_referral_if_needed(user.id)
        name = html.escape(user.first_name or "Helper")
        caption = (
            f"✨ <b>Привет, {name}!</b>\n"
            "💎 <b>Добро пожаловать в GiftsMMS !</b>\n"
            "💰 <b>Зарабатывай звёзды за приглашение!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "⬇️ <b>Выбери раздел:</b>"
        )

        if isinstance(target, types.CallbackQuery):
            try:
                await target.message.delete()
            except Exception:
                pass
            chat_id = user.id
        else:
            chat_id = target.chat.id

        # menu_small.jpg удалена: отправляем чистое текстовое меню
        # с обычной клавиатурой снизу.
        await bot.send_message(
            chat_id=chat_id,
            text=caption,
            reply_markup=dark_menu_keyboard(user.id),
            parse_mode="HTML",
        )

    main.show_menu = custom_show_menu
    main.main_menu_keyboard = dark_menu_keyboard

    # Кнопки ReplyKeyboardMarkup — сообщения, а не callback-кнопки.
    @dp.message(F.text == "📢 Канал")
    async def reply_channel(message: types.Message):
        await message.answer("📢 Наш канал: https://t.me/eclipsedlf")

    @dp.message(F.text == "🆘 Поддержка")
    async def reply_support(message: types.Message):
        await message.answer("🆘 Поддержка: https://t.me/Eclipsed_consult")

    @dp.message(F.text == "📣 Купить рекламу")
    async def reply_ads(message: types.Message):
        await message.answer("📣 Купить рекламу: https://t.me/huskytelegram")

    @dp.message(F.text == "💰 Баланс")
    async def reply_balance(message: types.Message):
        data = await main.get_user_data(str(message.from_user.id))
        balance = float(data.get("balance", 0)) if data else 0
        await message.answer(f"💰 Ваш баланс: <b>{balance:.2f} ⭐</b>", parse_mode="HTML")

    @dp.message(F.text == "💳 Пополнить баланс")
    async def reply_topup(message: types.Message):
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🧸 Мишка — 15 ⭐", callback_data="topup:15")],
            [InlineKeyboardButton(text="🌹 Роза — 25 ⭐", callback_data="topup:25")],
            [InlineKeyboardButton(text="💎 Алмаз — 100 ⭐", callback_data="topup:100")],
        ])
        await message.answer("⭐ <b>Пополнение баланса</b>\n\nВыберите подарок для пополнения:", reply_markup=kb, parse_mode="HTML")

    @dp.message(F.text == "🎁 Кейсы")
    async def reply_cases(message: types.Message):
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎁 15 ⭐", callback_data="case:15"), InlineKeyboardButton(text="🎁 25 ⭐", callback_data="case:25"), InlineKeyboardButton(text="🎁 50 ⭐", callback_data="case:50")],
            [InlineKeyboardButton(text="🎁 75 ⭐", callback_data="case:75"), InlineKeyboardButton(text="🎁 100 ⭐", callback_data="case:100"), InlineKeyboardButton(text="🎁 150 ⭐", callback_data="case:150")],
            [InlineKeyboardButton(text="🎁 250 ⭐", callback_data="case:250"), InlineKeyboardButton(text="🎁 500 ⭐", callback_data="case:500")],
        ])
        await message.answer("🎁 <b>Выберите кейс:</b>", reply_markup=kb, parse_mode="HTML")

    @dp.message(F.text == "👥 Рефералы")
    async def reply_referrals(message: types.Message):
        user_id = str(message.from_user.id)
        await main.ensure_user(user_id, message.from_user.username or f"User_{user_id[:6]}", message.from_user.full_name or "")
        me = await bot.get_me()
        ref_link = f"https://t.me/{me.username}?start=ref_{user_id}"
        data = await main.get_user_data(user_id)
        refs = data.get("refs", 0)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📨 ОТПРАВИТЬ ДРУГУ", url="https://t.me/share/url?url=" + quote(ref_link, safe="") + "&text=" + quote("Приглашай друзей и Зарабатывай звёзды!", safe=""))],
        ])
        await message.answer(
            "👥 <b>Приглашай друзей и Зарабатывай звёзды!</b>\n\n"
            f"🔗 Твоя ссылка:\n<code>{html.escape(ref_link)}</code>\n\n"
            f"⭐ За каждого друга: <b>+{main.REF_BONUS:.2f} ⭐</b>\n"
            f"👥 Приглашено: <b>{refs}</b>",
            reply_markup=kb,
            parse_mode="HTML",
        )

    async def patched_cmd_start(message: types.Message):
        user_id = str(message.from_user.id)
        await main.ensure_user(
            user_id,
            message.from_user.username or f"User_{user_id[:6]}",
            message.from_user.full_name or "",
        )
        args = (message.text or "").split()
        if len(args) > 1:
            ref_id = args[1]
            if ref_id.startswith("ref_"):
                ref_id = ref_id[4:]
            if ref_id != user_id and ref_id.isdigit():
                async with main.db_pool.acquire() as db:
                    async with db.transaction():
                        user_row = await db.fetchrow(
                            "SELECT referred_by FROM users WHERE user_id = $1 FOR UPDATE",
                            int(user_id),
                        )
                        ref_exists = await db.fetchrow(
                            "SELECT user_id FROM users WHERE user_id = $1",
                            int(ref_id),
                        )
                        if ref_exists and user_row and user_row["referred_by"] is None:
                            await db.execute(
                                "UPDATE users SET referred_by = $1 WHERE user_id = $2 AND referred_by IS NULL",
                                int(ref_id), int(user_id),
                            )
        await custom_show_menu(message)

    for handler in getattr(dp.message, "handlers", []):
        callback = getattr(handler, "callback", None)
        if getattr(callback, "__name__", "") == "cmd_start":
            handler.callback = patched_cmd_start

    main.logger.info("GiftsMMS UI extension loaded: ReplyKeyboardMarkup main menu")


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
