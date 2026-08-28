import os
from flask import Flask

app = Flask(__name__)


@app.route('/')
def home():
  return 'GiftEzz bot is running and alive! 🚀'


if __name__ == '__main__':
  # Render передает свой порт через переменную окружения PORT
  port = int(os.environ.get('PORT', 10000))
  app.run(host='0.0.0.0', port=port)
