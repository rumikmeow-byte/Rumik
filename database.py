import psycopg2
from contextlib import contextmanager
from psycopg2.extras import RealDictCursor
from config import DATABASE_URL
@contextmanager
def db():
    c=psycopg2.connect(DATABASE_URL)
    try: yield c; c.commit()
    except: c.rollback(); raise
    finally: c.close()
def init_db():
    with db() as c:
        x=c.cursor()
        x.execute('CREATE TABLE IF NOT EXISTS users(user_id BIGINT PRIMARY KEY,username TEXT,first_name TEXT,balance NUMERIC(12,2) DEFAULT 0,referrals INT DEFAULT 0,invited_by BIGINT,last_spin_at TIMESTAMPTZ,bonus_spins INT DEFAULT 0,created_at TIMESTAMPTZ DEFAULT NOW())')
        x.execute('CREATE TABLE IF NOT EXISTS referrals(id BIGSERIAL PRIMARY KEY,inviter_id BIGINT NOT NULL,invited_id BIGINT UNIQUE NOT NULL,reward NUMERIC(12,2) DEFAULT .85,created_at TIMESTAMPTZ DEFAULT NOW())')
        x.execute('CREATE TABLE IF NOT EXISTS required_chats(chat_ref TEXT PRIMARY KEY,title TEXT,enabled BOOLEAN DEFAULT TRUE)')
        x.execute('CREATE TABLE IF NOT EXISTS promo_codes(code TEXT PRIMARY KEY,reward NUMERIC(12,2) DEFAULT 0,spins INT DEFAULT 0,max_uses INT NOT NULL,uses INT DEFAULT 0)')
        x.execute('CREATE TABLE IF NOT EXISTS promo_uses(code TEXT,user_id BIGINT,used_at TIMESTAMPTZ DEFAULT NOW(),PRIMARY KEY(code,user_id))')
        x.execute('CREATE TABLE IF NOT EXISTS withdrawals(id BIGSERIAL PRIMARY KEY,user_id BIGINT,username TEXT,amount NUMERIC(12,2),status TEXT DEFAULT \'pending\',created_at TIMESTAMPTZ DEFAULT NOW())')
        x.execute("INSERT INTO promo_codes(code,reward,spins,max_uses) VALUES('NEW',0,1,10),('10STARS',10,0,10) ON CONFLICT(code) DO NOTHING")
        x.execute("INSERT INTO required_chats(chat_ref,title) VALUES('@eclipsedlf','EclipsedLf') ON CONFLICT(chat_ref) DO NOTHING")
def upsert(uid,username,first):
    with db() as c:
        x=c.cursor(); x.execute('INSERT INTO users(user_id,username,first_name) VALUES(%s,%s,%s) ON CONFLICT(user_id) DO UPDATE SET username=EXCLUDED.username,first_name=EXCLUDED.first_name',(uid,username,first)); x.execute('SELECT * FROM users WHERE user_id=%s',(uid,)); return x.fetchone()
def get_user(uid):
    with db() as c:
        x=c.cursor(cursor_factory=RealDictCursor); x.execute('SELECT * FROM users WHERE user_id=%s',(uid,)); return x.fetchone()
def add_ref(invited_by,invited):
    if invited_by==invited:return False
    with db() as c:
        x=c.cursor(); x.execute('SELECT invited_by FROM users WHERE user_id=%s FOR UPDATE',(invited,)); r=x.fetchone()
        if not r or r[0] is not None:return False
        x.execute('SELECT 1 FROM referrals WHERE invited_id=%s',(invited,))
        if x.fetchone():return False
        x.execute('UPDATE users SET invited_by=%s WHERE user_id=%s',(invited_by,invited)); x.execute('UPDATE users SET balance=balance+.85,referrals=referrals+1 WHERE user_id=%s',(invited_by,)); x.execute('INSERT INTO referrals(inviter_id,invited_id) VALUES(%s,%s)',(invited_by,invited)); return True
def required():
    with db() as c:
        x=c.cursor(cursor_factory=RealDictCursor); x.execute('SELECT chat_ref,title FROM required_chats WHERE enabled=TRUE ORDER BY chat_ref'); return x.fetchall()
def add_required(ref,title):
    with db() as c:c.cursor().execute('INSERT INTO required_chats(chat_ref,title) VALUES(%s,%s) ON CONFLICT(chat_ref) DO UPDATE SET enabled=TRUE,title=EXCLUDED.title',(ref,title))
def del_required(ref):
    with db() as c:c.cursor().execute('UPDATE required_chats SET enabled=FALSE WHERE chat_ref=%s',(ref,))
def spin(uid):
    from datetime import datetime,timezone,timedelta
    import random
    with db() as c:
        x=c.cursor(); x.execute('SELECT last_spin_at,bonus_spins FROM users WHERE user_id=%s FOR UPDATE',(uid,)); last,bonus=x.fetchone(); now=datetime.now(timezone.utc)
        if last and now-last<timedelta(hours=24) and bonus<=0:return {'ok':False,'error':'cooldown'}
        if last and now-last<timedelta(hours=24):bonus-=1
        else:last=now
        z=random.random(); reward=3 if z<.5 else (5 if z<.8 else 10)
        x.execute('UPDATE users SET last_spin_at=%s,bonus_spins=%s,balance=balance+%s WHERE user_id=%s',(last,bonus,reward,uid)); return {'ok':True,'reward':reward}
def promo(uid,code):
    code=code.strip().upper()
    with db() as c:
        x=c.cursor(); x.execute('SELECT reward,spins,max_uses,uses FROM promo_codes WHERE code=%s FOR UPDATE',(code,)); p=x.fetchone()
        if not p:return {'ok':False,'error':'not_found'}
        reward,spins,max_uses,uses=p
        if uses>=max_uses:return {'ok':False,'error':'limit'}
        x.execute('SELECT 1 FROM promo_uses WHERE code=%s AND user_id=%s',(code,uid))
        if x.fetchone():return {'ok':False,'error':'used'}
        x.execute('INSERT INTO promo_uses(code,user_id) VALUES(%s,%s)',(code,uid)); x.execute('UPDATE promo_codes SET uses=uses+1 WHERE code=%s',(code,)); x.execute('UPDATE users SET balance=balance+%s,bonus_spins=bonus_spins+%s WHERE user_id=%s',(reward,spins,uid)); return {'ok':True}
def withdraw(uid,username,amount):
    with db() as c:
        x=c.cursor(); x.execute('SELECT balance FROM users WHERE user_id=%s FOR UPDATE',(uid,)); r=x.fetchone()
        if not r or amount<15 or amount>float(r[0]):return None
        x.execute('UPDATE users SET balance=balance-%s WHERE user_id=%s',(amount,uid)); x.execute('INSERT INTO withdrawals(user_id,username,amount) VALUES(%s,%s,%s) RETURNING id',(uid,username,amount)); return x.fetchone()[0]
def top5():
    with db() as c:
        x=c.cursor(cursor_factory=RealDictCursor); x.execute("SELECT u.username,u.first_name,COUNT(r.id) n FROM referrals r JOIN users u ON u.user_id=r.inviter_id WHERE r.created_at>=NOW()-INTERVAL '7 days' GROUP BY u.user_id ORDER BY n DESC LIMIT 5"); return x.fetchall()
