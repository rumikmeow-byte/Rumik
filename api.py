import os

from flask import Flask, jsonify, request

from database import (
    get_user,
    create_user,
    create_withdrawal,
)


app = Flask(__name__)

WEBAPP_URL = os.getenv(
    "WEBAPP_URL",
    ""
)

SUPPORT_USERNAME = os.getenv(
    "SUPPORT_USERNAME",
    "Eclipsed_consult"
)


# =========================
# ГЛАВНАЯ
# =========================

@app.get("/")
def home():

    return jsonify({
        "ok": True,
        "app": "GiftsEz"
    })


# =========================
# ПРОФИЛЬ
# =========================

@app.get("/api/profile/<int:user_id>")
def profile(user_id):

    user = get_user(user_id)

    if not user:

        create_user(
            user_id=user_id
        )

        user = get_user(
            user_id
        )

    return jsonify({
        "ok": True,
        "user": {
            "id": user["user_id"],
            "username": user["username"],
            "first_name": user["first_name"],
            "balance": float(
                user["balance"]
            ),
            "referrals": user["referrals"]
        }
    })


# =========================
# ВЫВОД STARS
# =========================

@app.post("/api/withdraw")
def withdraw():

    data = request.get_json(
        silent=True
    ) or {}

    user_id = data.get(
        "user_id"
    )

    amount = data.get(
        "amount"
    )

    # Проверяем user_id
    try:

        user_id = int(
            user_id
        )

    except (
        TypeError,
        ValueError
    ):

        return jsonify({
            "ok": False,
            "error": "Некорректный пользователь"
        }), 400

    # Проверяем сумму
    try:

        amount = float(
            amount
        )

    except (
        TypeError,
        ValueError
    ):

        return jsonify({
            "ok": False,
            "error": "Введите корректную сумму"
        }), 400

    # Только целые Stars
    if not amount.is_integer():

        return jsonify({
            "ok": False,
            "error": "Количество Stars должно быть целым числом"
        }), 400

    amount = int(
        amount
    )

    # Ограничения
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

    user = get_user(
        user_id
    )

    if not user:

        return jsonify({
            "ok": False,
            "error": "Пользователь не найден"
        }), 404

    # Создаём заявку и списываем
    # Stars атомарно
    result = create_withdrawal(
        user_id=user_id,
        amount=amount
    )

    if not result["success"]:

        return jsonify({
            "ok": False,
            "error": result["error"]
        }), 400

    return jsonify({
        "ok": True,
        "message": "Заявка создана",
        "withdrawal_id": result[
            "withdrawal_id"
        ],
        "amount": result[
            "amount"
        ],
        "support": f"@{SUPPORT_USERNAME}"
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
