from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import Optional

# -------------------------------
#  Константы (вынеси в config.py)
# -------------------------------
SUPPORT_ID = 123456789  # ⚠️ Замени на реальный ID своего аккаунта
BUTTON_TEXTS = {
    "channel": "🔵  Канал",
    "support": "🟣  Поддержка",
    "referrals": "🟢  Рефералы",
    "roulette": "🟡  Рулетка",
    "withdraw": "🟠  Вывод",
    "leaders": "🏆  ТОП 3 Лидеров",
    "admin": "🔴  Админ-панель",
}

# -------------------------------
#  Основная функция
# -------------------------------
def main_menu_keyboard(
    user_id: int,
    support_id: Optional[int] = None,
) -> InlineKeyboardMarkup:
    """
    Генерирует главную клавиатуру для пользователя.
    Если support_id не передан, используется глобальная константа SUPPORT_ID.
    """
    # Определяем ID поддержки
    if support_id is None:
        support_id = SUPPORT_ID  # глобальная константа

    # Базовые кнопки (видны всем)
    buttons = [
        [
            InlineKeyboardButton(
                text=BUTTON_TEXTS["channel"],
                url="https://t.me/eclipsedlf"
            ),
            InlineKeyboardButton(
                text=BUTTON_TEXTS["support"],
                url="https://t.me/Eclipsed_consult"
            ),
        ],
        [
            InlineKeyboardButton(
                text=BUTTON_TEXTS["referrals"],
                callback_data="referrals"
            )
        ],
        [
            InlineKeyboardButton(
                text=BUTTON_TEXTS["roulette"],
                callback_data="roulette"
            ),
            InlineKeyboardButton(
                text=BUTTON_TEXTS["withdraw"],
                callback_data="withdraw"
            )
        ],
        [
            InlineKeyboardButton(
                text=BUTTON_TEXTS["leaders"],
                callback_data="leaders"
            )
        ],
    ]

    # Если пользователь — поддержка, добавляем админ-кнопку
    if user_id == support_id and support_id:
        buttons.append([
            InlineKeyboardButton(
                text=BUTTON_TEXTS["admin"],
                callback_data="admin_panel"
            )
        ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)
