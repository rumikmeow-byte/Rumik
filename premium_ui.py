"""Premium visual layer for GiftsMMS Telegram bot.

Telegram does not allow arbitrary fonts, so this uses readable Unicode display
characters, HTML emphasis and clean separators without changing business logic.
"""

import html
import sys


def install():
    main = sys.modules.get("__main__")
    if main is None or getattr(main, "_PREMIUM_UI_V2", False):
        return

    try:
        from aiogram import types
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
    except Exception:
        return

    bot = getattr(main, "bot", None)
    if bot is None:
        return

    main._PREMIUM_UI_V2 = True

    def quick_menu():
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🎁 Кейсы"), KeyboardButton(text="👤 Профиль")],
                [KeyboardButton(text="💰 Баланс"), KeyboardButton(text="👥 Рефералы")],
                [KeyboardButton(text="💳 Пополнить"), KeyboardButton(text="🏆 Топ")],
                [KeyboardButton(text="📢 Канал"), KeyboardButton(text="🆘 Поддержка")],
            ],
            resize_keyboard=True,
            is_persistent=True,
            input_field_placeholder="✦ Выберите раздел ✦",
        )

    def home_buttons():
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎁  ОТКРЫТЬ КЕЙСЫ", callback_data="ui_cases")],
            [InlineKeyboardButton(text="👤  ПРОФИЛЬ", callback_data="ui_balance"), InlineKeyboardButton(text="👥  РЕФЕРАЛЫ", callback_data="ui_refs")],
            [InlineKeyboardButton(text="💳  ПОПОЛНИТЬ", callback_data="ui_topup")],
            [InlineKeyboardButton(text="📢  КАНАЛ", url="https://t.me/eclipsedlf"), InlineKeyboardButton(text="🆘  ПОДДЕРЖКА", url="https://t.me/Eclipsed_consult")],
        ])

    async def premium_show_menu(target):
        user = target.from_user
        uid = str(user.id)
        try:
            await main.ensure_user(uid, user.username or f"User_{uid[:6]}", user.full_name or "")
        except Exception:
            pass

        if user.id != getattr(main, "SUPPORT_ID", 0):
            try:
                subscribed = await main.check_subscription(user.id)
            except Exception:
                subscribed = True
            if not subscribed:
                if isinstance(target, types.CallbackQuery):
                    await target.answer("🔒 Сначала подпишитесь на канал и чат", show_alert=True)
                try:
                    await bot.send_message(
                        user.id,
                        "╭───────────────╮\n"
                        "│  🔐 <b>ДОСТУП ЗАКРЫТ</b>  │\n"
                        "╰───────────────╯\n\n"
                        "Чтобы открыть <b>GiftsMMS</b>, подпишитесь на канал и вступите в чат.\n\n"
                        "✦ После подписки нажмите <b>«Проверить подписку»</b>.",
                        reply_markup=await main.subscription_keyboard(),
                        parse_mode="HTML",
                    )
                except Exception:
                    pass
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

        name = html.escape(user.first_name or "друг")
        text = (
            "╭────────────────────╮\n"
            "│   𝙂𝙄𝙁𝙏𝙎𝙈𝙈𝙎  ✦  𝙋𝙍𝙊   │\n"
            "╰────────────────────╯\n\n"
            f"✨ <b>Привет, {name}!</b>\n\n"
            "🎁 <b>GiftsMMS</b> — пространство кейсов, подарков и звёзд.\n\n"
            "✦ Открывай кейсы и получай награды\n"
            "✦ Приглашай друзей и зарабатывай\n"
            "✦ Управляй балансом и профилем\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💎 <b>Премиум-меню готово.</b>\n"
            "👇 Выбери нужный раздел"
        )
        try:
            await bot.send_message(chat_id, text, reply_markup=home_buttons(), parse_mode="HTML")
            await bot.send_message(chat_id, "✦ <b>БЫСТРОЕ МЕНЮ</b> ✦", reply_markup=quick_menu(), parse_mode="HTML")
        except Exception:
            await bot.send_message(chat_id, text, parse_mode="HTML")

    main.show_menu = premium_show_menu
    main.main_menu_keyboard = quick_menu

    # Keep the new quick-menu labels compatible with the existing UI handlers.
    @main.dp.message(lambda m: m.text == "👤 Профиль")
    async def _profile(message):
        try:
            data = await main.get_user_data(str(message.from_user.id)) or {}
            balance = float(data.get("balance", 0) or 0)
            refs = int(data.get("refs", 0) or 0)
            username = f"@{html.escape(message.from_user.username)}" if message.from_user.username else "не указан"
            await message.answer(
                "╭───────────────╮\n"
                "│  👤 <b>ПРОФИЛЬ</b>  │\n"
                "╰───────────────╯\n\n"
                f"🪪 ID: <code>{message.from_user.id}</code>\n"
                f"💬 Username: {username}\n"
                f"⭐ Баланс: <b>{balance:.2f} ⭐</b>\n"
                f"👥 Рефералов: <b>{refs}</b>",
                parse_mode="HTML",
            )
        except Exception:
            pass

    @main.dp.message(lambda m: m.text == "💳 Пополнить")
    async def _topup_alias(message):
        await message.answer(
            "💳 <b>ПОПОЛНЕНИЕ БАЛАНСА</b>\n\nВыберите сумму ⭐",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🧸 15 ⭐", callback_data="topup:15"), InlineKeyboardButton(text="🌹 25 ⭐", callback_data="topup:25")],
                [InlineKeyboardButton(text="💎 100 ⭐", callback_data="topup:100")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="ui_home")],
            ]),
            parse_mode="HTML",
        )

    @main.dp.message(lambda m: m.text == "🏆 Топ")
    async def _top_alias(message):
        await message.answer(
            "🏆 <b>ТОП ИГРОКОВ</b>\n\n"
            "✦ Самые активные участники GiftsMMS\n"
            "✦ Больше активности — выше позиция\n\n"
            "🚀 Раздел уже готов к подключению рейтинга.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="ui_home")],
            ]),
            parse_mode="HTML",
        )
