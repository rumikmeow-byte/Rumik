const tg = window.Telegram.WebApp;

tg.ready();
tg.expand();

const initData = tg.initData || "";
const user = tg.initDataUnsafe?.user || null;

function apiHeaders() {
    return {
        "Content-Type": "application/json",
        "X-Telegram-Init-Data": initData
    };
}

function setBalance(value) {
    const el = document.getElementById("balance");

    if (el) {
        el.textContent = Number(value).toFixed(2);
    }
}

function openTelegram(url) {
    tg.openTelegramLink(url);
}

function closeModal() {
    const modal = document.getElementById("modal");

    if (modal) {
        modal.classList.add("hidden");
    }
}

function openModal(html) {
    const modal = document.getElementById("modal");
    const content = document.getElementById("modalContent");

    if (!modal || !content) return;

    content.innerHTML = html;
    modal.classList.remove("hidden");
}

function showHome() {
    closeModal();
    window.scrollTo({
        top: 0,
        behavior: "smooth"
    });
}


// ======================
// ПРОФИЛЬ
// ======================

async function loadProfile() {

    if (!initData) {
        openModal(`
            <h2>⚠️ Открой через Telegram</h2>
            <br>
            <p>
                GiftsEz должен быть открыт
                именно как Telegram Mini App.
            </p>
        `);

        return;
    }

    try {

        const response = await fetch(
            "/api/profile",
            {
                headers: apiHeaders()
            }
        );

        const data = await response.json();

        if (!data.ok) {
            throw new Error(data.error);
        }

        const profile = data.user;

        setBalance(profile.balance);

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
                👤 Username:
                <b>
                    ${
                        profile.username
                        ? "@" + escapeHtml(profile.username)
                        : "не указан"
                    }
                </b>
            </p>

            <p>
                ⭐ Баланс:
                <b>${Number(profile.balance).toFixed(2)} ⭐</b>
            </p>

            <p>
                👥 Рефералов:
                <b>${profile.referrals}</b>
            </p>
        `);

    } catch (error) {

        openModal(`
            <h2>❌ Ошибка</h2>
            <br>
            <p>
                Не удалось загрузить профиль.
            </p>
        `);
    }
}


// ======================
// РАЗДЕЛЫ
// ======================

function openSection(section) {

    if (section === "profile") {
        loadProfile();
        return;
    }

   
