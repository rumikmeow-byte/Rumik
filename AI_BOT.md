# AI Telegram Bot

В репозитории добавлен отдельный `ai_bot.py`: AI-помощник для Telegram.

## Что умеет

- отвечать на обычные вопросы;
- решать задачи и объяснять ход решения;
- помогать с программированием;
- использовать веб-поиск для актуальных вопросов;
- генерировать изображения через `/image <описание>`;
- не пускать пользователя к AI-функциям, пока он не подписан на `@Xoylis`.

Для проверки подписки бот использует Telegram `getChatMember`. Для надёжной проверки бот должен быть администратором канала `@Xoylis`.

## Переменные окружения

Скопируй `.env.ai.example` в настройки окружения сервиса и задай:

- `AI_BOT_TOKEN` — токен отдельного Telegram-бота из BotFather;
- `OPENAI_API_KEY` — ключ OpenAI API;
- `REQUIRED_CHANNEL=@Xoylis`;
- `REQUIRED_CHANNEL_URL=https://t.me/Xoylis`.

## Запуск

```bash
pip install -r requirements-ai.txt
python ai_bot.py
```

Важно: API-ключи не нужно коммитить в GitHub. Храни их в Secrets/Environment Variables на хостинге.
