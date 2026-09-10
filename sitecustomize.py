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
    from aiogram import types
    from aiogram.fsm.state import State, StatesGroup
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile

    main = sys.modules.get("__main__")
    if main is None or getattr(main, "_GIFTSMMS_UI_INSTALLED", False):
        return

    main._GIFTSMMS_UI_INSTALLED = True
    bot = main.bot

    class AdsStates(StatesGroup):
        waiting_for_text = State()

    def dark_menu_keyboard(user_id: int):
        rows = [
            [
                InlineKeyboardButton(text="📢 Канал", url="https://t.me/eclipsedlf"),
                InlineKeyboardButton(text="🆘 Поддержка", url="https://t.me/Eclipsed_consult"),
                InlineKeyboardButton(text="📣 Купить рекламу", url="https://t.me/huskytelegram"),
            ],
            [
                InlineKeyboardButton(text="💳 Пополнить баланс", callback_data="topup"),
                InlineKeyboardButton(text="💰 Баланс", callback_data="balance"),
                InlineKeyboardButton(text="🎁 Кейсы", callback_data="cases"),
            ],
            [
                InlineKeyboardButton(text="👥 Рефералы", callback_data="referrals"),
            ],
        ]
        support_id = getattr(main, "SUPPORT_ID", 0)
        if user_id == support_id and support_id:
            rows.append([InlineKeyboardButton(text="⚙️ Админ-панель", callback_data="admin_panel")])
        return InlineKeyboardMarkup(inline_keyboard=rows)

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

        try:
            await bot.send_photo(
                chat_id=chat_id,
                photo=FSInputFile(MENU_IMAGE_PATH),
                caption=caption,
                reply_markup=dark_menu_keyboard(user.id),
                parse_mode="HTML",
            )
        except Exception as e:
            main.logger.warning(f"Не удалось отправить новое фото меню: {e}")
            await bot.send_message(
                chat_id=chat_id,
                text=caption,
                reply_markup=dark_menu_keyboard(user.id),
                parse_mode="HTML",
            )

    main.show_menu = custom_show_menu
    main.main_menu_keyboard = dark_menu_keyboard

    async def cb_referrals_new(call: types.CallbackQuery):
        if not await main.require_subscription(call):
            return

        user_id = str(call.from_user.id)
        await main.ensure_user(
            user_id,
            call.from_user.username or f"User_{user_id[:6]}",
            call.from_user.full_name or "",
        )
        me = await bot.get_me()
        ref_link = f"https://t.me/{me.username}?start=ref_{user_id}"
        share_text = "Приглашай друзей и Зарабатывай звёзды!"
        share_url = (
            "https://t.me/share/url?url="
            + quote(ref_link, safe="")
            + "&text="
            + quote(share_text, safe="")
        )
        data = await main.get_user_data(user_id)
        refs = data.get("refs", 0)

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📨  ОТПРАВИТЬ ДРУГУ", url=share_url)],
            [InlineKeyboardButton(text="🔙  НАЗАД В МЕНЮ", callback_data="menu")],
        ])
        caption = (
            "👥 <b>Приглашай друзей и Зарабатывай звёзды!</b>\n\n"
            f"🔗 <b>Твоя реферальная ссылка:</b>\n<code>{html.escape(ref_link)}</code>\n\n"
            f"⭐ За каждого друга: <b>+{main.REF_BONUS:.2f} ⭐</b>\n"
            f"👥 Приглашено: <b>{refs}</b>\n\n"
            "Нажми «📨 ОТПРАВИТЬ ДРУГУ» и выбери друга в Telegram."
        )
        try:
            await call.message.delete()
        except Exception:
            pass
        try:
            await bot.send_photo(
                call.from_user.id,
                REFERRAL_IMAGE_URL,
                caption=caption,
                reply_markup=kb,
                parse_mode="HTML",
            )
        except Exception as e:
            main.logger.warning(f"Не удалось отправить картинку рефералов: {e}")
            await bot.send_message(
                call.from_user.id,
                caption,
                reply_markup=kb,
                parse_mode="HTML",
            )
        await call.answer()

    # Replace the original referrals callback with the UI version.
    for handler in getattr(dp.callback_query, "handlers", []):
        callback = getattr(handler, "callback", None)
        if getattr(callback, "__name__", "") == "cb_referrals":
            handler.callback = cb_referrals_new

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
                                int(ref_id),
                                int(user_id),
                            )
        await custom_show_menu(message)

    for handler in getattr(dp.message, "handlers", []):
        callback = getattr(handler, "callback", None)
        if getattr(callback, "__name__", "") == "cmd_start":
            handler.callback = patched_cmd_start

    main.logger.info("GiftsMMS UI extension loaded: topup + referrals")


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
