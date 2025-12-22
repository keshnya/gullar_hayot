"""Планировщик задач для завершения аукционов"""
import asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.connection import async_session_maker
from database.models.auction import Auction, AuctionStatus
from services.auction import finish_auction, get_active_auctions
from services.channel import get_auction_status_text, send_contacts_after_auction
from config import settings
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import logging

logger = logging.getLogger(__name__)


async def check_and_finish_auctions(bot: Bot):
    """Проверить и завершить истекшие аукционы"""
    async with async_session_maker() as session:
        now = datetime.now(timezone.utc)
        
        result = await session.execute(
            select(Auction).where(
                Auction.status == AuctionStatus.ACTIVE.value,
                Auction.ends_at <= now
            )
        )
        expired_auctions = result.scalars().all()
        
        for auction in expired_auctions:
            try:
                # Сохраняем ID сообщения перед завершением
                channel_message_id = auction.channel_message_id
                
                finished_auction = await finish_auction(session, auction.id)
                logger.info(f"Аукцион {auction.id} завершен. Победитель: {finished_auction.winner_id}")
                
                # Обновляем сообщение в канале
                if channel_message_id:
                    try:
                        status_text = await get_auction_status_text(session, finished_auction.id)
                        await bot.edit_message_text(
                            chat_id=settings.CHANNEL_ID,
                            message_id=channel_message_id,
                            text=status_text,
                            reply_markup=None,  # Убираем кнопку для завершенных аукционов
                            parse_mode="HTML",
                        )
                        logger.info(f"Сообщение в канале обновлено для аукциона {finished_auction.id}")
                    except Exception as e:
                        logger.error(f"Ошибка при обновлении сообщения в канале для аукциона {finished_auction.id}: {e}")
                
                # Сразу после завершения аукциона отправляем контакты победителю и продавцу
                try:
                    await send_contacts_after_auction(bot, session, finished_auction.id)
                except Exception as e:
                    logger.error(f"Ошибка при отправке контактов для аукциона {finished_auction.id}: {e}")
            
            except Exception as e:
                logger.error(f"Ошибка при завершении аукциона {auction.id}: {e}")


async def update_active_auctions_messages(bot: Bot):
    """Обновить сообщения в канале для всех активных аукционов"""
    async with async_session_maker() as session:
        try:
            active_auctions = await get_active_auctions(session)
            
            if not active_auctions:
                logger.debug("Нет активных аукционов для обновления")
                return
            
            logger.info(f"Начинаю обновление сообщений для {len(active_auctions)} активных аукционов")
            updated_count = 0
            
            for auction in active_auctions:
                if not auction.channel_message_id:
                    continue
                
                # Обновляем данные аукциона из базы, чтобы получить актуальные ends_at и current_price
                await session.refresh(auction)
                
                try:
                    # Получаем обновленный текст
                    status_text = await get_auction_status_text(session, auction.id)
                    
                    # Логируем информацию для отладки
                    now = datetime.now(timezone.utc)
                    time_info = ""
                    if auction.ends_at:
                        if auction.ends_at.tzinfo is None:
                            ends_at = auction.ends_at.replace(tzinfo=timezone.utc)
                        else:
                            ends_at = auction.ends_at.astimezone(timezone.utc)
                        delta = ends_at - now
                        hours = int(delta.total_seconds()) // 3600
                        minutes = (int(delta.total_seconds()) % 3600) // 60
                        time_info = f"ends_at={ends_at}, now={now}, осталось={hours}ч {minutes}м"
                    else:
                        time_info = "ends_at=None"
                    
                    logger.debug(f"Аукцион {auction.id}: {time_info}")
                    logger.debug(f"Аукцион {auction.id}: длина текста={len(status_text)}")
                    
                    # Создаем клавиатуру только для активных аукционов
                    bot_info = await bot.get_me()
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
                    
                    # Обновляем сообщение в канале
                    await bot.edit_message_text(
                        chat_id=settings.CHANNEL_ID,
                        message_id=auction.channel_message_id,
                        text=status_text,
                        reply_markup=keyboard,
                        parse_mode="HTML",
                    )
                    updated_count += 1
                    logger.info(f"Сообщение обновлено для аукциона {auction.id}")
                except Exception as e:
                    error_msg = str(e).lower()
                    # Игнорируем ошибку "message is not modified"
                    if "message is not modified" in error_msg:
                        logger.debug(f"Сообщение для аукциона {auction.id} не изменилось (это нормально)")
                    else:
                        logger.warning(
                            f"Не удалось обновить сообщение для аукциона {auction.id}: {e!r}"
                        )
                        logger.debug(f"Текст сообщения (первые 200 символов): {status_text[:200]}")
            
            logger.info(f"Обновление завершено: обновлено {updated_count} из {len(active_auctions)} аукционов")
        except Exception as e:
            logger.error(f"Ошибка при обновлении сообщений аукционов: {e}")


async def scheduler_loop(bot: Bot):
    """Основной цикл планировщика"""
    # Счетчик минут для периодического обновления
    minutes_passed = 0
    
    while True:
        try:
            # Проверяем завершенные аукционы каждую минуту
            await check_and_finish_auctions(bot)
            
            # Обновляем все активные аукционы каждые 15 минут
            if minutes_passed >= 15:
                logger.info("Запуск периодического обновления сообщений аукционов (каждые 15 минут)")
                await update_active_auctions_messages(bot)
                minutes_passed = 0
            
            minutes_passed += 1
            
        except Exception as e:
            logger.error(f"Ошибка в планировщике: {e}")
        
        # Проверяем каждую минуту
        await asyncio.sleep(60)


def start_scheduler(bot: Bot):
    """Запустить планировщик"""
    asyncio.create_task(scheduler_loop(bot))
    logger.info("Планировщик аукционов запущен")

