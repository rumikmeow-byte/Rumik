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

    # Если пользователя еще нет в базе — регистрируем
    if not user:
        await create_user(user_id, username, full_name, referred_by)
        
        # Начисляем бонус, ТОЛЬКО если это новый пользователь и указан валидный реферер
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
                except Exception as e:
                    logger.error(f"Failed to send referral reward notification: {e}")
        
        user = await get_user(user_id)
    else:
        # Если юзер уже был, но зашел по рефке впервые (и у него еще не было реферера)
        if referred_by and not user.get("referred_by") and user["user_id"] != referred_by:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("UPDATE users SET referred_by = ? WHERE user_id = ?", (referred_by, user_id))
                await db.commit()
            
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
                except Exception as e:
                    logger.error(f"Failed to send referral reward notification: {e}")

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
