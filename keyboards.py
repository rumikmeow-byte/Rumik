from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import CHANNEL_LINK, SUPPORT_LINK, BOT_USERNAME


def main_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👤 Профиль", callback_data="profile"),
        InlineKeyboardButton(text="🎁 Рефералы", callback_data="referrals")
    )
    builder.row(
        InlineKeyboardButton(text="🎰 Ежедневная рулетка", callback_data="roulette"),
        InlineKeyboardButton(text="🏆 Лидеры", callback_data="leaders")
    )
    builder.row(
        InlineKeyboardButton(text="💸 Вывести звёзды", callback_data="withdraw"),
        InlineKeyboardButton(text="📢 Наш канал", url=CHANNEL_LINK)
    )
    builder.row(
        InlineKeyboardButton(text="💬 Поддержка", url=SUPPORT_LINK)
    )
    return builder.as_markup()


def back_to_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu"))
    return builder.as_markup()


def subscribe_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📢 Подписаться на канал", url=CHANNEL_LINK))
    builder.row(InlineKeyboardButton(text="✅ Я подписался", callback_data="check_sub"))
    return builder.as_markup()


def referrals_kb(ref_link: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    # Кнопка поделиться (открывает выбор чата)
    builder.row(InlineKeyboardButton(
        text="📤 Выбрать чат и отправить ссылку",
        switch_inline_query=f"Присоединяйся ко мне! {ref_link}"
    ))
    builder.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu"))
    return builder.as_markup()


def confirm_withdraw_kb(amount: float) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=f"✅ Подтвердить вывод {amount} ⭐", callback_data=f"confirm_wd_{amount}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="main_menu")
    )
    return builder.as_markup()


def roulette_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🎰 Крутить рулетку", callback_data="spin_roulette"))
    builder.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu"))
    return builder.as_markup()
