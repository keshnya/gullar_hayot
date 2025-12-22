"""Сервис модерации"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from database.models.moderation import ModerationQueue, ModerationStatus
from database.models.auction import Auction, AuctionStatus
from database.models.regular_sale import RegularSale, SaleStatus
from datetime import datetime


async def add_to_moderation(
    session: AsyncSession,
    product_id: int,
    user_id: int
) -> ModerationQueue:
    """Добавить товар в очередь модерации"""
    # Проверяем, нет ли уже записи
    result = await session.execute(
        select(ModerationQueue).where(ModerationQueue.product_id == product_id)
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        return existing
    
    moderation = ModerationQueue(
        product_id=product_id,
        user_id=user_id,
        status=ModerationStatus.PENDING.value
    )
    session.add(moderation)
    await session.commit()
    await session.refresh(moderation)
    return moderation


async def approve_product(
    session: AsyncSession,
    product_id: int,
    moderator_id: int
) -> ModerationQueue:
    """Одобрить товар"""
    result = await session.execute(
        select(ModerationQueue).where(
            ModerationQueue.product_id == product_id,
            ModerationQueue.status == ModerationStatus.PENDING.value
        )
    )
    moderation = result.scalar_one_or_none()
    
    if not moderation:
        raise ValueError("Товар не найден в очереди модерации")
    
    # Обновляем статус модерации
    await session.execute(
        update(ModerationQueue)
        .where(ModerationQueue.id == moderation.id)
        .values(
            status=ModerationStatus.APPROVED.value,
            moderator_id=moderator_id,
            moderated_at=datetime.utcnow()
        )
    )
    
    # Активируем товар и связанный аукцион/продажу
    # (это будет сделано при публикации в канал)
    
    await session.commit()
    
    result = await session.execute(
        select(ModerationQueue).where(ModerationQueue.id == moderation.id)
    )
    return result.scalar_one()


async def reject_product(
    session: AsyncSession,
    product_id: int,
    moderator_id: int,
    reason: str
) -> ModerationQueue:
    """Отклонить товар"""
    result = await session.execute(
        select(ModerationQueue).where(
            ModerationQueue.product_id == product_id,
            ModerationQueue.status == ModerationStatus.PENDING.value
        )
    )
    moderation = result.scalar_one_or_none()
    
    if not moderation:
        raise ValueError("Товар не найден в очереди модерации")
    
    await session.execute(
        update(ModerationQueue)
        .where(ModerationQueue.id == moderation.id)
        .values(
            status=ModerationStatus.REJECTED.value,
            moderator_id=moderator_id,
            rejection_reason=reason,
            moderated_at=datetime.utcnow()
        )
    )
    
    await session.commit()
    
    result = await session.execute(
        select(ModerationQueue).where(ModerationQueue.id == moderation.id)
    )
    return result.scalar_one()


async def get_pending_moderations(session: AsyncSession) -> list[ModerationQueue]:
    """Получить товары, ожидающие модерации"""
    result = await session.execute(
        select(ModerationQueue)
        .where(ModerationQueue.status == ModerationStatus.PENDING.value)
        .order_by(ModerationQueue.created_at.asc())
    )
    return list(result.scalars().all())

