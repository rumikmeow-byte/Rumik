const tg = window.Telegram.WebApp;

tg.ready();
tg.expand();

const user = tg.initDataUnsafe?.user;

function setText(id, value) {
    const element = document.getElementById(id);

    if (element) {
        element.textContent = value;
    }
}

function openTelegram(url) {
    tg.openTelegramLink(url);
}

function showHome() {
    closeModal();
    window.scrollTo({
        top: 0,
        behavior: "smooth"
    });
}

function closeModal() {
    const modal = document.getElementById("modal");

    if (modal) {
        modal.classList.add("hidden");
    }
}

function openModal(content) {
    const modal = document.getElementById("modal");
    const modalContent = document.getElementById("modalContent");

    if (!modal || !modalContent) return;

    modalContent.innerHTML = content;
    modal.classList.remove("hidden");
}

function openSection(section) {

    if (section === "profile") {
        openModal(`
            <h2>👤 Профиль</h2>
            <br>
            <p>Загрузка данных...</p>
        `);

        loadProfile();
        return;
    }

    if (section === "referrals") {
        openModal(`
            <h2>👥 Рефералы</h2>
            <br>
            <p>Приглашай друзей и получай</p>
            <h2>+0.85 ⭐</h2>
            <br>
            <button class="action-button"
                onclick="shareReferral()">
                📤 Поделиться ссылкой
            </button>
        `);

        return;
    }

    if (section === "roulette") {
        openModal(`
            <h2>🎰 Ежедневная рулетка</h2>
            <br>
            <p>Можно играть один раз в день.</p>
            <br>

            <div class="roulette-rewards">
                ⭐ 0.5<br>
                ⭐ 5<br>
                ⭐ 10<br>
                ⭐ 15
            </div>

            <br>

            <button class="action-button"
                onclick="spinRoulette()">
                🎰 Крутить
            </button>
        `);

        return;
    }

    if (section === "promo") {
        openModal(`
            <h2>🎁 Промокод</h2>
            <br>

            <p>
                Введи промокод, если он у тебя есть.
            </p>

            <br>

            <input
                id="promoInput"
                class="input"
                placeholder="Промокод"
                autocomplete="off"
            >

            <br>

            <button
                class="action-button"
                onclick="activatePromo()">
                Активировать
            </button>
        `);

        return;
    }

    if (section === "withdraw") {
        openModal(`
            <h2>⭐ Вывод Stars</h2>
            <br>

            <p>
                Минимальная сумма:
                <b>15 ⭐</b>
            </p>

            <br>

            <input
                id="withdrawInput"
                class="input"
                type="number"
                min="15"
                step="0.01"
                placeholder="Введите сумму"
            >

            <br>

            <button
                class="action-button"
                onclick="requestWithdraw()">
                💸 Создать заявку
            </button>
        `);

        return;
    }

    if (section === "leaders") {
        openModal(`
            <h2>🏆 Лидеры</h2>
            <br>
            <p>Загрузка рейтинга...</p>
        `);

        loadLeaders();
        return;
    }
}

async function loadProfile() {

    if (!user) {
        openModal(`
            <h2>❌ Ошибка</h2>
            <br>
            <p>
                Открой GiftsEz именно через Telegram.
            </p>
        `);

        return;
    }

    try {

        const response = await fetch(
            `/api/profile/${user.id}`
        );

        const data = await response.json();

        if (!data.ok) {
            throw new Error("API error");
        }

        const profile = data.user;

        openModal(`
            <h2>👤 ${escapeHtml(
                profile.first_name || "Пользователь"
            )}</h2>

            <br>

            <p>
                🆔 ID:
                <b>${profile.id}</b>
            </p>

            <p>
                ⭐ Баланс:
                <b>${Number(
                    profile.balance
                ).toFixed(2)} ⭐</b>
            </p>

            <p>
                👥 Рефералов:
                <b>${profile.referrals}</b>
            </p>
        `);

        setText(
            "balance",
            Number(profile.balance).toFixed(2)
        );

    } catch (error) {

        openModal(`
            <h2>⚠️ Ошибка</h2>
            <br>
            <p>
                Не удалось загрузить профиль.
            </p>
        `);
    }
}

function shareReferral() {

    if (!user) return;

    const botUsername = "GiftsEz_bot";

    const link =
        `https://t.me/${botUsername}?start=ref_${user.id}`;

    const shareUrl =
        `https://t.me/share/url?url=${
            encodeURIComponent(link)
        }`;

    tg.openTelegramLink(shareUrl);
}

async function activatePromo() {

    const input =
        document.getElementById("promoInput");

    if (!input) return;

    const code =
        input.value.trim().toUpperCase();

    if (!code) {
        tg.showAlert(
            "Введите промокод."
        );
        return;
    }

    tg.showAlert(
        "Промокод будет проверен сервером."
    );
}

async function requestWithdraw() {

    const input =
        document.getElementById("withdrawInput");

    if (!input) return;

    const amount =
        Number(input.value);

    if (!amount || amount < 15) {
        tg.showAlert(
            "Минимальная сумма вывода — 15 ⭐"
        );
        return;
    }

    tg.showAlert(
        "Заявка будет отправлена на сервер."
    );
}

async function spinRoulette() {

    tg.showAlert(
        "Рулетка будет обработана сервером."
    );
}

async function loadLeaders() {

    openModal(`
        <h2>🏆 Топ-5</h2>
        <br>

        <p>🥇 Загружается...</p>
        <p>🥈 Загружается...</p>
        <p>🥉 Загружается...</p>
        <p>4️⃣ Загружается...</p>
        <p>5️⃣ Загружается...</p>
    `);
}

function escapeHtml(value) {

    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}


// Загружаем профиль при открытии приложения
if (user) {
    loadProfile();
}
