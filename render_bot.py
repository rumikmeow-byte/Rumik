import asyncio

from aiogram.types import BufferedInputFile

import bot
from menu_photo_data import menu_photo

bot.MENU_PHOTO = BufferedInputFile(menu_photo(), filename="menu.jpg")


if __name__ == "__main__":
    asyncio.run(bot.main())
