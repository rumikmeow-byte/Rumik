# GiftsEzz Telegram Bot

Бот с ежедневной рулеткой, реферальной системой, выводом звёзд и топом лидеров.

## Возможности

- ✅ Проверка подписки на канал + чат
- 🎰 Ежедневная рулетка (0.5 / 5 / 6 / 10 ⭐)
- 👥 Реферальная система (+0.85 ⭐ за каждого)
- ⭐ Вывод от 15 ⭐ (заявка уходит саппорту)
- 🏆 Топ-10 по рефералам
- 💾 Данные в `data.json`

---

## 1. Локальный запуск (для теста)

```bash
git clone <твой-репозиторий>
cd telegram-bot

python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Открой .env и вставь свой BOT_TOKEN
```

Запуск:
```bash
python bot.py
```

---

## 2. Выкладка на GitHub

1. Создай новый репозиторий на GitHub (можно Private).
2. В папке проекта:

```bash
git init
git add .
git commit -m "Initial commit: GiftsEzz bot"
git branch -M main
git remote add origin https://github.com/ТВОЙ_ЮЗЕР/ТВОЙ_РЕПО.git
git push -u origin main
```

---

## 3. Деплой на Render

1. Зайди на [https://render.com](https://render.com) → **New +** → **Background Worker**
2. Подключи свой GitHub-репозиторий
3. Настройки:

| Параметр              | Значение                  |
|-----------------------|---------------------------|
| Name                  | giftsezz-bot              |
| Region                | Frankfurt (или любой)     |
| Branch                | main                      |
| Runtime               | Python 3                  |
| Build Command         | `pip install -r requirements.txt` |
| Start Command         | `python bot.py`           |

4. **Environment** → добавь переменные:

```
BOT_TOKEN=твой_токен_от_BotFather
CHANNEL_ID=@eclipsedlf
CHAT_ID=@GiftsEzzChat
SUPPORT_ID=8644223884
MIN_WITHDRAW=15
REF_BONUS=0.85
```

5. Нажми **Create Background Worker**

Готово. Бот запустится через 1–2 минуты.

---

## Важно про данные

На бесплатном Render диск **эфемерный** — при перезапуске сервиса файл `data.json` может пропасть.

Решения:
- Платный план Render (Persistent Disk)
- Или заменить хранилище на SQLite + диск / PostgreSQL / Redis

Для старта JSON вполне хватает.

---

## Команды бота

| Команда / кнопка | Описание                          |
|------------------|-----------------------------------|
| /start           | Запуск + реферал                  |
| 🎰 РУЛЕТКА       | Раз в сутки                       |
| 👥 Рефералы      | Ссылка + статистика               |
| ⭐ Вывод         | Заявка от 15 ⭐                    |
| 🏆 Лидеры        | Топ по количеству рефералов       |

---

## Настройка

Все важные значения можно менять через переменные окружения (см. `.env.example`).

Удачи! 💎
