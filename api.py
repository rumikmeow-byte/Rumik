import os
import random
import datetime

from flask import Flask, jsonify, request

from database import (
    get_connection,
    get_user,
    create_user,
    add_balance,
    remove_balance
)


app = Flask(__name__)


# =========================
# ГЛАВНАЯ
# =========================

@app.get("/")
def home():
    return jsonify({
        "ok": True,
        "app": "GiftsEz",
        "status": "online"
    })


# =========================
# ПРОФИЛЬ
# =========================

@app.get("/api/profile/<int:user_id>")
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
            "balance": float(user["balance"]),
            "referrals": user["referrals"]
        }
    })


# =========================
# ВЫВОД
# =========================

@app.post("/api/withdraw")
def withdraw():

    data = request.get_json(silent=True) or {}

    user_id = data.get("user_id")
    amount = data.get("amount")

    if not user_id or amount is None:
        return jsonify({
            "ok": False,
            "error": "Не указаны данные"
        }), 400

    try:
        user_id = int(user_id)
        amount = int(amount)
    except (ValueError, TypeError):

        return jsonify({
            "ok": False,
            "error": "Некорректная сумма"
        }), 400

    # Лимиты вывода
    if amount < 15:

        return jsonify({
            "ok": False,
            "error": "Минимальный вывод — 15 ⭐"
        }), 400

    if amount > 10000:

        return jsonify({
            "ok": False,
            "error": "Максимальный вывод — 10 000 ⭐"
        }), 400

    user = get_user(user_id)

    if not user:

        return jsonify({
            "ok": False,
            "error": "Пользователь не найден"
        }), 404

    # Списываем баланс
    success = remove_balance(
        user_id,
        amount
    )

    if not success:

        return jsonify({
            "ok": False,
            "error": "Недостаточно Stars"
        }), 400

    conn = get_connection()
    cur = conn.cursor()

    try:

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

    except Exception:

        conn.rollback()

        # Возвращаем Stars,
        # если заявка не создалась
        add_balance(
            user_id,
            amount
        )

        return jsonify({
            "ok": False,
            "error": "Не удалось создать заявку"
        }), 500

    finally:

        cur.close()
        conn.close()

    return jsonify({
        "ok": True,
        "withdrawal_id": withdrawal_id,
        "amount": amount,
        "status": "pending"
    })


# =========================
# ЛИДЕРЫ
# =========================

@app.get("/api/leaders")
def leaders():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            user_id,
            username,
            first_name,
            referrals
        FROM users
        ORDER BY referrals DESC
        LIMIT 5
    """)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    result = []

    for row in rows:

        result.append({
            "user_id": row[0],
            "username": row[1],
            "first_name": row[2],
            "referrals": row[3]
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

    data = request.get_json(silent=True) or {}

    user_id = data.get("user_id")
    code = data.get("code")

    if not user_id or not code:

        return jsonify({
            "ok": False,
            "error": "Введите промокод"
        }), 400

    try:
        user_id = int(user_id)
    except (ValueError, TypeError):

        return jsonify({
            "ok": False,
            "error": "Некорректный пользователь"
        }), 400

    code = str(code).strip().upper()

    conn = get_connection()
    cur = conn.cursor()

    try:

        # Проверяем промокод
        cur.execute("""
            SELECT
                reward,
                max_uses,
                uses,
                active
            FROM promos
            WHERE code = %s
            FOR UPDATE
        """, (
            code,
        ))

        promo_data = cur.fetchone()

        if not promo_data:

            conn.rollback()

            return jsonify({
                "ok": False,
                "error": "Промокод не найден"
            }), 404

        reward = float(promo_data[0])
        max_uses = promo_data[1]
        uses = promo_data[2]
        active = promo_data[3]

        if not active:

            conn.rollback()

            return jsonify({
                "ok": False,
                "error": "Промокод отключён"
            }), 400

        if uses >= max_uses:

            conn.rollback()

            return jsonify({
                "ok": False,
                "error": "Лимит активаций промокода исчерпан"
            }), 400

        # Проверяем использовал ли пользователь
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

            conn.rollback()

            return jsonify({
                "ok": False,
                "error": "Ты уже использовал этот промокод"
            }), 400

        # Проверяем пользователя
        cur.execute("""
            SELECT user_id
            FROM users
            WHERE user_id = %s
            FOR UPDATE
        """, (
            user_id,
        ))

        if not cur.fetchone():

            conn.rollback()

            return jsonify({
                "ok": False,
                "error": "Пользователь не найден"
            }), 404

        # Начисляем награду
        cur.execute("""
            UPDATE users
            SET balance = balance + %s
            WHERE user_id = %s
        """, (
            reward,
            user_id
        ))

        # Записываем использование
        cur.execute("""
            INSERT INTO promo_uses
                (user_id, promo_code)
            VALUES
                (%s, %s)
        """, (
            user_id,
            code
        ))

        # Увеличиваем количество активаций
        cur.execute("""
            UPDATE promos
            SET uses = uses + 1
            WHERE code = %s
        """, (
            code,
        ))

        conn.commit()

    except Exception as error:

        conn.rollback()

        return jsonify({
            "ok": False,
            "error": "Ошибка активации промокода"
        }), 500

    finally:

        cur.close()
        conn.close()

    return jsonify({
        "ok": True,
        "code": code,
        "reward": reward
    })


# =========================
# РУЛЕТКА
# =========================

@app.post("/api/roulette")
def roulette():

    data = request.get_json(silent=True) or {}

    user_id = data.get("user_id")

    if not user_id:

        return jsonify({
            "ok": False,
            "error": "Пользователь не указан"
        }), 400

    try:
        user_id = int(user_id)
    except (ValueError, TypeError):

        return jsonify({
            "ok": False,
            "error": "Некорректный пользователь"
        }), 400

    today = datetime.date.today()

    conn = get_connection()
    cur = conn.cursor()

    try:

        # Проверяем сегодняшнюю игру
        cur.execute("""
            SELECT reward
            FROM roulette_uses
            WHERE user_id = %s
              AND play_date = %s
        """, (
            user_id,
            today
        ))

        already = cur.fetchone()

        if already:

            conn.rollback()

            return jsonify({
                "ok": False,
                "error": "Сегодня ты уже крутил рулетку"
            }), 400

        # Вероятности:
        # 0.5 ⭐ — 50%
        # 5 ⭐   — 30%
        # 10 ⭐  — 15%
        # 15 ⭐  — 5%

        number = random.random()

        if number < 0.50:
            reward = 0.5

        elif number < 0.80:
            reward = 5

        elif number < 0.95:
            reward = 10

        else:
            reward = 15

        # Записываем игру
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

        # Начисляем награду
        cur.execute("""
            UPDATE users
            SET balance = balance + %s
            WHERE user_id = %s
        """, (
            reward,
            user_id
        ))

        if cur.rowcount != 1:

            conn.rollback()

            return jsonify({
                "ok": False,
                "error": "Пользователь не найден"
            }), 404

        conn.commit()

    except Exception:

        conn.rollback()

        return jsonify({
            "ok": False,
            "error": "Ошибка рулетки"
        }), 500

    finally:

        cur.close()
        conn.close()

    return jsonify({
        "ok": True,
        "reward": reward
    })


# =========================
# ЗАПУСК
# =========================

if __name__ == "__main__":

    port = int(
        os.getenv(
            "PORT",
            10000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
