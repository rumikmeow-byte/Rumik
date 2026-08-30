import asyncio
import random
import logging
from datetime import date
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, CommandObject, Command
from aiogram.types import Message, CallbackQuery, InlineQuery, InlineQueryResultArticle, InputTextMessageContent
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from config import (
    BOT_TOKEN, BOT_USERNAME, CHANNEL_ID, CHANNEL_LINK,
    SUPPORT_LINK, SUPPORT_USERNAME, ADMIN_ID, REFERRAL_BONUS, MIN_WITHDRAW
)
from database import (
    init_db, get_user, create_user, update_user_info,
    add_balance, set_balance, increment_referrals,
    set_last_roulette, get_top_referrers, create_withdraw_request
)
from keyboards import (
    main_menu_kb, back_to_menu_kb, subscribe_kb,
    referrals_kb, confirm_withdraw_kb, roulette_kb
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())


# === FSM ===
class WithdrawStates(StatesGroup):
    waiting_amount = State()


# === Утилиты ===
async def is_subscribed(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in (
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR
        )
    except Exception as e:
        logger.warning(f"Subscription check error: {e}")
        return False


def format_profile(user: dict) -> str:
    username = f"@{user['username']}" if user.get("username") else "нет"
    return (
        f"╭─────────────────────╮\n"
        f"│  <tg-emoji emoji-id='5368324170678222440'>🌌</tg-emoji> <b>ТВОЙ ПРОФИЛЬ</b>  │\n"
        f"╰─────────────────────╯\n\n"
        f"👤 <b>Имя:</b> {user.get('full_name', '—')}\n"
        f"🔗 <b>Username:</b> {username}\n"
        f"🆔 <b>ID:</b> <code>{user['user_id']}</code>\n\n"
        f"⭐ <b>Баланс:</b> <code>{user['balance']:.2f}</code> звёзд\n"
        f"🎁 <b>Рефералов:</b> <code>{user['referrals_count']}</code>\n\n"
        f"<i>Звезды ждут тебя!...</i> <tg-emoji emoji-id='5368324170678222440'>💜</tg-emoji>"
    )


def welcome_text(name: str) -> str:
    return (
        f"╭──────────────────────────╮\n"
        f"│  🫧 <b>ДОБРО ПОЖАЛОВАТЬ</b>  │\n"
        f"╰──────────────────────────╯\n\n"
        f"Привет, <b>{name}</b>!\n\n"
        f"Добро пожаловать на <b>GiftEzz</b> !\n\n"
        f"Здесь ты можешь:\n"
        f"• Зарабатывать звёзды через рефералов\n"
        f"• Крутить ежедневную рулетку\n"
        f"• Выводить звёзды\n\n"
        f"<i>Выбери действие в меню ниже</i> ⬇️"
    )


# === Хендлеры ===
@dp.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    full_name = message.from_user.full_name or "Пользователь"

    user = await get_user(user_id)

    referred_by = None
    if command.args:
        args_clean = command.args.strip()
        try:
            if args_clean.startswith("ref_"):
                ref_id = int(args_clean.split("_")[1])
                if ref_id != user_id:
                    referred_by = ref_id
            elif args_clean.isdigit():
                ref_id = int(args_clean)
                if ref_id != user_id:
                    referred_by = ref_id
        except (ValueError, IndexError):
            pass

    if not user:
        await create_user(user_id, username, full_name, referred_by)
        
        if referred_by:
            ref_user = await get_user(referred_by)
            if ref_user:
                await add_balance(referred_by, REFERRAL_BONUS)
                await increment_referrals(referred_by)
                try:
                    await bot.send_message(
                        referred_by,
                        f"🎉 <b>Новый реферал!</b>\n\n"
                        f"Пользователь <b>{full_name}</b> зашёл по твоей ссылке.\n"
                        f"Тебе начислено <b>+{REFERRAL_BONUS}</b> ⭐"
                    )
                except Exception:
                    pass
        user = await get_user(user_id)
    else:
        await update_user_info(user_id, username, full_name)

    if not await is_subscribed(user_id):
        await message.answer(
            "🔒 <b>Доступ закрыт</b>\n\n"
            "Чтобы пользоваться ботом, подпишись на наш канал:\n"
            f"<a href='{CHANNEL_LINK}'>📢 Подписаться</a>\n\n"
            "После подписки нажми кнопку ниже ⬇️",
            reply_markup=subscribe_kb(),
            disable_web_page_preview=True
        )
        return

    await message.answer(welcome_text(full_name), reply_markup=main_menu_kb())


@dp.callback_query(F.data == "check_sub")
async def check_subscription_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    if await is_subscribed(user_id):
        await callback.message.edit_text(
            "✅ <b>Подписка подтверждена!</b>\n\nТеперь ты можешь пользоваться ботом.",
            reply_markup=main_menu_kb()
        )
        user = await get_user(user_id)
        if not user:
            await create_user(
                user_id,
                callback.from_user.username or "",
                callback.from_user.full_name or "Пользователь"
            )
    else:
        await callback.answer("❌ Ты ещё не подписан на канал!", show_alert=True)


@dp.callback_query(F.data == "main_menu")
async def main_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        welcome_text(callback.from_user.full_name or "друг"),
        reply_markup=main_menu_kb()
    )


@dp.callback_query(F.data == "profile")
async def show_profile(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    if not user:
        await callback.answer("Сначала запусти /start", show_alert=True)
        return
    await callback.message.edit_text(
        format_profile(user),
        reply_markup=back_to_menu_kb()
    )


@dp.callback_query(F.data == "referrals")
async def show_referrals(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    if not user:
        await callback.answer("Сначала /start", show_alert=True)
        return

    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{callback.from_user.id}"
    text = (
        f"╭─────────────────────╮\n"
        f"│  <b>🎁 РЕФЕРАЛЬНАЯ СИСТЕМА</b>  │\n"
        f"╰─────────────────────╯\n\n"
        f"За каждого друга, который зайдёт по твоей ссылке,\n"
        f"ты получаешь <b>{REFERRAL_BONUS} ⭐</b>\n\n"
        f"📊 <b>Твоих рефералов:</b> <code>{user['referrals_count']}</code>\n\n"
        f"🔗 <b>Твоя ссылка:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        f"<i>Нажми кнопку ниже, чтобы выбрать чат и отправить ссылку другу</i> 💜"
    )
    await callback.message.edit_text(text, reply_markup=referrals_kb(ref_link))


@dp.callback_query(F.data == "leaders")
async def show_leaders(callback: CallbackQuery):
    top = await get_top_referrers(5)
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]

    text = (
        f"╭─────────────────────╮\n"
        f"│  <b>🏆 ЛИДЕРЫ РЕФЕРАЛОВ</b>  │\n"
        f"╰─────────────────────╯\n\n"
    )

    if not top:
        text += "<i>Пока никого нет. Стань первым!</i> 💜"
    else:
        for i, row in enumerate(top):
            user_id, username, full_name, refs, balance = row
            name = f"@{username}" if username else full_name or f"ID{user_id}"
            text += f"{medals[i]} <b>{name}</b> — <code>{refs}</code> реф.\n"

    text += "\n<i>Приглашай друзей и поднимайся в топ!</i>"
    await callback.message.edit_text(text, reply_markup=back_to_menu_kb())


@dp.callback_query(F.data == "roulette")
async def show_roulette(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    if not user:
        await callback.answer("Сначала /start", show_alert=True)
        return

    last = user.get("last_roulette")
    today = str(date.today())

    if last == today:
        text = (
            f"╭─────────────────────╮\n"
            f"│  <b>🎰 ЕЖЕДНЕВНАЯ РУЛЕТКА</b>  │\n"
            f"╰─────────────────────╯\n\n"
            f"Ты уже крутил рулетку сегодня!\n"
            f"Приходи завтра за новыми звёздами 💜\n\n"
            f"<b>Возможные призы:</b>\n"
            f"• 0.5 ⭐\n"
            f"• 5 ⭐\n"
            f"• 8 ⭐"
        )
        kb = back_to_menu_kb()
    else:
        text = (
            f"╭─────────────────────╮\n"
            f"│  <b>🎰 ЕЖЕДНЕВНАЯ РУЛЕТКА</b>  │\n"
            f"╰─────────────────────╯\n\n"
            f"Крути раз в сутки и получай звёзды!\n\n"
            f"<b>Призы:</b>\n"
            f"• <b>0.5 ⭐</b>\n"
            f"• <b>5 ⭐</b>\n"
            f"• <b>8 ⭐</b>\n\n"
            f"<i>Удачи, путник фиолетовой вселенной...</i> 🌌"
        )
        kb = roulette_kb()

    await callback.message.edit_text(text, reply_markup=kb)


@dp.callback_query(F.data == "spin_roulette")
async def spin_roulette(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    if not user:
        await callback.answer("Ошибка", show_alert=True)
        return

    today = str(date.today())
    if user.get("last_roulette") == today:
        await callback.answer("Ты уже крутил сегодня!", show_alert=True)
        return

    prizes = [0.5, 5.0, 8.0]
    weights = [60, 30, 10]
    prize = random.choices(prizes, weights=weights, k=1)[0]

    await add_balance(callback.from_user.id, prize)
    await set_last_roulette(callback.from_user.id, today)

    await callback.message.edit_text(
        f"╭─────────────────────╮\n"
        f"│  <b>🎉 РУЛЕТКА ПРОКРУЧЕНА!</b>  │\n"
        f"╰─────────────────────╯\n\n"
        f"Тебе выпало: <b>{prize} ⭐</b>\n\n"
        f"Звёзды уже на балансе!\n"
        f"Приходи завтра за новой удачей 💜",
        reply_markup=back_to_menu_kb()
    )


@dp.callback_query(F.data == "withdraw")
async def start_withdraw(callback: CallbackQuery, state: FSMContext):
    user = await get_user(callback.from_user.id)
    if not user:
        await callback.answer("Сначала /start", show_alert=True)
        return

    balance = user["balance"]
    if balance < MIN_WITHDRAW:
        await callback.message.edit_text(
            f"╭─────────────────────╮\n"
            f"│  <b>💸 ВЫВОД ЗВЁЗД</b>  │\n"
            f"╰─────────────────────╯\n\n"
            f"Минимальная сумма вывода — <b>{MIN_WITHDRAW} ⭐</b>\n\n"
            f"Твой баланс: <code>{balance:.2f}</code> ⭐\n\n"
            f"<i>Заработай ещё через рефералов или рулетку</i> 💜",
            reply_markup=back_to_menu_kb()
        )
        return

    await state.set_state(WithdrawStates.waiting_amount)
    await callback.message.edit_text(
        f"╭─────────────────────╮\n"
        f"│  <b>💸 ВЫВОД ЗВЁЗД</b>  │\n"
        f"╰─────────────────────╯\n\n"
        f"Твой баланс: <code>{balance:.2f}</code> ⭐\n"
        f"Минимум: <b>{MIN_WITHDRAW}</b> ⭐\n\n"
        f"Введи сумму, которую хочешь вывести:\n"
        f"<i>(числом, например 15 или 20.5)</i>",
        reply_markup=back_to_menu_kb()
    )


@dp.message(WithdrawStates.waiting_amount)
async def process_withdraw_amount(message: Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    if not user:
        await state.clear()
        return

    try:
        amount = float(message.text.replace(",", ".").strip())
    except ValueError:
        await message.answer("❌ Введи корректное число. Например: 15")
        return

    if amount < MIN_WITHDRAW:
        await message.answer(f"❌ Минимум для вывода — {MIN_WITHDRAW} ⭐")
        return

    if amount > user["balance"]:
        await message.answer(f"❌ Недостаточно средств. Баланс: {user['balance']:.2f} ⭐")
        return

    await state.clear()
    await message.answer(
        f"Ты хочешь вывести <b>{amount:.2f} ⭐</b>?\n\n"
        f"После подтверждения сумма спишется с баланса,\n"
        f"а заявка будет отправлена в поддержку.",
        reply_markup=confirm_withdraw_kb(amount)
    )


@dp.callback_query(F.data.startswith("confirm_wd_"))
async def confirm_withdraw(callback: CallbackQuery):
    amount = float(callback.data.split("_")[2])
    user_id = callback.from_user.id
    user = await get_user(user_id)

    if not user or user["balance"] < amount:
        await callback.answer("Недостаточно средств или ошибка", show_alert=True)
        return

    new_balance = user["balance"] - amount
    await set_balance(user_id, new_balance)
    req_id = await create_withdraw_request(user_id, amount)

    text_to_admin = (
        f"🔔 <b>НОВАЯ ЗАЯВКА НА ВЫВОД #{req_id}</b>\n\n"
        f"👤 Пользователь: {user.get('full_name')} (@{user.get('username') or 'нет'})\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"⭐ Сумма: <b>{amount:.2f}</b>\n"
        f"💰 Остаток баланса: {new_balance:.2f}\n\n"
        f"Свяжись с пользователем для выдачи звёзд."
    )

    if ADMIN_ID and ADMIN_ID != 0:
        try:
            await bot.send_message(ADMIN_ID, text_to_admin)
        except Exception as e:
            logger.error(f"Failed to send to ADMIN_ID: {e}")

    await callback.message.edit_text(
        f"✅ <b>Заявка #{req_id} создана!</b>\n\n"
        f"Списано: <b>{amount:.2f} ⭐</b>\n"
        f"Новый баланс: <code>{new_balance:.2f}</code> ⭐\n\n"
        f"Заявка отправлена в поддержку (@{SUPPORT_USERNAME}).\n"
        f"Ожидай ответа в ближайшее время 💜",
        reply_markup=back_to_menu_kb()
    )


@dp.inline_query()
async def inline_share(inline_query: InlineQuery):
    query = inline_query.query or ""
    results = [
        InlineQueryResultArticle(
            id="1",
            title="Отправить реферальную ссылку",
            description="Пригласи друга и получи звёзды",
            input_message_content=InputTextMessageContent(
                message_text=query if query else f"Присоединяйся к GiftEzz! https://t.me/{BOT_USERNAME}?start=ref_{inline_query.from_user.id}"
            )
        )
    ]
    await inline_query.answer(results, cache_time=1, is_personal=True)


async def main():
    await init_db()
    logger.info("Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
