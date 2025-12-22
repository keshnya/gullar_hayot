"""Подключение к базе данных"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from config import settings

# Создаем движок для асинхронной работы
engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True
)

# Создаем фабрику сессий
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Базовый класс для моделей
Base = declarative_base()


async def get_session() -> AsyncSession:
    """Получить сессию базы данных"""
    async with async_session_maker() as session:
        yield session

