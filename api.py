import os
import hmac
import hashlib
import urllib.parse
from decimal import Decimal
from datetime import date

from flask import Flask, jsonify, request

from database import (
    get_connection,
    get_user,
    create_user,
    add_balance,
    remove_balance,
)

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
MIN_WITHDRAW = Decimal("15")
REFERRAL_REWARD = Decimal("0.85")


def telegram_user():
    """
    Получает пользователя из Telegram WebApp initData.
    Не доверяем user_id, который просто прислал браузер.
    """

    init_data = request.headers.get("X-Telegram-Init-Data", "")

    if not init_data or not BOT_TOKEN:
        return None

    try:
        data = dict(
            urllib.parse.parse_qsl(
                init_data,
                keep_blank_values=True
            )
        )

        received_hash = data.pop("hash", None)

        if not received_hash:
            return None

        data_check_string = "\n".join(
            f"{key}={value}"
            for key, value in sorted(data.items())
        )

        secret_key = hmac.new(
            b"WebAppData",
            BOT_TOKEN.encode(),
            hashlib.sha256
        ).digest()

        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(
            calculated_hash,
            received_hash
        ):
            return None

        user_data = data.get("user")

        if not user_data:
            return None

        import json

        return json.loads(user_data)

    except Exception:
        return None


@app.get("/")
def home():
    return jsonify({
        "ok": True,
        "app": "GiftsEz"
    })


# =========================
# ПРОФИЛЬ
# =========================

@app.get("/api/profile")
def profile():

    tg_user = telegram_user()

    if not tg_user:
        return jsonify({
            "ok": False,
            "error": "invalid_telegram_data"
        }), 401

    user_id = int(tg_user["id"])

    user = get_user(user_id)

    if not user:
        create_user(
            user_id=user_id,
            username=tg_user.get("username"),
            first_name=tg_user.get("first_name")
        )

        user = get_user(user_id)

    return jsonify({
        "ok": True,
        "user": {
            "id": user["user_id"],
            "username": user["username"],
            "first_name": user["first_name"],
            "balance": float(user["balance"]),
            "referrals": user["referrals"]
        }
    })


# =========================
# ЛИДЕРЫ
# =========================

@app.get("/api/leaders")
def leaders():

    tg_user = telegram_user()

    if not tg_user:
        return jsonify({
            "ok": False,
            "error": "unauthorized"
        }), 401

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            username,
            first_name,
            referrals
        FROM users
        ORDER BY referrals DESC, user_id ASC
        LIMIT 5
    """)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    result = []

    for position, row in enumerate(rows, start=1):

        username, first_name, referrals = row

        result.append({
            "position": position,
            "username": username,
            "first_name": first_name,
            "referrals": referrals
        })

    return jsonify({
        "ok": True,
        "leaders": result
    })


# =========================
# ПРОМОКОД
# =========================

@app.post("/api/promo")
def promo():

    tg_user = telegram_user()

    if not tg_user:
        return jsonify({
            "ok": False,
            "error": "unauthorized"
        }), 401

    body = request.get_json(silent=True) or {}

    code = str(
        body.get("code", "")
    ).strip().upper()

    if not code:
        return jsonify({
            "ok": False,
            "error": "empty_code"
        }), 400

    user_id = int(tg_user["id"])

    conn = get_connection()
    cur = conn.cursor()

    try:

        cur.execute("""
            SELECT
                reward,
                max_uses,
                uses,
                active
            FROM promos
            WHERE code = %s
        """, (code,))

        promo_data = cur.fetchone()

        if not promo_data:
            return jsonify({
                "ok": False,
                "error": "invalid_code"
            }), 400

        reward, max_uses, uses, active = promo_data

        if not active:
            return jsonify({
                "ok": False,
                "error": "promo_disabled"
            }), 400

        if uses >= max_uses:
            return jsonify({
                "ok": False,
                "error": "promo_limit"
            }), 400

        cur.execute("""
            SELECT id
            FROM promo_uses
            WHERE user_id = %s
              AND promo_code = %s
        """, (
            user_id,
            code
        ))

        if cur.fetchone():
            return jsonify({
                "ok": False,
                "error": "already_used"
            }), 400

        cur.execute("""
            INSERT INTO promo_uses
                (user_id, promo_code)
            VALUES
                (%s, %s)
        """, (
            user_id,
            code
        ))

        cur.execute("""
            UPDATE promos
            SET uses = uses + 1
            WHERE code = %s
        """, (code,))

        cur.execute("""
            UPDATE users
            SET balance = balance + %s
            WHERE user_id = %s
        """, (
            reward,
            user_id
        ))

        conn.commit()

        return jsonify({
            "ok": True,
            "reward": float(reward)
        })

    except Exception:

        conn.rollback()

        return jsonify({
            "ok": False,
            "error": "server_error"
        }), 500

    finally:
        cur.close()
        conn.close()


# =========================
# РУЛЕТКА
# =========================

@app.post("/api/roulette")
def roulette():

    tg_user = telegram_user()

    if not tg_user:
        return jsonify({
            "ok": False,
            "error": "unauthorized"
        }), 401

    import random

    user_id = int(tg_user["id"])
    today = date.today()

    conn = get_connection()
    cur = conn.cursor()

    try:

        cur.execute("""
            SELECT reward
            FROM roulette_uses
            WHERE user_id = %s
              AND play_date = %s
        """, (
            user_id,
            today
        ))

        if cur.fetchone():

            return jsonify({
                "ok": False,
                "error": "already_played"
            }), 400

        rewards = [
            (Decimal("0.5"), 50),
            (Decimal("5"), 30),
            (Decimal("10"), 15),
            (Decimal("15"), 10)
        ]

        reward = random.choices(
            [item[0] for item in rewards],
            weights=[item[1] for item in rewards],
            k=1
        )[0]

        cur.execute("""
            INSERT INTO roulette_uses
                (user_id, play_date, reward)
            VALUES
                (%s, %s, %s)
        """, (
            user_id,
            today,
            reward
        ))

        cur.execute("""
            UPDATE users
            SET balance = balance + %s
            WHERE user_id = %s
        """, (
            reward,
            user_id
        ))

        conn.commit()

        return jsonify({
            "ok": True,
            "reward": float(reward)
        })

    except Exception:

        conn.rollback()

        return jsonify({
            "ok": False,
            "error": "server_error"
        }), 500

    finally:
        cur.close()
        conn.close()


# =========================
# ВЫВОД
# =========================

@app.post("/api/withdraw")
def withdraw():

    tg_user = telegram_user()

    if not tg_user:
        return jsonify({
            "ok": False,
            "error": "unauthorized"
        }), 401

    body = request.get_json(silent=True) or {}

    try:
        amount = Decimal(
            str(body.get("amount"))
        )
    except Exception:
        return jsonify({
            "ok": False,
            "error": "invalid_amount"
        }), 400

    if amount < MIN_WITHDRAW:

        return jsonify({
            "ok": False,
            "error": "minimum_15"
        }), 400

    user_id = int(tg_user["id"])

    conn = get_connection()
    cur = conn.cursor()

    try:

        # Списываем баланс атомарно.
        cur.execute("""
            UPDATE users
            SET balance = balance - %s
            WHERE user_id = %s
              AND balance >= %s
        """, (
            amount,
            user_id,
            amount
        ))

        if cur.rowcount != 1:

            conn.rollback()

            return jsonify({
                "ok": False,
                "error": "insufficient_balance"
            }), 400

        cur.execute("""
            INSERT INTO withdrawals
                (user_id, amount, status)
            VALUES
                (%s, %s, 'pending')
            RETURNING id
        """, (
            user_id,
            amount
        ))

        withdrawal_id = cur.fetchone()[0]

        conn.commit()

        return jsonify({
            "ok": True,
            "withdrawal_id": withdrawal_id,
            "amount": float(amount)
        })

    except Exception:

        conn.rollback()

        return jsonify({
            "ok": False,
            "error": "server_error"
        }), 500

    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":

    port = int(
        os.getenv("PORT", "10000")
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
