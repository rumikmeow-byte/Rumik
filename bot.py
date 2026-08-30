@dp.callback_query(F.data == "check_sub")
async def cb_check_sub(call: types.CallbackQuery) -> None:
    if await check_subscription(call.from_user.id):
        await call.answer("✅ Подписка подтверждена!")
        await show_menu(call)
    else:
        await call.answer("❌ Вы ещё не подписались на канал и чат!", show_alert=True)


@dp.callback_query(F.data == "menu")
async def cb_menu(call: types.CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await show_menu(call)


# ==================== РУЛЕТКА ====================
@dp.callback_query(F.data == "roulette")
async def cb_roulette(call: types.CallbackQuery) -> None:
    user_id = str(call.from_user.id)
    ensure_user(user_id, call.from_user.username or f"User_{user_id[:6]}")

    last = data["daily"].get(user_id)
    if last:
        try:
            last_dt = datetime.fromisoformat(last)
            if last_dt > datetime.now() - timedelta(days=1):
                await call.answer(
                    "⏳ Ты уже крутил сегодня! Жди завтра.",
                    show_alert=True,
                )
                return
        except ValueError:
            pass

    prizes = [0.5, 5, 6, 10]
    weights = [50, 30, 15, 5]  # сумма 100
    win = random.choices(prizes, weights=weights)[0]

    data["users"][user_id]["balance"] = (
        data["users"][user_id].get("balance", 0.0) + win
    )
    data["daily"][user_id] = datetime.now().isoformat()
    save_data(data)

    text = (
        f"🎰 <b>Результат рулетки</b>\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"Вы выиграли: <code>{win} ⭐</code>\n"
        f"Новый баланс: <code>{data['users'][user_id]['balance']:.2f} ⭐</code>\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"<i>Приходи завтра снова!</i>"
    )

    try:
        await call.message.delete()
    except Exception:
        pass

    await bot.send_message(
        chat_id=call.from_user.id,
        text=text,
        reply_markup=back_keyboard(),
        parse_mode="HTML",
    )
    await call.answer()


# ==================== РЕФЕРАЛЫ ====================
@dp.callback_query(F.data == "referrals")
async def cb_referrals(call: types.CallbackQuery) -> None:
    user_id = str(call.from_user.id)
    ensure_user(user_id, call.from_user.username or f"User_{user_id[:6]}")

    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
    refs_count = data["users"].get(user_id, {}).get("refs", 0)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📤 Поделиться",
                    switch_inline_query=ref_link,
                )
            ],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="menu")],
        ]
    )

    text = (
        f"👥 <b>Реферальная система</b>\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"Твоя ссылка:\n<code>{ref_link}</code>\n\n"
        f"За каждого приглашённого ты получаешь <b>{REF_BONUS} ⭐</b>\n"
        f"Всего рефералов: <code>{refs_count}</code>\n\n"
        f"<i>Нажми на ссылку, чтобы скопировать</i>"
    )

    try:
        await call.message.delete()
    except Exception:
        pass

    await bot.send_message(
        chat_id=call.from_user.id,
        text=text,
        reply_markup=kb,
        parse_mode="HTML",
    )
    await call.answer()


# ==================== ВЫВОД ====================
@dp.callback_query(F.data == "withdraw")
async def cb_withdraw(call: types.CallbackQuery, state: FSMContext) -> None:
    await state.set_state(WithdrawStates.waiting_for_amount)

    text = (
        f"💸 <b>Вывод звёзд</b>\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"Минимальная сумма: <b>{MIN_WITHDRAW} ⭐</b>\n\n"
        f"Введите количество звёзд для вывода:"
    )

    try:
        await call.message.delete()
    except Exception:
        pass

    await bot.send_message(
        chat_id=call.from_user.id,
        text=text,
        reply_markup=back_keyboard(),
        parse_mode="HTML",
    )
    await call.answer()


@dp.message(WithdrawStates.waiting_for_amount)
async def process_withdraw(message: types.Message, state: FSMContext) -> None:
    user_id = str(message.from_user.id)
    ensure_user(user_id, message.from_user.username or f"User_{user_id[:6]}")

    try:
        amount = float(message.text.replace(",", ".").strip())
    except ValueError:
        await message.answer("❌ Введите число!", reply_markup=back_keyboard())
        return

    if amount < MIN_WITHDRAW:
        await message.answer(
            f"❌ Минимальный вывод — {MIN_WITHDRAW} ⭐",
            reply_markup=back_keyboard(),
        )
        return

    balance = data["users"][user_id].get("balance", 0.0)
    if balance < amount:
        await message.answer(
            "❌ Недостаточно средств!",
            reply_markup=back_keyboard(),
        )
        return

    data["users"][user_id]["balance"] = balance - amount
    save_data(data)

    try:
        await bot.send_message(
            SUPPORT_ID,
            f"💰 <b>Заявка на вывод</b>\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"👤 Пользователь: {message.from_user.full_name}\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"⭐ Сумма: <code>{amount:.2f}</code>\n"
            f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"Не удалось отправить заявку саппорту: {e}")

    await message.answer(
        f"✅ Заявка на <code>{amount:.2f} ⭐</code> отправлена!\n"
        f"Ожидайте обработки.",
        reply_markup=back_keyboard(),
        parse_mode="HTML",
    )
    await state.clear()


# ==================== ЛИДЕРЫ ====================
@dp.callback_query(F.data == "leaders")
async def cb_leaders(call: types.CallbackQuery) -> None:
    sorted_users = sorted(
        data["users"].items(),
        key=lambda x: x[1].get("refs", 0),
        reverse=True,
    )[:10]

    if not sorted_users or all(u[1].get("refs", 0) == 0 for u in sorted_users):
        text = (
            "🏆 <b>ТОП РЕФЕРАЛОВ</b>\n"
            "━━━━━━━━━━━━━━━━━\n"
            "Пока нет рефералов 😔"
        )
        kb = back_keyboard()
    else:
        medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
        lines = ["🏆 <b>ТОП РЕФЕРАЛОВ</b>\n━━━━━━━━━━━━━━━━━"]
        buttons = []

        for i, (uid, info) in enumerate(sorted_users):
            refs = info.get("refs", 0)
            if refs == 0:
                break
            username = info.get("username", f"User_{uid[:6]}")
            medal = medals[i] if i < len(medals) else "•"
            lines.append(f"{medal} <b>{username}</b> — {refs} реф.")
            buttons.append(
                [
                    InlineKeyboardButton(
                        text=f"{medal} {username}",
                        url=f"tg://user?id={uid}",
                    )
                ]
            )

        buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="menu")])
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        text = "\n".join(lines)

    try:
        await call.message.delete()
    except Exception:
        pass

    await bot.send_message(
        chat_id=call.from_user.id,
        text=text,
        reply_markup=kb,
        parse_mode="HTML",
    )
    await call.answer()


# ==================== ЗАПУСК ====================
async def main() -> None:
    logger.info("Запуск бота...")
    me = await bot.get_me()
    logger.info(f"Бот @{me.username} успешно запущен")

    try:
        await bot.set_my_description("💎 GiftsEzz Bot — рулетка, рефералы, вывод ⭐")
    except Exception as e:
        logger.warning(f"Не удалось установить описание: {e}")

    await dp.start_polling(bot)


if name == "main":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        raise
