"""Сервис для публикации товаров в Telegram канал"""
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database.models.product import Product, ProductType
from database.models.auction import Auction, AuctionStatus
from database.models.regular_sale import RegularSale, SaleStatus
from database.models.user import User
from database.models.bid import Bid
from services.auction import start_auction
from datetime import datetime, timedelta, timezone
from config import settings
import json
import logging

logger = logging.getLogger(__name__)

# Фиксированный часовой пояс Ташкента (UTC+5)
TASHKENT_TZ = timezone(timedelta(hours=5))


def _parse_description_fields(description: str) -> dict:
    """Парсит описание и достаёт город/размер/свежесть"""
    result: dict[str, str] = {}
    if not description:
        return result
    
    lines = description.split("\n")
    for line in lines:
        line = line.strip()
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        if "город" in key:
            result["city"] = value
        elif "размер" in key:
            result["size"] = value
        elif "свежесть" in key or "износ" in key:
            result["freshness"] = value
    return result


def _format_auction_status_text(
    city: str | None,
    size: str | None,
    freshness: str | None,
    price: int,
    bids_count: int,
    time_left: str,
    is_finished: bool = False,
) -> str:
    """Формирует текст статуса аукциона для сообщения в канале"""
    lines: list[str] = []
    # Убираем city, size, freshness из статуса, так как они уже есть в описании
    # Оставляем только цену, количество ставок и время
    lines.append(f"Цена: {price:,} сум")
    if is_finished:
        lines.append(f"👥 Было ставок: {bids_count}")
    else:
        lines.append(f"👥 Кол-во ставок: {bids_count}")
        if time_left:
            lines.append(f"⏳ До завершения: {time_left}")
    return "\n".join(lines)


async def get_auction_status_text(
    session: AsyncSession,
    auction_id: int,
) -> str:
    """Построить ПОЛНЫЙ текст аукциона для канала (описание + статус)"""
    result = await session.execute(
        select(Auction, Product, User)
        .join(Product, Product.id == Auction.product_id)
        .join(User, Product.user_id == User.id)
        .where(Auction.id == auction_id)
    )
    data = result.first()
    if not data:
        return "Аукцион не найден"
    
    auction, product, user = data
    
    # Перезагружаем аукцион отдельным запросом для получения актуальных ends_at и current_price
    # (данные из join могут быть устаревшими)
    result = await session.execute(
        select(Auction).where(Auction.id == auction_id)
    )
    auction = result.scalar_one()
    
    desc_data = _parse_description_fields(product.description or "")
    
    # Кол-во ставок
    bids_result = await session.execute(
        select(func.count(Bid.id)).where(Bid.auction_id == auction_id)
    )
    bids_count = bids_result.scalar_one() or 0
    
    # Проверяем статус аукциона
    is_finished = auction.status == AuctionStatus.FINISHED.value
    
    # Время до завершения: используем ends_at напрямую
    # Используем timezone-aware datetime для правильного сравнения
    from datetime import timezone as tz
    now = datetime.now(tz.utc)
    time_left = "0м"
    
    if not is_finished and auction.ends_at:
        # ends_at из базы данных должен быть timezone-aware (TIMESTAMP WITH TIME ZONE)
        ends_at = auction.ends_at
        
        # Если ends_at naive (старые записи), считаем что это UTC
        if ends_at.tzinfo is None:
            ends_at = ends_at.replace(tzinfo=tz.utc)
        # Если ends_at в другом timezone, конвертируем в UTC
        elif ends_at.tzinfo != tz.utc:
            ends_at = ends_at.astimezone(tz.utc)
        
        if ends_at > now:
            delta = ends_at - now
            total_seconds = int(delta.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            if hours > 0:
                time_left = f"{hours}ч {minutes}м"
            else:
                time_left = f"{minutes}м"
            # Логируем для отладки
            logger.debug(f"Аукцион {auction_id}: ends_at={ends_at}, now={now}, time_left={time_left}")
        else:
            logger.warning(f"Аукцион {auction_id}: ends_at уже прошел! ends_at={ends_at}, now={now}")
            time_left = "0м"
    
    # Основная часть текста (как при первоначальной публикации)
    product_type_names = {
        "flowers": "🌹 Цветы",
        "gift": "🎁 Подарок",
        "other": "📦 Другое",
    }
    
    # Конвертируем время завершения из UTC в локальное (Ташкент, UTC+5)
    if auction.ends_at:
        # Если ends_at naive, считаем что это UTC
        if auction.ends_at.tzinfo is None:
            ends_at_utc = auction.ends_at.replace(tzinfo=timezone.utc)
        else:
            # Нормализуем к UTC
            ends_at_utc = auction.ends_at.astimezone(timezone.utc)
        ends_at_local = ends_at_utc.astimezone(TASHKENT_TZ)
        ends_at_str = ends_at_local.strftime("%d.%m.%Y %H:%M")
    else:
        ends_at_str = "Не указано"
    
    # Если аукцион завершен, показываем специальный текст (без описания, контактов и продавца)
    if is_finished:
        text = (
            f"🤝 <b>Букет Продан</b> 🤝\n\n"
            f"📦 <b>{product.title}</b>\n\n"
            f"Тип: {product_type_names.get(product.product_type, product.product_type)}\n"
            f"Начальная цена: <b>{auction.start_price:,} сум</b>\n"
            f"Финальная цена: <b>{auction.current_price:,} сум</b>\n\n"
        )
    else:
        text = (
            f"📦 <b>{product.title}</b>\n\n"
            f"Тип: {product_type_names.get(product.product_type, product.product_type)}\n"
            f"Начальная цена: <b>{auction.start_price:,} сум</b>\n"
            f"Текущая цена: <b>{auction.current_price:,} сум</b>\n"
            f"⏰ Аукцион завершится: {ends_at_str}\n\n"
        )
        
        # Описание показываем только для активных аукционов
        if product.description:
            text += f"{product.description}\n"
    
    # Блок статуса (город/размер/свежесть, ставки, время)
    if is_finished:
        # Для завершенных аукционов показываем "Было ставок"
        status_block = _format_auction_status_text(
            city=desc_data.get("city"),
            size=desc_data.get("size"),
            freshness=desc_data.get("freshness"),
            price=auction.start_price,
            bids_count=bids_count,
            time_left="",  # Не показываем время для завершенных
            is_finished=True
        )
    else:
        status_block = _format_auction_status_text(
            city=desc_data.get("city"),
            size=desc_data.get("size"),
            freshness=desc_data.get("freshness"),
            price=auction.current_price,  # Используем текущую цену, а не начальную
            bids_count=bids_count,
            time_left=time_left,
            is_finished=False
        )
    
    return f"{text}\n{status_block}"


async def publish_auction_to_channel(
    bot: Bot,
    session: AsyncSession,
    product_id: int
) -> int:
    """Опубликовать аукцион в канал"""
    # Получаем товар и аукцион
    result = await session.execute(
        select(Product, Auction, User)
        .join(Auction, Product.id == Auction.product_id)
        .join(User, Product.user_id == User.id)
        .where(Product.id == product_id)
    )
    data = result.first()
    
    if not data:
        raise ValueError("Товар или аукцион не найден")
    
    product, auction, user = data
    
    # Формируем текст сообщения
    product_type_names = {
        "flowers": "🌹 Цветы",
        "gift": "🎁 Подарок",
        "other": "📦 Другое"
    }
    
    # Время окончания аукциона считаем в UTC и отображаем в Ташкенте (UTC+5)
    ends_at_utc = datetime.now(timezone.utc) + timedelta(hours=settings.AUCTION_DURATION_HOURS)
    ends_at_local = ends_at_utc.astimezone(TASHKENT_TZ)
    # Формат даты: день.месяц.год часы:минуты
    ends_at_str = ends_at_local.strftime("%d.%m.%Y %H:%M")
    
    text = (
        f"📦 <b>{product.title}</b>\n\n"
        f"Тип: {product_type_names.get(product.product_type, product.product_type)}\n"
        f"Начальная цена: <b>{auction.start_price:,} сум</b>\n"
        f"Текущая цена: <b>{auction.current_price:,} сум</b>\n"
        f"⏰ Аукцион завершится: {ends_at_str}\n\n"
    )
    
    if product.description:
        text += f"{product.description}\n"
    
    # Загружаем фото
    photos = json.loads(product.photos) if product.photos else []
    media_group = []
    
    # Получаем username бота для deep-link
    bot_info = await bot.get_me()
    bot_username = bot_info.username
    
    # Создаем клавиатуру для ставок - deep-link вместо callback
    deep_link_url = f"https://t.me/{bot_username}?start=auction_{auction.id}"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Участвовать в аукционе",
                url=deep_link_url
            )
        ]
    ])
    
    # Текст статуса (город/размер/свежесть, ставки, время)
    desc_data = _parse_description_fields(product.description or "")
    # При публикации ещё нет ставок
    initial_bids_count = 0
    # До завершения — полное время аукциона
    duration_hours = settings.AUCTION_DURATION_HOURS
    if duration_hours < 1:
        # Если меньше часа, показываем минуты
        minutes = int(duration_hours * 60)
        time_left_initial = f"{minutes}м"
    else:
        hours = int(duration_hours)
        minutes = int((duration_hours - hours) * 60)
        time_left_initial = f"{hours}ч {minutes}м"
    status_text = _format_auction_status_text(
        city=desc_data.get("city"),
        size=desc_data.get("size"),
        freshness=desc_data.get("freshness"),
        price=auction.start_price,
        bids_count=initial_bids_count,
        time_left=time_left_initial,
    )
    
    # Общий текст: основное описание + блок статуса
    full_text = f"{text}\n\n{status_text}"

    if photos:
        # На канал сначала отправляем только фото (без описания),
        # а текст + кнопка идут отдельным сообщением ниже
        for photo_id in photos[:10]:  # Telegram позволяет до 10 фото в группе
            media_group.append({
                "type": "photo",
                "media": photo_id,
            })
        
        # Публикуем в канал
        # Если есть фото, отправляем медиа-группу
        await bot.send_media_group(
            chat_id=settings.CHANNEL_ID,
            media=media_group
        )
        # Отправляем отдельное сообщение с кнопкой и полным текстом (описание + статус)
        message = await bot.send_message(
            chat_id=settings.CHANNEL_ID,
            text=full_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        channel_message_id = message.message_id
    else:
        # Если нет фото, отправляем текстовое сообщение (описание + статус)
        message = await bot.send_message(
            chat_id=settings.CHANNEL_ID,
            text=full_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        channel_message_id = message.message_id
    
    # Запускаем аукцион и сохраняем ID сообщения
    await start_auction(session, auction.id, channel_message_id)
    
    return channel_message_id


async def publish_sale_to_channel(
    bot: Bot,
    session: AsyncSession,
    product_id: int
) -> int:
    """Опубликовать обычную продажу в канал"""
    # Получаем товар и продажу
    result = await session.execute(
        select(Product, RegularSale, User)
        .join(RegularSale, Product.id == RegularSale.product_id)
        .join(User, Product.user_id == User.id)
        .where(Product.id == product_id)
    )
    data = result.first()
    
    if not data:
        raise ValueError("Товар или продажа не найдены")
    
    product, sale, user = data
    
    # Формируем текст сообщения
    product_type_names = {
        "flowers": "🌹 Цветы",
        "gift": "🎁 Подарок",
        "other": "📦 Другое"
    }
    
    text = (
        f"📦 <b>{product.title}</b>\n\n"
        f"Тип: {product_type_names.get(product.product_type, product.product_type)}\n"
        f"Цена: <b>{sale.price:,} сум</b>\n\n"
    )
    
    if product.description:
        text += f"{product.description}\n"
    
    text += f"📞 Контакты: {product.contact_info or 'Не указано'}\n"
    text += f"👤 Продавец: @{user.username if user.username else f'ID: {user.telegram_id}'}"
    
    # Загружаем фото
    photos = json.loads(product.photos) if product.photos else []
    media_group = []
    
    if photos:
        # Telegram ограничивает caption до 1024 символов
        caption_text = text
        if len(caption_text) > 1000:
            caption_text = caption_text[:1000] + "…"

        for i, photo_id in enumerate(photos[:10]):
            if i == 0:
                media_group.append({
                    "type": "photo",
                    "media": photo_id,
                    "caption": caption_text,
                    "parse_mode": "HTML"
                })
            else:
                media_group.append({
                    "type": "photo",
                    "media": photo_id
                })
    
    # Создаем клавиатуру для покупки
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🛒 Хочу купить",
                callback_data=f"sale:buy:{sale.id}"
            )
        ]
    ])
    
    # Публикуем в канал
    if media_group:
        # Если есть фото, отправляем медиа-группу
        messages = await bot.send_media_group(
            chat_id=settings.CHANNEL_ID,
            media=media_group
        )
        # Отправляем отдельное сообщение с кнопками
        message = await bot.send_message(
            chat_id=settings.CHANNEL_ID,
            text="🛒 <b>Хотите купить?</b>",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        channel_message_id = message.message_id
    else:
        # Если нет фото, отправляем текстовое сообщение
        message = await bot.send_message(
            chat_id=settings.CHANNEL_ID,
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        channel_message_id = message.message_id
    
    # Обновляем статус продажи, сохраняем ID сообщения и устанавливаем время истечения (24 часа)
    from sqlalchemy import update
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    await session.execute(
        update(RegularSale)
        .where(RegularSale.id == sale.id)
        .values(
            status=SaleStatus.ACTIVE.value,
            channel_message_id=channel_message_id,
            expires_at=expires_at
        )
    )
    await session.commit()
    
    return channel_message_id


async def send_contacts_after_auction(
    bot: Bot,
    session: AsyncSession,
    auction_id: int
) -> bool:
    """Отправить контакты победителю и продавцу после завершения аукциона."""
    try:
        # Получаем аукцион с товаром, победителем и продавцом
        result = await session.execute(
            select(Auction, Product, User)
            .join(Product, Product.id == Auction.product_id)
            .join(User, Product.user_id == User.id)
            .where(Auction.id == auction_id)
        )
        data = result.first()
        
        if not data:
            logger.error(f"Аукцион {auction_id} не найден")
            return False
        
        auction, product, seller = data
        
        # Проверяем, что аукцион завершен
        if auction.status != AuctionStatus.FINISHED.value:
            logger.warning(f"Аукцион {auction_id} не завершен, статус: {auction.status}")
            return False
        
        # Проверяем, что у аукциона есть время завершения
        if not auction.finished_at:
            logger.warning(f"Аукцион {auction_id} не имеет времени завершения")
            return False
        
        # Если нет победителя, не отправляем контакты
        if not auction.winner_id:
            logger.info(f"Аукцион {auction_id} завершен без победителя")
            return False
        
        # Получаем информацию о победителе
        result = await session.execute(
            select(User).where(User.id == auction.winner_id)
        )
        winner = result.scalar_one_or_none()
        
        if not winner:
            logger.error(f"Победитель {auction.winner_id} не найден")
            return False
        
        # Формируем контакты продавца
        seller_contact = ""
        if seller.phone:
            seller_contact += f"Телефон: {seller.phone}\n"
        if seller.username:
            seller_contact += f"Telegram: @{seller.username}"
        elif seller.telegram_id:
            seller_contact += f"Telegram ID: {seller.telegram_id}"
        if product.contact_info:
            seller_contact += f"\nДополнительно: {product.contact_info}"
        
        if not seller_contact.strip():
            seller_contact = "Контактная информация не указана"
        
        # Формируем контакты победителя
        winner_contact = ""
        if winner.phone:
            winner_contact += f"Телефон: {winner.phone}\n"
        if winner.username:
            winner_contact += f"Telegram: @{winner.username}"
        elif winner.telegram_id:
            winner_contact += f"Telegram ID: {winner.telegram_id}"
        if winner.contact_info:
            winner_contact += f"\nДополнительно: {winner.contact_info}"
        
        if not winner_contact.strip():
            winner_contact = "Контактная информация не указана"
        
        # Отправляем контакты победителю
        winner_message = (
            f"🎉 Поздравляем! Вы выиграли аукцион!\n\n"
            f"📦 Товар: <b>{product.title}</b>\n"
            f"💰 Финальная цена: <b>{auction.current_price:,} сум</b>\n\n"
            f"📞 <b>Контакты продавца:</b>\n{seller_contact}"
        )
        
        try:
            await bot.send_message(
                chat_id=winner.telegram_id,
                text=winner_message,
                parse_mode="HTML"
            )
            logger.info(f"Контакты продавца отправлены победителю {winner.telegram_id} для аукциона {auction_id}")
        except Exception as e:
            logger.error(f"Ошибка отправки контактов победителю {winner.telegram_id}: {e}")
        
        # Отправляем контакты продавцу
        seller_message = (
            f"✅ Ваш аукцион завершен!\n\n"
            f"📦 Товар: <b>{product.title}</b>\n"
            f"💰 Финальная цена: <b>{auction.current_price:,} сум</b>\n\n"
            f"👤 <b>Победитель:</b> @{winner.username if winner.username else f'ID: {winner.telegram_id}'}\n\n"
            f"📞 <b>Контакты победителя:</b>\n{winner_contact}"
        )
        
        try:
            await bot.send_message(
                chat_id=seller.telegram_id,
                text=seller_message,
                parse_mode="HTML"
            )
            logger.info(f"Контакты победителя отправлены продавцу {seller.telegram_id} для аукциона {auction_id}")
        except Exception as e:
            logger.error(f"Ошибка отправки контактов продавцу {seller.telegram_id}: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при отправке контактов для аукциона {auction_id}: {e}")
        return False

