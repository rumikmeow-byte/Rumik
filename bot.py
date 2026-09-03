def main_menu_keyboard(user_id: int):
    buttons = [
        [
            InlineKeyboardButton(
                text="🔵  Канал",
                url="https://t.me/eclipsedlf"
            ),
            InlineKeyboardButton(
                text="🟣  Поддержка",
                url="https://t.me/Eclipsed_consult"
            )
        ],
        [
            InlineKeyboardButton(
                text="🟢  Рефералы",
                callback_data="referrals"
            )
        ],
        [
            InlineKeyboardButton(
                text="🟡  Рулетка",
                callback_data="roulette"
            ),
            InlineKeyboardButton(
                text="🟠  Вывод",
                callback_data="withdraw"
            )
        ],
        [
            InlineKeyboardButton(
                text="🏆  ТОП 3 Лидеров",
                callback_data="leaders"
            )
        ]
    ]

    if user_id == SUPPORT_ID and SUPPORT_ID != 0:
        buttons.append([
            InlineKeyboardButton(
                text="🔴  Админ-панель",
                callback_data="admin_panel"
            )
        ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)
