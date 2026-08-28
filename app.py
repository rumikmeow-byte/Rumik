import os
import sqlite3
from flask import Flask, request, jsonify

app = Flask(__name__)

DB_FILE = "giftsupp.db"
REFERRAL_BONUS = 0.85


def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance REAL DEFAULT 0,
            referrals INTEGER DEFAULT 0,
            referred_by INTEGER
        )
    """)

    conn.commit()
    conn.close()


@app.route("/")
def home():
    return "GiftsUpp работает!"


@app.route("/health")
def health():
    return "OK"


@app.route("/api/user/<int:user_id>", methods=["GET"])
def get_user(user_id):
    conn = get_db()

    user = conn.execute(
        "SELECT * FROM users WHERE user_id = ?",
        (user_id,)
    ).fetchone()

    conn.close()

    if not user:
        return jsonify({
            "success": False,
            "error": "Пользователь не найден"
        }), 404

    return jsonify({
        "success": True,
        "user_id": user["user_id"],
        "balance": user["balance"],
        "referrals": user["referrals"]
    })


@app.route("/api/referral", methods=["POST"])
def api_referral():
    data = request.get_json(silent=True) or {}

    user_id = data.get("user_id")
    referrer_id = data.get("referrer_id")

    if not user_id or not referrer_id:
        return jsonify({
            "success": False,
            "error": "user_id и referrer_id обязательны"
        }), 400

    if str(user_id) == str(referrer_id):
        return jsonify({
            "success": False,
            "error": "Нельзя пригласить самого себя"
        }), 400

    conn = get_db()

    # Создаём пользователя, если его ещё нет
    conn.execute(
        """
        INSERT OR IGNORE INTO users
        (user_id, balance, referrals)
        VALUES (?, 0, 0)
        """,
        (user_id,)
    )

    # Создаём реферера, если его ещё нет
    conn.execute(
        """
        INSERT OR IGNORE INTO users
        (user_id, balance, referrals)
        VALUES (?, 0, 0)
        """,
        (referrer_id,)
    )

    # Проверяем, был ли уже реферал
    user = conn.execute(
        "SELECT referred_by FROM users WHERE user_id = ?",
        (user_id,)
    ).fetchone()

    if user["referred_by"] is not None:
        conn.close()

        return jsonify({
            "success": False,
            "error": "Реферал уже был засчитан"
        }), 400

    # Записываем пригласившего
    conn.execute(
        """
        UPDATE users
        SET referred_by = ?
        WHERE user_id = ?
        """,
        (referrer_id, user_id)
    )

    # Начисляем 0.85 ⭐
    conn.execute(
        """
        UPDATE users
        SET balance = balance + ?,
            referrals = referrals + 1
        WHERE user_id = ?
        """,
        (REFERRAL_BONUS, referrer_id)
    )

    conn.commit()

    referrer = conn.execute(
        "SELECT balance, referrals FROM users WHERE user_id = ?",
        (referrer_id,)
    ).fetchone()

    conn.close()

    return jsonify({
        "success": True,
        "bonus": REFERRAL_BONUS,
        "balance": referrer["balance"],
        "referrals": referrer["referrals"]
    })


init_db()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port
    )
