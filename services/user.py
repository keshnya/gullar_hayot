"""Сервис для работы с пользователями"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models.user import User


async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    username: str = None,
    first_name: str = None,
    last_name: str = None
) -> User:
    """Получить или создать пользователя"""
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    else:
        # Обновляем данные, если изменились
        if username != user.username or first_name != user.first_name:
            user.username = username
            user.first_name = first_name
            user.last_name = last_name
            await session.commit()
    
    return user


async def update_user_balance(
    session: AsyncSession,
    user_id: int,
    amount: int
) -> User:
    """Обновить баланс пользователя"""
    result = await session.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise ValueError("Пользователь не найден")
    
    user.balance += amount
    await session.commit()
    await session.refresh(user)
    return user

