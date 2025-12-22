"""Сервис для отправки уведомлений админам"""
import asyncio
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database.connection import async_session_maker
from database.models.moderation import ModerationQueue, ModerationStatus
from config import settings
from aiogram import Bot
from database.models.user import User
from sqlalchemy import select
import logging

logger = logging.getLogger(__name__)


async def check_and_notify_pending_moderations(bot: Bot):
    """Проверить и уведомить админов о непромодерированных товарах"""
    async with async_session_maker() as session:
        # Получаем количество непромодерированных товаров
        result = await session.execute(
            select(func.count(ModerationQueue.id)).where(
                ModerationQueue.status == ModerationStatus.PENDING.value
            )
        )
        pending_count = result.scalar() or 0
        
        if pending_count == 0:
            return
        
        # Формируем сообщение
        text = (
            f"🔔 Напоминание о модерации\n\n"
            f"Товаров на модерации: <b>{pending_count}</b>\n\n"
            "Откройте меню бота и нажмите кнопку "
            "<b>👮 Модерация</b>, чтобы просмотреть и обработать товары."
        )
        
        # Получаем всех админов и модераторов
        admin_ids = list(settings.admin_ids_list)
        
        # Добавляем модераторов из БД
        async with async_session_maker() as mod_session:
            result = await mod_session.execute(
                select(User.telegram_id).where(User.is_moderator == True)
            )
            moderator_ids = [row[0] for row in result.all()]
        
        from bot.keyboards.admin import get_admin_keyboard, get_moderator_keyboard
        
        # Отправляем админам
        for admin_id in admin_ids:
            try:
                await bot.send_message(
                    admin_id,
                    text,
                    parse_mode="HTML",
                    reply_markup=get_admin_keyboard()
                )
            except Exception as e:
                logger.error(f"Ошибка отправки напоминания админу {admin_id}: {e}")
        
        # Отправляем модераторам
        for moderator_id in moderator_ids:
            try:
                await bot.send_message(
                    moderator_id,
                    text,
                    parse_mode="HTML",
                    reply_markup=get_moderator_keyboard()
                )
            except Exception as e:
                logger.error(f"Ошибка отправки напоминания модератору {moderator_id}: {e}")


async def notification_scheduler(bot: Bot):
    """Планировщик напоминаний о модерации"""
    while True:
        try:
            # Проверяем каждые 2 часа
            await check_and_notify_pending_moderations(bot)
        except Exception as e:
            logger.error(f"Ошибка в планировщике напоминаний: {e}")
        
        # Ждем 2 часа
        await asyncio.sleep(2 * 60 * 60)


def start_notification_scheduler(bot: Bot):
    """Запустить планировщик напоминаний"""
    asyncio.create_task(notification_scheduler(bot))
    logger.info("Планировщик напоминаний о модерации запущен")

