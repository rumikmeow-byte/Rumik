import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

CHANNEL = os.getenv("CHANNEL", "@eclipsedlf")
SUPPORT = "@Eclipsed_consult"

REFERRAL_REWARD = 0.85
MIN_WITHDRAW = 15

PROMOCODES = {
    "IZIDROP": {
        "reward": 12,
        "max_uses": 100
    },
    "LOL10": {
        "reward": 10,
        "max_uses": 10
    }
}
