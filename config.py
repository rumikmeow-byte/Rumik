import os
from dotenv import load_dotenv
load_dotenv()
BOT_TOKEN=os.getenv('BOT_TOKEN','')
BOT_USERNAME=os.getenv('BOT_USERNAME','GiftsEzz_bot')
ADMIN_CHAT_ID=int(os.getenv('ADMIN_CHAT_ID','0'))
WEBAPP_URL=os.getenv('WEBAPP_URL','').rstrip('/')
DATABASE_URL=os.getenv('DATABASE_URL','')
SUPPORT_USERNAME=os.getenv('SUPPORT_USERNAME','Eclipsed_consult').lstrip('@')
if not BOT_TOKEN or not DATABASE_URL: raise RuntimeError('Set BOT_TOKEN and DATABASE_URL')
