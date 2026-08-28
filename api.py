import os
from flask import Flask, jsonify, request
from database import get_user, create_user

app = Flask(__name__)

WEBAPP_URL = os.getenv("WEBAPP_URL", "")


@app.get("/")
def home():
    return jsonify({
        "ok": True,
        "app": "GiftsEz"
    })


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


if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(
        host="0.0.0.0",
        port=port
    )
