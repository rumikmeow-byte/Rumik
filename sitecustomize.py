"""GiftsMMS UI extension.

Loaded automatically by Python before bot.py. It keeps the original bot logic
intact and adds the new dark menu + advertising order flow.
"""

import functools
import html
import sys

from aiogram import F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


# Replace this URL after uploading the requested logo to the repository.
MENU_IMAGE_URL = "https://raw.githubusercontent.com/rumikmeow-byte/Rumik/main/assets/menu_logo.jpg"


class AdsStates(StatesGroup):
    waiting_for_text = State()


_original_start_polling = None


def _install_giftsmms_ui(dp):
    main = sys.modules.get("__main__")
    if main is None or getattr(main, "_GIFTSMMS_UI_INSTALLED", False):
        return

    main._GIFTSMMS_UI_INSTALLED = True
    bot = main.bot

    def dark_menu_keyboard(user_id: int):
        rows = [
            [
                InlineKeyboardButton(text="📢  КАНАЛ", url="https://t.me/eclipsedlf"),
                InlineKeyboardButton(text="💬  ПОДДЕРЖКА", url="https://t.me/Eclipsed_consult"),
            ],
            [InlineKeyboardButton(text="🎁  РЕФЕРАЛЫ", callback_data="referrals")],
            [
                InlineKeyboardButton(text="🎰  РУЛЕТКА", callback_data="roulette"),
                InlineKeyboardButton(text="💳  ВЫВОД", callback_data="withdraw"),
            ],
            [InlineKeyboardButton(text="👑  ЛИДЕРЫ ПО РЕФЕРАЛАМ", callback_data="leaders")],
            [InlineKeyboardButton(text="📣  КУПИТЬ РЕКЛАМУ", callback_data="buy_ads")],
        ]

        support_id = getattr(main, "SUPPORT_ID", 0)
        if user_id == support_id and support_id:
            rows.append([
                InlineKeyboardButton(text="⚙️  АДМИН-ПАНЕЛЬ", callback_data="admin_panel")
            ])

        return InlineKeyboardMarkup(inline_keyboard=rows)

    def ads_keyboard():
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🟦  1 час — 5 ⭐", callback_data="ads_package:1h:5")],
                [InlineKeyboardButton(text="🟪  24 часа — 25 ⭐", callback_data="ads_package:24h:25")],
                [InlineKeyboardButton(text="🟥  3 дня — 60 ⭐", callback_data="ads_package:3d:60")],
                [InlineKeyboardButton(text="🔙  Назад в меню", callback_data="menu")],
            ]
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
        data = await main.get_user_data(user_id)
        balance = float(data.get("balance", 0))
        name = html.escape(user.first_name or "Helper")

        caption = (
            f"✨ <b>Привет, {name}!</b>\n"
            "💎 <b>Добро пожаловать в GiftsMMS Bot</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"⭐ <b>Твой баланс:</b> <code>{balance:.2f} ⭐</code>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💰 Зарабатывай звёзды за приглашение!\n"
            "📣 Покупай рекламу и продвигай свой проект!\n"
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

        try:
            await bot.send_photo(
                chat_id=chat_id,
                photo=MENU_IMAGE_URL,
                caption=caption,
                reply_markup=dark_menu_keyboard(user.id),
                parse_mode="HTML",
            )
        except Exception:
            await bot.send_message(
                chat_id=chat_id,
                text=caption,
                reply_markup=dark_menu_keyboard(user.id),
                parse_mode="HTML",
            )

    main.show_menu = custom_show_menu
    main.main_menu_keyboard = dark_menu_keyboard

    async def cb_buy_ads(call: types.CallbackQuery):
        if not await main.require_subscription(call):
            return
        await call.message.edit_text(
            "📣 <b>ПОКУПКА РЕКЛАМЫ</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Выбери срок размещения рекламы:\n\n"
            "🟦 1 час — <b>5 ⭐</b>\n"
            "🟪 24 часа — <b>25 ⭐</b>\n"
            "🟥 3 дня — <b>60 ⭐</b>\n\n"
            "После выбора отправь текст/ссылку рекламы. "
            "Заявка уйдёт администратору на проверку.",
            reply_markup=ads_keyboard(),
            parse_mode="HTML",
        )
        await call.answer()

    async def cb_ads_package(call: types.CallbackQuery, state: FSMContext):
        if not await main.require_subscription(call):
            return
        try:
            _, period, price = call.data.split(":", 2)
            price = float(price)
        except (ValueError, AttributeError):
            await call.answer("❌ Ошибка пакета", show_alert=True)
            return

        await state.update_data(ad_period=period, ad_price=price)
        await state.set_state(AdsStates.waiting_for_text)
        await call.message.edit_text(
            "📝 <b>Отправь рекламный материал</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Пришли одним сообщением текст рекламы, ссылку или описание проекта.\n\n"
            f"📌 Пакет: <b>{period}</b>\n"
            f"💰 Стоимость: <b>{price:.0f} ⭐</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 Отмена", callback_data="menu")
            ]]),
            parse_mode="HTML",
        )
        await call.answer()

    async def process_ads(message: types.Message, state: FSMContext):
        if not await main.require_subscription(message):
            await state.clear()
            return

        data = await state.get_data()
        period = data.get("ad_period", "не выбран")
        price = float(data.get("ad_price", 0))
        username = f"@{message.from_user.username}" if message.from_user.username else "нет username"

        admin_id = getattr(main, "SUPPORT_ID", 0)
        if not admin_id:
            await message.answer(
                "❌ Приём рекламных заявок временно недоступен.",
                reply_markup=main.back_keyboard(),
            )
            await state.clear()
            return

        admin_text = (
            "📣 <b>НОВАЯ ЗАЯВКА НА РЕКЛАМУ</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Пользователь: {html.escape(message.from_user.full_name)}\n"
            f"🔗 Username: {html.escape(username)}\n"
            f"🆔 ID: <code>{message.from_user.id}</code>\n"
            f"📌 Срок: <b>{html.escape(str(period))}</b>\n"
            f"💰 Цена: <b>{price:.0f} ⭐</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"📝 Материал:\n{html.escape(message.text or '')}"
        )

        await bot.send_message(admin_id, admin_text, parse_mode="HTML")
        await message.answer(
            "✅ <b>Заявка отправлена!</b>\n\n"
            f"📌 Пакет: <b>{html.escape(str(period))}</b>\n"
            f"💰 Стоимость: <b>{price:.0f} ⭐</b>\n\n"
            "Администратор свяжется с тобой для подтверждения размещения.",
            reply_markup=main.back_keyboard(),
            parse_mode="HTML",
        )
        await state.clear()

    dp.callback_query.register(cb_buy_ads, F.data == "buy_ads")
    dp.callback_query.register(cb_ads_package, F.data.startswith("ads_package:"))
    dp.message.register(process_ads, AdsStates.waiting_for_text)


try:
    from aiogram import Dispatcher
    _original_start_polling = Dispatcher.start_polling

    @functools.wraps(_original_start_polling)
    async def _patched_start_polling(self, *bots, **kwargs):
        _install_giftsmms_ui(self)
        return await _original_start_polling(self, *bots, **kwargs)

    Dispatcher.start_polling = _patched_start_polling
except Exception:
    pass
