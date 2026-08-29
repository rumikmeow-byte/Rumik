import os
from dotenv import load_dotenv

load_dotenv()

# === ОБЯЗАТЕЛЬНО ЗАПОЛНИ ===
BOT_TOKEN = os.getenv("BOT_TOKEN", "ВАШ_ТОКЕН_ОТ_BOTFATHER")
BOT_USERNAME = os.getenv("BOT_USERNAME", "YourBotUsername")  # без @

# Канал, на который нужно подписаться (username без @ или id вида -100...)
CHANNEL_ID = os.getenv("CHANNEL_ID", "@your_channel")  # например @Eclipsed_channel
CHANNEL_LINK = os.getenv("CHANNEL_LINK", "https://t.me/your_channel")

# Поддержка
SUPPORT_USERNAME = "Eclipsed_consult"
SUPPORT_LINK = f"https://t.me/{SUPPORT_USERNAME}"

# Куда отправлять заявки на вывод (ID админа или чата). 
# Получить свой ID: напиши боту @userinfobot
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # замени на свой Telegram ID

# Реферальный бонус
REFERRAL_BONUS = 0.85

# Минимальный вывод
MIN_WITHDRAW = 15.0
