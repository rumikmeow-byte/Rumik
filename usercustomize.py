"""Global Telegram subscription gate."""

import os


def _install_gate():
    try:
        from aiogram import BaseMiddleware, Dispatcher
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    except Exception:
        return

    if getattr(Dispatcher, "_rumik_subscription_gate_installed", False):
        return

    class SubscriptionGateMiddleware(BaseMiddleware):
        async def __call__(self, handler, event, data):
            user = getattr(event, "from_user", None)
            if user is None:
                return await handler(event, data)

            try:
                support_id = int(os.getenv("SUPPORT_ID", "0"))
            except ValueError:
                support_id = 0

            if support_id and user.id == support_id:
                return await handler(event, data)

            text = getattr(event, "text", None) or ""
            callback_data = getattr(event, "data", None)

            # /start and the subscription-check button must always work.
            if text.startswith("/start") or callback_data == "check_sub":
                return await handler(event, data)

            bot = data.get("bot") or getattr(event, "bot", None)
            if bot is None:
                return await handler(event, data)

            required = [
                (os.getenv("CHANNEL_ID", "@eclipsedlf"), "📢 Подписаться на канал", "https://t.me/eclipsedlf"),
                (os.getenv("CHAT_ID", "@GiftsEzzChat"), "💬 Вступить в чат", "https://t.me/GiftsEzzChat"),
            ]

            for chat_id, _, _ in required:
                try:
                    member = await bot.get_chat_member(chat_id=chat_id, user_id=user.id)
                    status = getattr(member, "status", None)
                    if status in ("left", "kicked"):
                        raise RuntimeError("not subscribed")
                    if status == "restricted" and not getattr(member, "is_member", False):
                        raise RuntimeError("not subscribed")
                except Exception:
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text=required[0][1], url=required[0][2])],
                        [InlineKeyboardButton(text=required[1][1], url=required[1][2])],
                        [InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_sub")],
                    ])
                    message = (
                        "🔐 <b>ДОСТУП ОГРАНИЧЕН</b>\n\n"
                        "Чтобы пользоваться GiftsMMS, подпишитесь на канал и вступите в чат.\n\n"
                        "✦ После этого нажмите «✅ Проверить подписку»."
                    )
                    try:
                        if callback_data is not None and hasattr(event, "answer"):
                            await event.answer("🔒 Сначала подпишитесь на канал и чат!", show_alert=True)
                        await bot.send_message(user.id, message, reply_markup=keyboard, parse_mode="HTML")
                    except Exception:
                        pass
                    return None

            return await handler(event, data)

    original_init = Dispatcher.__init__

    def patched_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        middleware = SubscriptionGateMiddleware()
        self.message.outer_middleware(middleware)
        self.callback_query.outer_middleware(middleware)

    Dispatcher.__init__ = patched_init
    Dispatcher._rumik_subscription_gate_installed = True


_install_gate()

# The premium visual layer is isolated from business logic and loaded after the gate.
try:
    import premium_ui
    premium_ui.install()
except Exception:
    pass
