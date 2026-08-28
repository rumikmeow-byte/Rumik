import os
import random
from datetime import date

from flask import Flask, jsonify, request, send_from_directory

from database import get_connection, get_user, create_user


app = Flask(__name__)


BOT_USERNAME = os.getenv("BOT_USERNAME", "GiftsEz_bot")


# =========================
# ГЛАВНАЯ
# =========================

@app.route("/")
def home():
    return send_from_directory(".", "index.html")


# =========================
# ПРОФИЛЬ
# =========================

@app.route("/api/profile/<int:user_id>")
def profile(user_id):

    user = get_user(user_id)

    if not user:
        create_user(user_id)
        user = get_user(user_id)

    return jsonify({
        "ok": True,
        "user": {
            "id": user["user_id"],
            "username": user["username"],
            "first_name": user["first_name"],
            "balance": float(user["balance"] or 0),
            "referrals": int(user["referrals"] or 0)
        }
    })


# =========================
# ПРОМОКОД
# =========================

@app.route("/api/promo", methods=["POST"])
def promo():

    data = request.get_json(silent=True) or {}

    user_id = data.get("user_id")
    code = str(data.get("code", "")).strip().upper()

    if not user_id:
        return jsonify({
            "ok": False,
            "error": "Пользователь не указан"
        }), 400

    if not code:
        return jsonify({
            "ok": False,
            "error": "Введите промокод"
        }), 400

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT code, reward, max_uses, uses, active
            FROM promos
            WHERE code = %s
            FOR UPDATE
        """, (code,))

        promo_data = cur.fetchone()

        if not promo_data:
            conn.rollback()
            return jsonify({
                "ok": False,
                "error": "Промокод не найден"
            })

        promo_code = promo_data[0]
        reward = float(promo_data[1])
        max_uses = promo_data[2]
        uses = promo_data[3]
        active = promo_data[4]

        if not active:
            conn.rollback()
            return jsonify({
                "ok": False,
                "error": "Промокод отключён"
            })

        if uses >= max_uses:
            conn.rollback()
            return jsonify({
                "ok": False,
                "error": "Лимит промокода исчерпан"
            })

        cur.execute("""
            SELECT id
            FROM promo_uses
            WHERE user_id = %s
              AND promo_code = %s
        """, (user_id, promo_code))

        if cur.fetchone():
            conn.rollback()
            return jsonify({
                "ok": False,
                "error": "Ты уже использовал этот промокод"
            })

        cur.execute("""
            SELECT user_id
            FROM users
            WHERE user_id = %s
            FOR UPDATE
        """, (user_id,))

        if not cur.fetchone():
            conn.rollback()
            return jsonify({
                "ok": False,
                "error": "Пользователь не найден"
            })

        cur.execute("""
            UPDATE users
            SET balance = balance + %s
            WHERE user_id = %s
        """, (reward, user_id))

        cur.execute("""
            INSERT INTO promo_uses
                (user_id, promo_code)
            VALUES
                (%s, %s)
        """, (user_id, promo_code))

        cur.execute("""
            UPDATE promos
            SET uses = uses + 1
            WHERE code = %s
        """, (promo_code,))

        conn.commit()

        return jsonify({
            "ok": True,
            "reward": reward
        })

    except Exception as error:
        conn.rollback()
        print("PROMO ERROR:", error)

        return jsonify({
            "ok": False,
            "error": "Ошибка промокода"
        }), 500

    finally:
        cur.close()
        conn.close()


# =========================
# РУЛЕТКА
# =========================

@app.route("/api/roulette", methods=["POST"])
def roulette():

    data = request.get_json(silent=True) or {}

    user_id = data.get("user_id")

    if not user_id:
        return jsonify({
            "ok": False,
            "error": "Пользователь не указан"
        }), 400

    conn = get_connection()
    cur = conn.cursor()

    try:
        today = date.today()

        cur.execute("""
            SELECT user_id
            FROM users
            WHERE user_id = %s
            FOR UPDATE
        """, (user_id,))

        if not cur.fetchone():
            conn.rollback()

            return jsonify({
                "ok": False,
                "error": "Пользователь не найден"
            })

        cur.execute("""
            SELECT reward
            FROM roulette_uses
            WHERE user_id = %s
              AND play_date = %s
        """, (user_id, today))

        if cur.fetchone():
            conn.rollback()

            return jsonify({
                "ok": False,
                "error": "Ты уже крутил рулетку сегодня"
            })

        # Шансы:
        # 0.5 ⭐ — 50%
        # 5 ⭐   — 30%
        # 10 ⭐  — 15%
        # 15 ⭐  — 5%

        number = random.uniform(0, 100)

        if number < 50:
            reward = 0.5
        elif number < 80:
            reward = 5
        elif number < 95:
            reward = 10
        else:
            reward = 15

        cur.execute("""
            INSERT INTO roulette_uses
                (user_id, play_date, reward)
            VALUES
                (%s, %s, %s)
        """, (user_id, today, reward))

        cur.execute("""
            UPDATE users
            SET balance = balance + %s
            WHERE user_id = %s
        """, (reward, user_id))

        conn.commit()

        return jsonify({
            "ok": True,
            "reward": reward
        })

    except Exception as error:
        conn.rollback()
        print("ROULETTE ERROR:", error)

        return jsonify({
            "ok": False,
            "error": "Ошибка рулетки"
        }), 500

    finally:
        cur.close()
        conn.close()


# =========================
# ЛИДЕРЫ
# =========================

@app.route("/api/leaders")
def leaders():

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT
                user_id,
                username,
                first_name,
                referrals
            FROM users
            ORDER BY referrals DESC
            LIMIT 10
        """)

        rows = cur.fetchall()

        result = []

        for row in rows:
            result.append({
                "user_id": row[0],
                "username": row[1],
                "first_name": row[2],
                "referrals": int(row[3] or 0)
            })

        return jsonify({
            "ok": True,
            "leaders": result
        })

    finally:
        cur.close()
        conn.close()


# =========================
# ВЫВОД
# =========================

@app.route("/api/withdraw", methods=["POST"])
def withdraw():

    data = request.get_json(silent=True) or {}

    user_id = data.get("user_id")
    amount = data.get("amount")

    if not user_id:
        return jsonify({
            "ok": False,
            "error": "Пользователь не указан"
        }), 400

    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return jsonify({
            "ok": False,
            "error": "Введите число"
        }), 400

    if amount < 15:
        return jsonify({
            "ok": False,
            "error": "Минимальный вывод — 15 ⭐"
        })

    if amount > 10000:
        return jsonify({
            "ok": False,
            "error": "Максимальный вывод — 10 000 ⭐"
        })

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT balance
            FROM users
            WHERE user_id = %s
            FOR UPDATE
        """, (user_id,))

        user = cur.fetchone()

        if not user:
            conn.rollback()

            return jsonify({
                "ok": False,
                "error": "Пользователь не найден"
            })

        balance = float(user[0] or 0)

        if balance < amount:
            conn.rollback()

            return jsonify({
                "ok": False,
                "error": "Недостаточно ⭐"
            })

        cur.execute("""
            UPDATE users
            SET balance = balance - %s
            WHERE user_id = %s
              AND balance >= %s
        """, (amount, user_id, amount))

        if cur.rowcount != 1:
            conn.rollback()

            return jsonify({
                "ok": False,
                "error": "Не удалось списать баланс"
            })

        cur.execute("""
            INSERT INTO withdrawals
                (user_id, amount, status)
            VALUES
                (%s, %s, 'pending')
            RETURNING id
        """, (user_id, amount))

        withdrawal_id = cur.fetchone()[0]

        conn.commit()

        return jsonify({
            "ok": True,
            "withdrawal_id": withdrawal_id,
            "amount": amount,
            "status": "pending"
        })

    except Exception as error:
        conn.rollback()
        print("WITHDRAW ERROR:", error)

        return jsonify({
            "ok": False,
            "error": "Ошибка создания заявки"
        }), 500

    finally:
        cur.close()
        conn.close()


# =========================
# ПРОВЕРКА СЕРВЕРА
# =========================

@app.route("/health")
def health():

    return jsonify({
        "ok": True,
        "app": "GiftsEz"
    })


# =========================
# ЗАПУСК
# =========================

if __name__ == "__main__":

    port = int(
        os.getenv(
            "PORT",
            "10000"
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
      )
