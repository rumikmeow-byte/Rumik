import requests


# Добавь этот эндпоинт в свой app.py, если бот работает через Webhook
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
  data = request.get_json(silent=True)
  if not data:
    return "OK", 200

  # Проверяем, что пришло текстовое сообщение
  if "message" in data:
    message = data["message"]
    chat_id = message["chat"]["id"]
    text = message.get("text", "")
    user_id = message["from"]["id"]

    # Обработка команды /start с реферальным аргументом (например: /start 123456)
    if text.startswith("/start"):
      parts = text.split()
      if len(parts) > 1:
        referrer_id = parts[1]
        if referrer_id.isdigit():
          # Автоматически регистрируем реферала через внутренний вызов или запрос
          # Здесь можно отправить запрос на твой собственный эндпоинт или выполнить логику базы
          pass

      # Отправляем приветственное сообщение пользователю
      send_telegram_message(
          chat_id,
          f"Привет! Добро пожаловать в {BOT_USERNAME}. Твой ID: `{user_id}`",
      )

  return "OK", 200


def send_telegram_message(chat_id, text):
  if not BOT_TOKEN:
    return
  url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
  payload = {
      "chat_id": chat_id,
      "text": text,
      "parse_mode": "Markdown",
  }
  requests.post(url, json=payload)
