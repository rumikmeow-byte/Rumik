import asyncio
from aiogram import Bot,Dispatcher
from aiogram.filters import CommandStart,Command
from aiogram.types import Message,InlineKeyboardMarkup,InlineKeyboardButton,WebAppInfo
from config import *
from database import *
bot=Bot(BOT_TOKEN); dp=Dispatcher()
@dp.message(CommandStart())
async def start(m:Message):
    upsert(m.from_user.id,m.from_user.username,m.from_user.first_name); p=m.text.split(maxsplit=1)
    if len(p)==2 and p[1].startswith('ref_'):
        try:
            if add_ref(int(p[1][4:]),m.from_user.id): await m.answer('🎉 Реферал засчитан! +0.85⭐')
        except: pass
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='💎 Открыть GiftsEzz',web_app=WebAppInfo(url=WEBAPP_URL))]])
    await m.answer('💜 GiftsEzz\n\nОткрой приложение:',reply_markup=kb)
def admin(m):return m.from_user.id==ADMIN_CHAT_ID
@dp.message(Command('addchannel'))
async def add(m:Message):
    if not admin(m):return
    p=m.text.split(maxsplit=1)
    if len(p)<2:return await m.answer('Пример: /addchannel @channel')
    ref=p[1].strip()
    try:
        chat=await bot.get_chat(ref); add_required(ref,chat.title or ref); await m.answer('✅ Добавлено: '+(chat.title or ref))
    except: await m.answer('❌ Не найдено. Проверь @username/ID и права бота.')
@dp.message(Command('delchannel'))
async def delete(m:Message):
    if admin(m) and len(m.text.split())>1:del_required(m.text.split(maxsplit=1)[1].strip()); await m.answer('✅ Отключено.')
@dp.message(Command('channels'))
async def channels(m:Message):
    if admin(m):await m.answer('📋 Обязательные:\n'+'\n'.join('• '+r['chat_ref'] for r in required()))
async def main():
    init_db(); await dp.start_polling(bot)
if __name__=='__main__':asyncio.run(main())
