"""Runtime override for the bot's legacy menu photo.

Python imports sitecustomize automatically during interpreter startup when this
file is on sys.path. This lets us replace the old Telegram file_id without
rewriting the large bot.py file.
"""

from aiogram import Bot

OLD_MENU_PHOTO = (
    "AgACAgIAAxkBAAEuWDpqmWLboBOFIlHcmgpylNym1rLLIgACSB1rG8qiyEgmn7iMl-EITAEAAwIAA3gAAz0E"
)
NEW_MENU_PHOTO = (
    "https://raw.githubusercontent.com/rumikmeow-byte/Rumik/main/menu_small.jpg"
)

_original_send_photo = Bot.send_photo


async def _send_photo_with_new_menu(self, chat_id, photo, *args, **kwargs):
    if photo == OLD_MENU_PHOTO:
        photo = NEW_MENU_PHOTO
    return await _original_send_photo(self, chat_id, photo, *args, **kwargs)


Bot.send_photo = _send_photo_with_new_menu
