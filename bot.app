import os
import sqlite3
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
BOT_USERNAME = os.getenv("BOT_USERNAME", "GiftsEz_bot")

DB_FILE = "giftsupp.db"


def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            first_name TEXT,
            username TEXT,
            balance REAL DEFAULT 0,
            referrals INTEGER DEFAULT 0,
            referred_by INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            status TEXT DEFAULT 'pending'
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS promo_activations (
            user_id INTEGER,
            code TEXT,
            PRIMARY KEY (user_id, code)
        )
    """)
    conn.commit()
    conn.close()


@app.route("/")
def home():
    html_code = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<meta name="theme-color" content="#09090d">
<title>GiftsEz</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }
:root {
    --bg: #09090d; --card: #111117; --card-light: #17171f;
    --purple: #8b5cf6; --purple2: #6d28d9; --text: #ffffff;
    --muted: #92929f; --border: rgba(255,255,255,.07);
    --success: #7dd3a8; --danger: #f87171;
}
html, body { min-height: 100%; background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
body { overflow-x: hidden; }
button, input { font-family: inherit; }
button { border: 0; outline: 0; cursor: pointer; }
.app { width: 100%; max-width: 520px; min-height: 100vh; margin: auto; padding: 18px 15px 105px; position: relative; }
.header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 18px; }
.brand { font-size: 27px; font-weight: 850; letter-spacing: -1px; }
.brand-sub { margin-top: 3px; color: var(--muted); font-size: 11px; }
.avatar { width: 47px; height: 47px; border-radius: 50%; display: flex; align-items: center; justify-content: center; background: linear-gradient(145deg, #9b6cff, #4c1d95); box-shadow: 0 0 25px rgba(139,92,246,.28); font-size: 19px; font-weight: 800; }
.page { display: none; animation: pageIn .18s ease; }
.page.active { display: block; }
@keyframes pageIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
.balance-card { position: relative; overflow: hidden; padding: 24px; border-radius: 25px; background: linear-gradient(145deg, #1a1525, #101014); border: 1px solid rgba(167,139,250,.14); box-shadow: 0 20px 50px rgba(0,0,0,.35); }
.balance-label { color: var(--muted); font-size: 12px; }
.balance { margin-top: 7px; font-size: 39px; line-height: 1; font-weight: 850; letter-spacing: -1.5px; }
.balance-stars { margin-top: 8px; color: var(--muted); font-size: 12px; }
.profile-card { margin-top: 12px; padding: 18px; border-radius: 21px; background: var(--card); border: 1px solid var(--border); }
.profile-row { display: flex; align-items: center; gap: 13px; }
.profile-avatar { width: 48px; height: 48px; display: flex; align-items: center; justify-content: center; border-radius: 16px; background: var(--card-light); font-size: 21px; }
.profile-name { font-size: 15px; font-weight: 750; }
.profile-username { margin-top: 3px; color: var(--muted); font-size: 12px; }
.stats { display: grid; grid-template-columns: 1fr 1fr; gap: 11px; margin-top: 12px; }
.stat { padding: 17px; border-radius: 19px; background: var(--card); border: 1px solid var(--border); }
.stat-value { font-size: 22px; font-weight: 800; }
.stat-label { margin-top: 4px; color: var(--muted); font-size: 11px; }
.section-title { margin: 21px 2px 10px; font-size: 17px; font-weight: 800; }
.menu-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 11px; margin-top: 12px; }
.menu-item { min-height: 118px; padding: 17px; text-align: left; border-radius: 20px; background: var(--card); border: 1px solid var(--border); color: var(--text); transition: transform .15s ease; }
.menu-item:active { transform: scale(.97); }
.menu-icon { font-size: 24px; margin-bottom: 17px; }
.menu-title { font-size: 14px; font-weight: 750; }
.menu-desc { margin-top: 4px; color: var(--muted); font-size: 10px; }
.card { margin-top: 12px; padding: 19px; border-radius: 21px; background: var(--card); border: 1px solid var(--border); }
.card h2 { font-size: 21px; font-weight: 800; }
.card p { margin-top: 7px; color: var(--muted); font-size: 13px; line-height: 1.55; }
.primary { width: 100%; min-height: 52px; padding: 14px 18px; border-radius: 16px; background: linear-gradient(135deg, var(--purple), var(--purple2)); color: white; font-size: 14px; font-weight: 750; box-shadow: 0 8px 25px rgba(139,92,246,.22); transition: transform .15s ease, opacity .15s ease; }
.primary:active { transform: scale(.97); opacity: .85; }
.primary:disabled { opacity: .5; cursor: not-allowed; }
.secondary { width: 100%; min-height: 50px; padding: 13px 17px; border-radius: 16px; background: var(--card-light); color: var(--text); border: 1px solid var(--border); font-size: 14px; font-weight: 700; }
.input { width: 100%; height: 52px; margin-top: 15px; padding: 0 16px; border: 1px solid var(--border); border-radius: 16px; background: var(--card-light); color: var(--text); font-size: 15px; outline: none; }
.input:focus { border-color: rgba(139,92,246,.55); }
.input::placeholder { color: #686875; }
.ref-box { margin-top: 14px; padding: 14px; border-radius: 16px; background: var(--card-light); border: 1px solid var(--border); word-break: break-all; color: var(--muted); font-size: 12px; line-height: 1.5; }
.roulette { margin-top: 15px; min-height: 160px; display: flex; flex-direction: column; align-items: center; justify-content: center; border-radius: 23px; background: radial-gradient(circle at center, #23183b, #111117 70%); border: 1px solid rgba(139,92,246,.15); }
.roulette-result { font-size: 42px; font-weight: 850; }
.roulette-sub { margin-top: 5px; color: var(--muted); font-size: 12px; }
.reward-list { margin-top: 13px; padding: 15px; border-radius: 17px; background: var(--card-light); border: 1px solid var(--border); color: var(--muted); font-size: 13px; line-height: 2; }
.reward-list b { color: var(--text); }
.promo-status { margin-top: 11px; min-height: 20px; font-size: 12px; }
.success { color: var(--success); }
.error { color: var(--danger); }
.leader { display: flex; align-items: center; gap: 10px; min-height: 56px; margin-top: 9px; padding: 10px 13px; border-radius: 15px; background: var(--card-light); border: 1px solid var(--border); }
.leader-place { width: 28px; font-size: 18px; }
.leader-name { flex: 1; font-size: 13px; font-weight: 700; }
.leader-count { color: var(--muted); font-size: 12px; }
.support-icon { width: 65px; height: 65px; display: flex; align-items: center; justify-content: center; margin-bottom: 15px; border-radius: 20px; background: var(--card-light); font-size: 29px; }
.bottom-nav { position: fixed; z-index: 50; left: 50%; bottom: 11px; transform: translateX(-50%); width: calc(100% - 26px); max-width: 495px; height: 67px; display: grid; grid-template-columns: repeat(4,1fr); padding: 6px; border-radius: 22px; background: rgba(17,17,23,.94); border: 1px solid var(--border); backdrop-filter: blur(20px); box-shadow: 0 15px 40px rgba(0,0,0,.45); }
.nav-button { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 3px; border-radius: 17px; background: transparent; color: var(--muted); transition: .2s; }
.nav-button.active { background: rgba(139,92,246,.13); color: #c4b5fd; }
.nav-icon { font-size: 18px; }
.nav-text { font-size: 9px; }
.toast { position: fixed; z-index: 100; left: 50%; bottom: 92px; transform: translateX(-50%) translateY(15px); width: calc(100% - 36px); max-width: 450px; padding: 13px 16px; border-radius: 15px; background: #1a1a22; border: 1px solid var(--border); color: white; text-align: center; font-size: 13px; opacity: 0; pointer-events: none; transition: .2s; }
.toast.show { opacity: 1; transform: translateX(-50%) translateY(0); }
.loading { position: fixed; z-index: 200; inset: 0; display: flex; align-items: center; justify-content: center; background: var(--bg); }
.loading.hidden { display: none; }
.loader { text-align: center; }
.loader-logo { font-size: 31px; font-weight: 850; }
.loader-text { margin-top: 8px; color: var(--muted); font-size: 12px; }
</style>
</head>
<body>
<div class="loading" id="loading">
    <div class="loader">
        <div class="loader-logo">GiftsEz</div>
        <div class="loader-text">Загрузка приложения...</div>
    </div>
</div>
<div class="app">
<header class="header">
    <div>
        <div class="brand">GiftsEz</div>
        <div class="brand-sub">Telegram Mini App</div>
    </div>
    <div class="avatar" id="headerAvatar">G</div>
</header>
<section class="page active" id="page-home">
    <div class="balance-card">
        <div class="balance-label">Твой баланс</div>
        <div class="balance" id="balance">0 ⭐</div>
        <div class="balance-stars">Telegram Stars</div>
    </div>
    <div class="profile-card">
        <div class="profile-row">
            <div class="profile-avatar" id="profileAvatar">👤</div>
            <div>
                <div class="profile-name" id="profileName">Загрузка...</div>
                <div class="profile-username" id="profileUsername">@username</div>
            </div>
        </div>
    </div>
    <div class="stats">
        <div class="stat">
            <div class="stat-value" id="referralsCount">0</div>
            <div class="stat-label">Рефералов</div>
        </div>
        <div class="stat">
            <div class="stat-value" id="balanceSmall">0 ⭐</div>
            <div class="stat-label">Баланс</div>
        </div>
    </div>
    <div class="section-title">Быстрые действия</div>
    <div class="menu-grid">
        <button class="menu-item" onclick="showPage('referrals')"><div class="menu-icon">👥</div><div class="menu-title">Рефералы</div><div class="menu-desc">+0.85 ⭐ за друга</div></button>
        <button class="menu-item" onclick="showPage('withdraw')"><div class="menu-icon">💸</div><div class="menu-title">Вывод</div><div class="menu-desc">15–10 000 ⭐</div></button>
        <button class="menu-item" onclick="showPage('roulette')"><div class="menu-icon">🎰</div><div class="menu-title">Рулетка</div><div class="menu-desc">1 раз в день</div></button>
        <button class="menu-item" onclick="showPage('promo')"><div class="menu-icon">🎁</div><div class="menu-title">Промокод</div><div class="menu-desc">Получай Stars</div></button>
        <button class="menu-item" onclick="showPage('leaders')"><div class="menu-icon">🏆</div><div class="menu-title">Лидеры</div><div class="menu-desc">Топ-5</div></button>
        <button class="menu-item" onclick="showPage('support')"><div class="menu-icon">💬</div><div class="menu-title">Поддержка</div><div class="menu-desc">Помощь</div></button>
    </div>
</section>
<section class="page" id="page-referrals">
    <div class="card">
        <h2>👥 Реферальная система</h2>
        <p>Приглашай друзей и получай <b>0.85 ⭐</b> за каждого нового пользователя.</p>
        <div class="ref-box"><span id="refLink">Формируем ссылку...</span></div>
        <button class="primary" style="margin-top:12px" onclick="copyReferral()">📋 Скопировать ссылку</button>
        <button class="secondary" style="margin-top:9px" onclick="shareReferral()">📤 Поделиться</button>
    </div>
    <div class="card">
        <h2>📊 Статистика</h2>
        <p>Приглашено: <b id="referralsPageCount">0</b> человек</p>
        <p>За каждого: <b>+0.85 ⭐</b></p>
    </div>
</section>
<section class="page" id="page-withdraw">
    <div class="card">
        <h2>💸 Вывод Stars</h2>
        <p>Укажи количество Stars, которое хочешь вывести.</p>
        <p>Минимум: <b>15 ⭐</b></p>
        <p>Максимум: <b>10 000 ⭐</b></p>
        <input class="input" id="withdrawAmount" type="number" min="15" max="10000" step="1" inputmode="numeric" placeholder="Например: 100">
        <button class="primary" style="margin-top:12px" onclick="withdrawStars()">💸 Создать заявку</button>
    </div>
    <div class="card">
        <h2>💰 Баланс</h2>
        <p>Доступно: <b id="withdrawBalance">0 ⭐</b></p>
    </div>
</section>
<section class="page" id="page-roulette">
    <div class="card">
        <h2>🎰 Ежедневная рулетка</h2>
        <p>Крутить можно один раз в сутки.</p>
        <div class="roulette">
            <div class="roulette-result" id="rouletteResult">?</div>
            <div class="roulette-sub">Твоя награда</div>
        </div>
        <button class="primary" style="margin-top:14px" id="rouletteButton" onclick="playRoulette()">🎰 Крутить рулетку</button>
        <div class="reward-list">
            <div><b>0.5 ⭐</b> — 50%</div>
            <div><b>5 ⭐</b> — 30%</div>
            <div><b>10 ⭐</b> — 15%</div>
            <div><b>15 ⭐</b> — 5%</div>
        </div>
    </div>
</section>
<section class="page" id="page-promo">
    <div class="card">
        <h2>🎁 Промокод</h2>
        <p>Введи промокод и получи награду на баланс.</p>
        <input class="input" id="promoCode" type="text" autocomplete="off" placeholder="Введите промокод">
        <button class="primary" style="margin-top:12px" onclick="activatePromo()">🎁 Активировать</button>
        <div class="promo-status" id="promoStatus"></div>
    </div>
</section>
<section class="page" id="page-leaders">
    <div class="card">
        <h2>🏆 Топ-5 рефералов</h2>
        <p>Самые активные пользователи по количеству приглашённых.</p>
        <div id="leadersList">
            <div class="leader"><div class="leader-place">🥇</div><div class="leader-name">Загрузка...</div><div class="leader-count">—</div></div>
        </div>
    </div>
</section>
<section class="page" id="page-support">
    <div class="card">
        <div class="support-icon">💬</div>
        <h2>Поддержка</h2>
        <p>Если возник вопрос или проблема, напиши нашей поддержке.</p>
        <button class="primary" style="margin-top:16px" onclick="openSupport()">💬 Написать в поддержку</button>
    </div>
    <div class="card">
        <h2>📢 Наш канал</h2>
        <p>Следи за новостями и обновлениями GiftsEz в Telegram.</p>
        <button class="primary" style="margin-top:16px" onclick="openChannel()">📢 Открыть канал</button>
    </div>
</section>
</div>
<nav class="bottom-nav">
    <button class="nav-button active" data-page="home" onclick="showPage('home')"><span class="nav-icon">👤</span><span class="nav-text">Профиль</span></button>
    <button class="nav-button" data-page="referrals" onclick="showPage('referrals')"><span class="nav-icon">👥</span><span class="nav-text">Рефералы</span></button>
    <button class="nav-button" data-page="roulette" onclick="showPage('roulette')"><span class="nav-icon">🎰</span><span class="nav-text">Рулетка</span></button>
    <button class="nav-button" data-page="leaders" onclick="showPage('leaders')"><span class="nav-icon">🏆</span><span class="nav-text">Лидеры</span></button>
</nav>
<div class="toast" id="toast"></div>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<script>
const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
if (tg) { tg.ready(); tg.expand(); }
let telegramUser = null;
if (tg && tg.initDataUnsafe && tg.initDataUnsafe.user) { telegramUser = tg.initDataUnsafe.user; }
const userId = telegramUser ? telegramUser.id : null;
const BOT_USERNAME = "GiftsEz_bot";
const CHANNEL_USERNAME = "eclipsedlf";
const SUPPORT_USERNAME = "Eclipsed_consult";
let rouletteLocked = false;
let toastTimer = null;

function showPage(page) {
    document.querySelectorAll(".page").forEach(element => { element.classList.remove("active"); });
    const selected = document.getElementById("page-" + page);
    if (selected) { selected.classList.add("active"); }
    document.querySelectorAll(".nav-button").forEach(button => { button.classList.toggle("active", button.dataset.page === page); });
    if (page === "leaders") { loadLeaders(); }
}

function toast(message) {
    const element = document.getElementById("toast");
    element.textContent = message;
    element.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { element.classList.remove("show"); }, 2600);
}

function formatStars(value) {
    const number = Number(value);
    if (Number.isInteger(number)) { return String(number); }
    return number.toFixed(2).replace(/0+$/, "").replace(/\.$/, "");
}

async function loadProfile() {
    if (!userId) { setDemoProfile(); return; }
    try {
        const response = await fetch(`/api/profile/${userId}`);
        const data = await response.json();
        if (!data.ok || !data.user) { throw new Error("Profile error"); }
        renderProfile(data.user);
    } catch (error) {
        console.error(error);
        setDemoProfile();
        toast("Не удалось загрузить профиль");
    }
}

function renderProfile(user) {
    const balance = Number(user.balance || 0);
    document.getElementById("balance").textContent = `${formatStars(balance)} ⭐`;
    document.getElementById("balanceSmall").textContent = `${formatStars(balance)} ⭐`;
    document.getElementById("withdrawBalance").textContent = `${formatStars(balance)} ⭐`;
    document.getElementById("referralsCount").textContent = user.referrals || 0;
    document.getElementById("referralsPageCount").textContent = user.referrals || 0;
    document.getElementById("profileName").textContent = user.first_name || "Пользователь";
    document.getElementById("profileUsername").textContent = user.username ? "@" + user.username : "Username не указан";
    const letter = (user.first_name || "G").charAt(0).toUpperCase();
    document.getElementById("headerAvatar").textContent = letter;
    document.getElementById("profileAvatar").textContent = letter;
    buildReferralLink();
}

function setDemoProfile() {
    renderProfile({
        first_name: telegramUser ? telegramUser.first_name : "GiftsEz",
        username: telegramUser ? telegramUser.username : null,
        balance: 0,
        referrals: 0
    });
}

function buildReferralLink() {
    const element = document.getElementById("refLink");
    if (!userId) { element.textContent = "Открой приложение через Telegram"; return; }
    element.textContent = `https://t.me/${BOT_USERNAME}?start=ref_${userId}`;
}

async function copyReferral() {
    if (!userId) { toast("Открой приложение через Telegram"); return; }
    const link = `https://t.me/${BOT_USERNAME}?start=ref_${userId}`;
    try {
        await navigator.clipboard.writeText(link);
        toast("✅ Ссылка скопирована");
    } catch {
        toast("Не удалось скопировать ссылку");
    }
}

function shareReferral() {
    if (!userId) { toast("Открой приложение через Telegram"); return; }
    const link = `https://t.me/${BOT_USERNAME}?start=ref_${userId}`;
    const text = "Присоединяйся к GiftsEz 💜";
    const shareUrl = `https://t.me/share/url?url=${encodeURIComponent(link)}&text=${encodeURIComponent(text)}`;
    if (tg) { tg.openTelegramLink(shareUrl); } else { window.open(shareUrl, "_blank"); }
}

async function withdrawStars() {
    if (!userId) { toast("Открой приложение через Telegram"); return; }
    const input = document.getElementById("withdrawAmount");
    const amount = Number(input.value);
    if (!Number.isInteger(amount)) { toast("Введите целое количество Stars"); return; }
    if (amount < 15) { toast("Минимальный вывод — 15 ⭐"); return; }
    if (amount > 10000) { toast("Максимальный вывод — 10 000 ⭐"); return; }
    try {
        const response = await fetch("/api/withdraw", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ user_id: userId, amount: amount })
        });
        const data = await response.json();
        if (!data.ok) { toast("❌ " + (data.error || "Ошибка вывода")); return; }
        input.value = "";
        toast(`✅ Заявка #${data.withdrawal_id} создана`);
        await loadProfile();
    } catch (error) {
        console.error(error);
        toast("❌ Ошибка соединения");
    }
}

async function activatePromo() {
    const input = document.getElementById("promoCode");
    const status = document.getElementById("promoStatus");
    const code = input.value.trim().toUpperCase();
    if (!code) { status.textContent = "Введите промокод."; status.className = "promo-status error"; return; }
    if (!userId) { status.textContent = "Открой приложение через Telegram."; status.className = "promo-status error"; return; }
    status.textContent = "Проверяем промокод...";
    status.className = "promo-status";
    try {
        const response = await fetch("/api/promo", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ user_id: userId, code: code })
        });
        const data = await response.json();
        if (!data.ok) {
            status.textContent = "❌ " + (data.error || "Ошибка");
            status.className = "promo-status error";
            return;
        }
        status.textContent = `✅ Промокод активирован! +${data.reward} ⭐`;
        status.className = "promo-status success";
        input.value = "";
        await loadProfile();
    } catch (error) {
        console.error(error);
        status.textContent = "❌ Ошибка соединения";
        status.className = "promo-status error";
    }
}

async function playRoulette() {
    if (rouletteLocked) return;
    if (!userId) { toast("Открой приложение через Telegram"); return; }
    rouletteLocked = true;
    const button = document.getElementById("rouletteButton");
    const result = document.getElementById("rouletteResult");
    button.disabled = true;
    button.textContent = "🎰 Крутим...";
    let counter = 0;
    const animation = setInterval(() => {
        const fake = ["0.5 ⭐", "5 ⭐", "10 ⭐", "15 ⭐"];
        result.textContent = fake[Math.floor(Math.random() * fake.length)];
        counter++;
        if (counter >= 15) { clearInterval(animation); }
    }, 100);
    try {
        const response = await fetch("/api/roulette", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ user_id: userId })
        });
        const data = await response.json();
        if (!data.ok) {
            clearInterval(animation);
            result.textContent = "❌";
            button.disabled = false;
            button.textContent = "🎰 Крутить рулетку";
            rouletteLocked = false;
            toast("❌ " + (data.error || "Ошибка рулетки"));
            return;
        }
        setTimeout(() => {
            result.textContent = `${data.reward} ⭐`;
            button.textContent = "🎰 Уже сыграно";
            toast(`🎉 Ты получил ${data.reward} ⭐`);
            loadProfile();
        }, 1600);
    } catch (error) {
        clearInterval(animation);
        console.error(error);
        result.textContent = "?";
        button.disabled = false;
        button.textContent = "🎰 Крутить рулетку";
        rouletteLocked = false;
        toast("❌ Ошибка соединения");
    }
}

async function loadLeaders() {
    const container = document.getElementById("leadersList");
    try {
        const response = await fetch("/api/leaders");
        const data = await response.json();
        if (!data.ok || !Array.isArray(data.leaders)) { throw new Error("Invalid leaders"); }
        const medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"];
        if (data.leaders.length === 0) {
            container.innerHTML = `<div class="leader"><div class="leader-place">🏆</div><div class="leader-name">Пока нет лидеров</div><div class="leader-count">0</div></div>`;
            return;
        }
        container.innerHTML = data.leaders.slice(0, 5).map((leader, index) => {
            const name = escapeHtml(leader.first_name || (leader.username ? "@" + leader.username : "Пользователь"));
            return `<div class="leader"><div class="leader-place">${medals[index]}</div><div class="leader-name">${name}</div><div class="leader-count">${Number(leader.referrals || 0)} 👥</div></div>`;
        }).join("");
    } catch (error) {
        console.error(error);
        container.innerHTML = `<div class="leader"><div class="leader-place">🏆</div><div class="leader-name">Не удалось загрузить топ</div><div class="leader-count">—</div></div>`;
    }
}

function openSupport() {
    const url = `https://t.me/${SUPPORT_USERNAME}`;
    if (tg) { tg.openTelegramLink(url); } else { window.open(url, "_blank"); }
}

function openChannel() {
    const url = `https://t.me/${CHANNEL_USERNAME}`;
    if (tg) { tg.openTelegramLink(url); } else { window.open(url, "_blank"); }
}

function escapeHtml(value) {
    return String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}

async function startApp() {
    await loadProfile();
    buildReferralLink();
    setTimeout(() => { document.getElementById("loading").classList.add("hidden"); }, 250);
}

startApp();
</script>
</body>
</html>"""
    return render_template_string(html_code)


@app.route("/api/profile/<int:user_id>")
def get_profile(user_id):
    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE user_id = ?", (user_id,)
    ).fetchone()
    if not user:
        conn.execute(
            "INSERT INTO users (user_id, balance, referrals) VALUES (?, 0, 0)",
            (user_id,),
        )
        conn.commit()
        user = conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
    conn.close()
    return jsonify(
        ok=True,
        user={
            "user_id": user["user_id"],
            "first_name": user["first_name"],
            "username": user["username"],
            "balance": user["balance"],
            "referrals": user["referrals"],
        },
    )


@app.route("/api/withdraw", methods=["POST"])
def api_withdraw():
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    amount = data.get("amount")

    if not user_id or not amount:
        return jsonify(ok=False, error="Неверные данные"), 400

    try:
        amount = float(amount)
    except ValueError:
        return jsonify(ok=False, error="Неверная сумма"), 400

    if amount < 15 or amount > 10000:
        return jsonify(ok=False, error="Сумма вне диапазона"), 400

    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE user_id = ?", (user_id,)
    ).fetchone()

    if not user or user["balance"] < amount:
        conn.close()
        return jsonify(ok=False, error="Недостаточно средств"), 400

    conn.execute(
        "UPDATE users SET balance = balance - ? WHERE user_id = ?",
        (amount, user_id),
    )
    cursor = conn.execute(
        "INSERT INTO withdrawals (user_id, amount, status) VALUES (?, ?, 'pending')",
        (user_id, amount),
    )
    withdrawal_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return jsonify(ok=True, withdrawal_id=withdrawal_id)


@app.route("/api/promo", methods=["POST"])
def api_promo():
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    code = data.get("code")

    if not user_id or not code:
        return jsonify(ok=False, error="Заполните поля"), 400

    conn = get_db()
    existing = conn.execute(
        "SELECT * FROM promo_activations WHERE user_id = ? AND code = ?",
        (user_id, code),
    ).fetchone()

    if existing:
        conn.close()
        return jsonify(ok=False, error="Промокод уже активирован"), 400

    reward = 5.0  # Пример награды за промокод
    conn.execute(
        "INSERT INTO promo_activations (user_id, code) VALUES (?, ?)",
        (user_id, code),
    )
    conn.execute(
        "UPDATE users SET balance = balance + ? WHERE user_id = ?",
        (reward, user_id),
    )
    conn.commit()
    conn.close()

    return jsonify(ok=True, reward=reward)


@app.route("/api/roulette", methods=["POST"])
def api_roulette():
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    if not user_id:
        return jsonify(ok=False, error="Ошибка авторизации"), 400

    import random

    reward = random.choice([0.5, 0.5, 5, 10, 15])

    conn = get_db()
    conn.execute(
        "UPDATE users SET balance = balance + ? WHERE user_id = ?",
        (reward, user_id),
    )
    conn.commit()
    conn.close()

    return jsonify(ok=True, reward=reward)


@app.route("/api/leaders")
def api_leaders():
    conn = get_db()
    leaders = conn.execute(
        "SELECT user_id, first_name, username, referrals FROM users ORDER BY referrals DESC LIMIT 5"
    ).fetchall()
    conn.close()

    result = []
    for l in leaders:
        result.append({
            "user_id": l["user_id"],
            "first_name": l["first_name"],
            "username": l["username"],
            "referrals": l["referrals"],
        })

    return jsonify(ok=True, leaders=result)


@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    data = request.get_json(silent=True)
    if not data:
        return "OK", 200

    if "message" in data:
        message = data["message"]
        chat_id = message["chat"]["id"]
        text = message.get("text", "")
        user_id = message["from"]["id"]
        first_name = message["from"].get("first_name", "Пользователь")
        username = message["from"].get("username")

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        if not user:
            conn.execute(
                "INSERT INTO users (user_id, first_name, username, balance, referrals) VALUES (?, ?, ?, 0, 0)",
                (user_id, first_name, username),
            )
        else:
            conn.execute(
                "UPDATE users SET first_name = ?, username = ? WHERE user_id = ?",
                (first_name, username, user_id),
            )
        conn.commit()
        conn.close()

        if text.startswith("/start"):
            parts = text.split()
            if len(parts) > 1 and parts[1].startswith("ref_"):
                try:
                    referrer_id = int(parts[1].replace("ref_", ""))
                    if referrer_id != user_id:
                        conn = get_db()
                        target_user = conn.execute(
                            "SELECT referred_by FROM users WHERE user_id = ?",
                            (user_id,),
                        ).fetchone()
                        if target_user and not target_user["referred_by"]:
                            conn.execute(
                                "UPDATE users SET referred_by = ? WHERE user_id = ?",
                                (referrer_id, user_id),
                            )
                            conn.execute(
                                "UPDATE users SET balance = balance + 0.85, referrals = referrals + 1 WHERE user_id = ?",
                                (referrer_id,),
                            )
                            conn.commit()
                        conn.close()
                except ValueError:
                    pass

            send_telegram_message(
                chat_id,
                f"Привет, {first_name}! 👋\nДобро пожаловать в GiftsEz.",
            )

    return "OK", 200


def send_telegram_message(chat_id, text):
    if not BOT_TOKEN:
        return
    import requests

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    requests.post(url, json=payload)


@app.route("/health")
def health():
    return "OK"


init_db()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

