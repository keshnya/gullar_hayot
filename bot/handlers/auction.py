"""Обработчики аукционов"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models.auction import Auction, AuctionStatus
from database.models.bid import Bid
from database.models.product import Product
from database.models.user import User
from services.auction import place_bid, get_active_auctions
from bot.keyboards.auction import get_auction_keyboard, get_bid_keyboard
from services.user import get_or_create_user
import json

router = Router()


class BidState(StatesGroup):
    """Состояния для ввода ставки"""
    waiting_amount = State()
    waiting_contact = State()  # Ожидание контакта для регистрации


async def _parse_product_description(description: str) -> dict:
    """Парсит описание товара и извлекает структурированные данные"""
    result = {}
    if not description:
        return result
    
    lines = description.split('\n')
    for line in lines:
        line = line.strip()
        if ':' in line:
            key, value = line.split(':', 1)
            key = key.strip().lower()
            value = value.strip()
            if 'город' in key:
                result['city'] = value
            elif 'свежесть' in key or 'износ' in key:
                result['freshness'] = value
            elif 'размер' in key:
                result['size'] = value
    return result


async def _get_bids_count_and_top(session: AsyncSession, auction_id: int) -> tuple[int, int]:
    """Получить количество ставок и топовую ставку"""
    result = await session.execute(
        select(Bid)
        .where(Bid.auction_id == auction_id)
        .order_by(Bid.amount.desc())
    )
    bids = list(result.scalars().all())
    count = len(bids)
    top_bid = bids[0].amount if bids else 0
    return count, top_bid


async def _send_product_to_user(
    bot,
    user_id: int,
    product: Product,
    auction: Auction,
    session: AsyncSession
):
    """Отправить товар пользователю в боте с фото/видео и новым форматом"""
    # Парсим описание
    desc_data = await _parse_product_description(product.description or "")
    
    # Получаем количество ставок и топовую ставку
    bids_count, top_bid = await _get_bids_count_and_top(session, auction.id)
    
    # Формируем текст в новом формате
    text_parts = []
    if desc_data.get('city'):
        text_parts.append(f"Город: {desc_data['city']}")
    if desc_data.get('freshness'):
        text_parts.append(f"Свежесть: {desc_data['freshness']}")
    text_parts.append(f"Изначальная Цена: {auction.start_price:,} сум")
    text_parts.append(f"👥 Кол-во ставок: {bids_count}")
    if top_bid > 0:
        text_parts.append(f"⚡️ Топовая ставка: {top_bid:,} сум")
    else:
        text_parts.append(f"⚡️ Топовая ставка: {auction.current_price:,} сум")
    
    text = "\n".join(text_parts)
    
    # Создаем клавиатуру с кнопками ставок
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    # Шаблонные кнопки добавляют +50 000 или +100 000 к текущей цене
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="+ 50 000 сум",
                    callback_data=f"bid:quick:{auction.id}:50000"
                )
            ],
            [
                InlineKeyboardButton(
                    text="+ 100 000 сум",
                    callback_data=f"bid:quick:{auction.id}:100000"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Ввести свою сумму",
                    callback_data=f"bid:custom:{auction.id}"
                )
            ]
        ]
    )
    
    # Отправляем фото/видео
    photos = json.loads(product.photos) if product.photos else []
    
    if photos:
        # Отправляем медиа-группу с фото
        media_group = []
        for i, photo_id in enumerate(photos[:10]):
            if i == 0:
                media_group.append({
                    "type": "photo",
                    "media": photo_id,
                    "caption": text[:1024] if len(text) <= 1024 else text[:1000] + "...",
                    "parse_mode": None
                })
            else:
                media_group.append({
                    "type": "photo",
                    "media": photo_id
                })
        
        try:
            await bot.send_media_group(chat_id=user_id, media=media_group)
            # Отправляем отдельное сообщение с кнопками
            await bot.send_message(chat_id=user_id, text="Выберите ставку:", reply_markup=keyboard)
        except Exception:
            # Если не получилось отправить медиа-группу, отправляем текстом
            await bot.send_message(chat_id=user_id, text=text, reply_markup=keyboard)
    elif product.video:
        # Если есть видео
        await bot.send_video(
            chat_id=user_id,
            video=product.video,
            caption=text[:1024] if len(text) <= 1024 else text[:1000] + "..."
        )
        # Отправляем отдельное сообщение с кнопками
        await bot.send_message(chat_id=user_id, text="Выберите ставку:", reply_markup=keyboard)
    else:
        # Только текст
        await bot.send_message(chat_id=user_id, text=text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("auction:participate:"))
async def start_auction_participation(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Начать участие в аукционе - показать товар и проверить регистрацию"""
    auction_id = int(callback.data.split(":")[2])
    
    result = await session.execute(
        select(Auction).where(Auction.id == auction_id)
    )
    auction = result.scalar_one_or_none()
    
    if not auction or auction.status != AuctionStatus.ACTIVE.value:
        await callback.answer("Аукцион не активен", show_alert=True)
        return
    
    result = await session.execute(
        select(Product).where(Product.id == auction.product_id)
    )
    product = result.scalar_one()
    
    # Получаем или создаем пользователя
    user = await get_or_create_user(
        session,
        callback.from_user.id,
        callback.from_user.username,
        callback.from_user.first_name,
        callback.from_user.last_name
    )
    
    # Проверяем регистрацию (есть ли телефон)
    if not user.phone:
        # Пользователь не зарегистрирован - просим контакт
        await state.update_data(auction_id=auction_id)
        await state.set_state(BidState.waiting_contact)
        
        from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
        
        contact_keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="📱 Поделиться контактом", request_contact=True)]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        
        try:
            await callback.bot.send_message(
                chat_id=callback.from_user.id,
                text="Чтобы воспользоваться сервисом, подключите свой номер телефона",
                reply_markup=contact_keyboard
            )
        except Exception:
            pass
        await callback.answer()
        return
    
    # Пользователь зарегистрирован - показываем товар и просим ставку
    await state.update_data(auction_id=auction_id)
    await state.set_state(BidState.waiting_amount)
    
    try:
        await _send_product_to_user(callback.bot, callback.from_user.id, product, auction, session)
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("bid:quick:"))
async def place_bid_quick(callback: CallbackQuery, session: AsyncSession):
    """Сделать ставку через быструю кнопку (50 000 или 100 000)"""
    parts = callback.data.split(":")
    auction_id = int(parts[2])
    increment = int(parts[3])
    
    # Получаем аукцион для проверки текущей цены
    result = await session.execute(
        select(Auction).where(Auction.id == auction_id)
    )
    auction = result.scalar_one_or_none()
    
    if not auction:
        await callback.answer("Аукцион не найден", show_alert=True)
        return
    
    # Новая ставка = текущая цена + приращение
    amount = auction.current_price + increment
    
    user = await get_or_create_user(
        session,
        callback.from_user.id,
        callback.from_user.username,
        callback.from_user.first_name,
        callback.from_user.last_name
    )
    
    try:
        bid = await place_bid(session, auction_id, user.id, amount)

        result = await session.execute(
            select(Auction).where(Auction.id == auction_id)
        )
        auction = result.scalar_one()

        # Обновляем статус сообщения в канале (кол-во ставок и время до конца)
        from services.channel import get_auction_status_text
        from config import settings
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        try:
            status_text = await get_auction_status_text(session, auction.id)
            if auction.channel_message_id:
                # Создаем клавиатуру только если аукцион активен
                keyboard = None
                if auction.status == AuctionStatus.ACTIVE.value:
                    bot_info = await callback.bot.get_me()
                    bot_username = bot_info.username
                    deep_link_url = f"https://t.me/{bot_username}?start=auction_{auction.id}"
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="Участвовать в аукционе",
                                url=deep_link_url
                            )
                        ]
                    ])
                
                await callback.bot.edit_message_text(
                    chat_id=settings.CHANNEL_ID,
                    message_id=auction.channel_message_id,
                    text=status_text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
        except Exception as e:
            print(
                f"[DEBUG] failed to update channel message after quick bid, "
                f"auction_id={auction.id}, msg_id={auction.channel_message_id}, error={e!r}"
            )

        # Получаем продавца лота
        product_result = await session.execute(
            select(Product, User)
            .join(User, Product.user_id == User.id)
            .where(Product.id == auction.product_id)
        )
        product_data = product_result.first()

        await callback.answer(f"Ставка {amount:,} сум принята! ✅")
        # Отправляем явное сообщение пользователю
        await callback.bot.send_message(
            chat_id=callback.from_user.id,
            text=(
                f"✅ Ваша ставка {amount:,} сум принята.\n"
                f"Текущая цена лота: {auction.current_price:,} сум."
            ),
        )

        if product_data:
            product, seller = product_data
            if seller.telegram_id:
                await callback.bot.send_message(
                    chat_id=seller.telegram_id,
                    text=(
                        "🔔 Новая ставка по вашему лоту!\n\n"
                        f"Товар: {product.title}\n"
                        f"Сумма ставки: {amount:,} сум\n"
                        f"Текущая цена: {auction.current_price:,} сум"
                    ),
                )
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
    except Exception as e:
        await callback.answer(f"Ошибка: {str(e)}", show_alert=True)


@router.callback_query(F.data.startswith("bid:amount:"))
async def place_bid_amount(callback: CallbackQuery, session: AsyncSession):
    """Сделать ставку на указанную сумму"""
    parts = callback.data.split(":")
    auction_id = int(parts[2])
    amount = int(parts[3])
    
    user = await get_or_create_user(
        session,
        callback.from_user.id,
        callback.from_user.username,
        callback.from_user.first_name,
        callback.from_user.last_name
    )
    
    try:
        bid = await place_bid(session, auction_id, user.id, amount)

        result = await session.execute(
            select(Auction).where(Auction.id == auction_id)
        )
        auction = result.scalar_one()

        # Обновляем статус сообщения в канале (кол-во ставок и время до конца)
        from services.channel import get_auction_status_text
        from config import settings
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        try:
            status_text = await get_auction_status_text(session, auction.id)
            if auction.channel_message_id:
                # Создаем клавиатуру только если аукцион активен
                keyboard = None
                if auction.status == AuctionStatus.ACTIVE.value:
                    bot_info = await callback.bot.get_me()
                    bot_username = bot_info.username
                    deep_link_url = f"https://t.me/{bot_username}?start=auction_{auction.id}"
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="Участвовать в аукционе",
                                url=deep_link_url
                            )
                        ]
                    ])
                
                await callback.bot.edit_message_text(
                    chat_id=settings.CHANNEL_ID,
                    message_id=auction.channel_message_id,
                    text=status_text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
        except Exception as e:
            print(
                f"[DEBUG] failed to update channel message after amount bid, "
                f"auction_id={auction.id}, msg_id={auction.channel_message_id}, error={e!r}"
            )

        # Получаем продавца лота
        product_result = await session.execute(
            select(Product, User)
            .join(User, Product.user_id == User.id)
            .where(Product.id == auction.product_id)
        )
        product_data = product_result.first()

        await callback.answer(f"Ставка {amount:,} сум принята! ✅")
        # Отправляем явное сообщение пользователю
        await callback.bot.send_message(
            chat_id=callback.from_user.id,
            text=(
                f"✅ Ваша ставка {amount:,} сум принята.\n"
                f"Текущая цена лота: {auction.current_price:,} сум."
            ),
        )

        if product_data:
            product, seller = product_data
            if seller.telegram_id:
                await callback.bot.send_message(
                    chat_id=seller.telegram_id,
                    text=(
                        "🔔 Новая ставка по вашему лоту!\n\n"
                        f"Товар: {product.title}\n"
                        f"Сумма ставки: {amount:,} сум\n"
                        f"Текущая цена: {auction.current_price:,} сум"
                    ),
                )
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
    except Exception as e:
        await callback.answer(f"Ошибка: {str(e)}", show_alert=True)


@router.callback_query(F.data.startswith("bid:custom:"))
async def bid_custom_amount(callback: CallbackQuery, state: FSMContext):
    """Запросить ввод своей суммы"""
    auction_id = int(callback.data.split(":")[2])
    
    await state.set_state(BidState.waiting_amount)
    await state.update_data(auction_id=auction_id)
    
    # Отправляем в личку пользователя, а не в канал
    await callback.bot.send_message(
        chat_id=callback.from_user.id,
        text="Введите сумму ставки (только число в сумах):"
    )
    await callback.answer()


@router.message(BidState.waiting_contact, F.contact)
async def process_contact_registration(message: Message, session: AsyncSession, state: FSMContext):
    """Обработка контакта для регистрации"""
    contact = message.contact
    
    # Получаем или создаем пользователя
    user = await get_or_create_user(
        session,
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
        message.from_user.last_name
    )
    
    # Сохраняем телефон
    if contact.phone_number:
        user.phone = contact.phone_number
        await session.commit()
    
    # Убираем клавиатуру
    from aiogram.types import ReplyKeyboardRemove
    await message.answer("✅ Регистрация завершена!", reply_markup=ReplyKeyboardRemove())
    
    # Получаем данные аукциона
    data = await state.get_data()
    auction_id = data.get("auction_id")
    
    if not auction_id:
        await message.answer("Ошибка: не найден ID аукциона")
        await state.clear()
        return
    
    # Получаем товар и аукцион
    result = await session.execute(
        select(Auction).where(Auction.id == auction_id)
    )
    auction = result.scalar_one_or_none()
    
    if not auction:
        await message.answer("Аукцион не найден")
        await state.clear()
        return
    
    result = await session.execute(
        select(Product).where(Product.id == auction.product_id)
    )
    product = result.scalar_one()
    
    # Показываем товар и просим ставку
    await state.set_state(BidState.waiting_amount)
    await _send_product_to_user(message.bot, message.from_user.id, product, auction, session)


@router.message(BidState.waiting_amount)
async def process_bid_amount(message: Message, session: AsyncSession, state: FSMContext):
    """Обработать введенную сумму ставки"""
    try:
        amount = int(message.text.replace(" ", "").replace(",", ""))
        
        if amount <= 0:
            await message.answer("Сумма должна быть положительным числом")
            return
        
        data = await state.get_data()
        auction_id = data.get("auction_id")
        
        if not auction_id:
            await message.answer("Ошибка: не найден ID аукциона")
            await state.clear()
            return
        
        # Получаем аукцион для проверки текущей цены
        result = await session.execute(
            select(Auction).where(Auction.id == auction_id)
        )
        auction = result.scalar_one_or_none()
        
        if not auction:
            await message.answer("Аукцион не найден")
            await state.clear()
            return
        
        # Проверяем, что ставка выше текущей цены
        if amount <= auction.current_price:
            await message.answer(
                f"Ставка не принята ☹️\n\n"
                f"Ваша ставка должна быть выше текущей цены: {auction.current_price:,} сум"
            )
            return
        
        user = await get_or_create_user(
            session,
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name
        )

        try:
            bid = await place_bid(session, auction_id, user.id, amount)

            # Обновляем аукцион после ставки
            result = await session.execute(
                select(Auction).where(Auction.id == auction_id)
            )
            auction = result.scalar_one()

            # Обновляем статус сообщения в канале (кол-во ставок и время до конца)
            from services.channel import get_auction_status_text
            from config import settings
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            try:
                status_text = await get_auction_status_text(session, auction.id)
                if auction.channel_message_id:
                    # Создаем клавиатуру только если аукцион активен
                    keyboard = None
                    if auction.status == AuctionStatus.ACTIVE.value:
                        bot_info = await message.bot.get_me()
                        bot_username = bot_info.username
                        deep_link_url = f"https://t.me/{bot_username}?start=auction_{auction.id}"
                        keyboard = InlineKeyboardMarkup(inline_keyboard=[
                            [
                                InlineKeyboardButton(
                                    text="Участвовать в аукционе",
                                    url=deep_link_url
                                )
                            ]
                        ])
                    
                    await message.bot.edit_message_text(
                        chat_id=settings.CHANNEL_ID,
                        message_id=auction.channel_message_id,
                        text=status_text,
                        reply_markup=keyboard,
                        parse_mode="HTML",
                    )
            except Exception as e:
                print(
                    f"[DEBUG] failed to update channel message after text bid, "
                    f"auction_id={auction.id}, msg_id={auction.channel_message_id}, error={e!r}"
                )

            # Получаем продавца лота
            product_result = await session.execute(
                select(Product, User)
                .join(User, Product.user_id == User.id)
                .where(Product.id == auction.product_id)
            )
            product_data = product_result.first()

            await message.answer(
                f"✅ Ваша ставка {amount:,} сум принята.\n"
                "Вы пока в лидерах."
            )

            if product_data:
                product, seller = product_data
                if seller.telegram_id:
                    await message.bot.send_message(
                        chat_id=seller.telegram_id,
                        text=(
                            "🔔 Новая ставка по вашему лоту!\n\n"
                            f"Товар: {product.title}\n"
                            f"Сумма ставки: {amount:,} сум\n"
                            f"Текущая цена: {auction.current_price:,} сум"
                        ),
                    )
        except ValueError as e:
            await message.answer(str(e))
        except Exception as e:
            await message.answer(f"Ошибка: {str(e)}")
        
        await state.clear()
        
    except ValueError:
        await message.answer("Пожалуйста, введите корректное число")


@router.callback_query(F.data.startswith("auction:bids:"))
async def view_bids_history(callback: CallbackQuery, session: AsyncSession):
    """Просмотр истории ставок"""
    auction_id = int(callback.data.split(":")[2])
    
    from database.models.user import User
    
    result = await session.execute(
        select(Bid, User)
        .join(User, Bid.user_id == User.id)
        .where(Bid.auction_id == auction_id)
        .order_by(Bid.created_at.desc())
        .limit(10)
    )
    bids_data = result.all()
    
    if not bids_data:
        await callback.answer("Ставок пока нет", show_alert=True)
        return
    
    text = "📊 История ставок (последние 10):\n\n"
    for i, (bid, user) in enumerate(bids_data, 1):
        username = f"@{user.username}" if user.username else f"ID: {user.telegram_id}"
        text += f"{i}. {bid.amount:,} сум от {username} - {bid.created_at.strftime('%H:%M:%S')}\n"
    
    # Отправляем в личку пользователя, а не в канал
    await callback.bot.send_message(
        chat_id=callback.from_user.id,
        text=text
    )
    await callback.answer()

