import asyncio
from flask import Flask,render_template,jsonify,request
from config import *
from database import *
from bot import bot
app=Flask(__name__); init_db()
def memberships(uid):
    async def go():
        out=[]
        for r in required():
            try: m=await bot.get_chat_member(r['chat_ref'],uid); ok=m.status not in ('left','kicked')
            except: ok=False
            out.append({'chat_ref':r['chat_ref'],'title':r['title'],'ok':ok})
        return out
    return asyncio.run(go())
@app.get('/')
def home():return render_template('index.html')
@app.post('/api/init')
def api_init():
    u=request.json.get('user',{}); uid=int(u['id']); upsert(uid,u.get('username'),u.get('first_name')); return jsonify({'user':dict(get_user(uid)),'required':required()})
@app.post('/api/check')
def check():
    rows=memberships(int(request.json['user_id'])); return jsonify({'ok':all(x['ok'] for x in rows),'rows':rows})
@app.post('/api/spin')
def api_spin():
    uid=int(request.json['user_id'])
    if not all(x['ok'] for x in memberships(uid)):return jsonify({'ok':False,'error':'subscription'}),403
    r=spin(uid)
    if r['ok']:r['user']=dict(get_user(uid))
    return jsonify(r),200 if r['ok'] else 400
@app.post('/api/promo')
def api_promo():
    uid=int(request.json['user_id']); r=promo(uid,request.json.get('code',''))
    if r['ok']:r['user']=dict(get_user(uid))
    return jsonify(r),200 if r['ok'] else 400
@app.post('/api/withdraw')
def api_withdraw():
    uid=int(request.json['user_id']); amount=float(request.json['amount']); u=get_user(uid); wid=withdraw(uid,u['username'],amount)
    if not wid:return jsonify({'ok':False,'error':'balance_or_min'}),400
    try:asyncio.run(bot.send_message(ADMIN_CHAT_ID,f'💸 Новый вывод\n👤 @{u["username"] or "без_username"}\n🆔 {uid}\n💎 {amount:g}⭐\n📨 @{SUPPORT_USERNAME}'))
    except:pass
    return jsonify({'ok':True,'id':wid,'user':dict(get_user(uid))})
@app.get('/api/top')
def api_top():return jsonify(top5())
