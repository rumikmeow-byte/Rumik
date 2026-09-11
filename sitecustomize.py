"""GiftsMMS menu customization loaded automatically by Python."""

import functools
import sys


def _install_menu(dp):
    main = sys.modules.get("__main__")
    if main is None or getattr(main, "_GIFTSMMS_MENU_INSTALLED", False):
        return

    main._GIFTSMMS_MENU_INSTALLED = True
    from aiogram import F, types
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    # 1 реферал = 0.50 ⭐
    main.REF_BONUS = 0.50

    def main_menu_keyboard(user_id: int, support_id=None) -> InlineKeyboardMarkup:
        support_id = main.SUPPORT_ID if support_id is None else support_id
        rows = [
            [InlineKeyboardButton(text="👥 Рефералы", callback_data="referrals")],
            [InlineKeyboardButton(text="💰 Баланс", callback_data="balance")],
            [InlineKeyboardButton(text="🛒 Купить рекламу", callback_data="buy_ads")],
            [InlineKeyboardButton(text="💸 Вывод", callback_data="withdraw")],
        ]
        if user_id == support_id and support_id:
            rows.append([
                InlineKeyboardButton(
                    text="⚙️ Админ-панель",
                    callback_data="admin_panel",
                )
            ])
        return InlineKeyboardMarkup(inline_keyboard=rows)

    # bot.py использует эту функцию при отправке главного меню.
    main.main_menu_keyboard = main_menu_keyboard

    @dp.callback_query(F.data == "buy_ads")
    async def buy_ads(call: types.CallbackQuery):
        if not await main.require_subscription(call):
            return
        try:
            await call.message.delete()
        except Exception:
            pass
        await main.bot.send_message(
            call.from_user.id,
            "🛒 <b>Покупка рекламы</b>\n\n"
            "Для размещения рекламы напишите: @Eclipsed_consult",
            reply_markup=main.back_keyboard(),
            parse_mode="HTML",
        )
        await call.answer()


def _patch_dispatcher():
    try:
        from aiogram import Dispatcher
        original_start_polling = Dispatcher.start_polling

        @functools.wraps(original_start_polling)
        async def patched_start_polling(self, *bots, **kwargs):
            _install_menu(self)
            return await original_start_polling(self, *bots, **kwargs)

        Dispatcher.start_polling = patched_start_polling
    except Exception:
        pass


_patch_dispatcher()
