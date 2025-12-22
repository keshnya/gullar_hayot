"""Главный файл бота"""
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from config import settings
from bot.handlers import start, main_menu, callbacks
from bot.middlewares.database import DatabaseMiddleware

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Запуск бота"""
    # Создаем бот и диспетчер
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()
    
    # Регистрируем middleware
    dp.message.middleware(DatabaseMiddleware())
    dp.callback_query.middleware(DatabaseMiddleware())
    
    # Регистрируем роутеры
    # Важно: publication.router должен быть ПЕРЕД callbacks.router,
    # чтобы обработчик publication_type из publication.py сработал первым
    from bot.handlers import auction, moderation, publication, sale, admin, payments
    dp.include_router(publication.router)  # Сначала публикация (FSM)
    dp.include_router(start.router)
    dp.include_router(main_menu.router)
    dp.include_router(admin.router)  # Админ команды
    dp.include_router(callbacks.router)  # Потом остальные callbacks
    dp.include_router(auction.router)
    dp.include_router(sale.router)
    dp.include_router(moderation.router)
    dp.include_router(payments.router)
    
    # Запускаем планировщик для завершения аукционов
    from services.scheduler import start_scheduler
    start_scheduler(bot)
    
    # Запускаем планировщик напоминаний о модерации
    from services.notifications import start_notification_scheduler
    start_notification_scheduler(bot)
    
    logger.info("Бот запущен")
    
    # Запускаем polling
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

