"""Сервис для работы с аукционами"""
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from database.models.auction import Auction, AuctionStatus
from database.models.bid import Bid
from database.models.product import Product
from config import settings


async def create_auction(
    session: AsyncSession,
    product_id: int,
    start_price: int
) -> Auction:
    """Создать аукцион"""
    auction = Auction(
        product_id=product_id,
        start_price=start_price,
        current_price=start_price,
        status=AuctionStatus.PENDING.value
    )
    session.add(auction)
    await session.commit()
    await session.refresh(auction)
    return auction


async def start_auction(
    session: AsyncSession,
    auction_id: int,
    channel_message_id: int
) -> Auction:
    """Запустить аукцион"""
    # Используем timezone-aware datetime с явным указанием UTC
    now = datetime.now(timezone.utc)
    ends_at = now + timedelta(hours=settings.AUCTION_DURATION_HOURS)
    
    await session.execute(
        update(Auction)
        .where(Auction.id == auction_id)
        .values(
            status=AuctionStatus.ACTIVE.value,
            started_at=now,
            ends_at=ends_at,
            channel_message_id=channel_message_id
        )
    )
    await session.commit()
    
    result = await session.execute(
        select(Auction).where(Auction.id == auction_id)
    )
    return result.scalar_one()


async def place_bid(
    session: AsyncSession,
    auction_id: int,
    user_id: int,
    amount: int
) -> Bid:
    """Сделать ставку"""
    # Проверяем, что аукцион активен
    result = await session.execute(
        select(Auction).where(
            Auction.id == auction_id,
            Auction.status == AuctionStatus.ACTIVE.value
        )
    )
    auction = result.scalar_one_or_none()
    
    if not auction:
        raise ValueError("Аукцион не найден или не активен")
    
    if amount <= auction.current_price:
        raise ValueError("Ставка должна быть выше текущей цены")
    
    # Проверяем, есть ли уже ставка от этого пользователя
    result = await session.execute(
        select(Bid).where(
            Bid.auction_id == auction_id,
            Bid.user_id == user_id
        ).order_by(Bid.amount.desc())
    )
    existing_bid = result.scalar_one_or_none()
    
    if existing_bid:
        # Если новая ставка выше предыдущей, обновляем существующую
        if amount > existing_bid.amount:
            await session.execute(
                update(Bid)
                .where(Bid.id == existing_bid.id)
                .values(amount=amount)
            )
            bid = existing_bid
            bid.amount = amount
        else:
            # Если новая ставка не выше, выбрасываем ошибку
            raise ValueError(f"Ваша новая ставка должна быть выше вашей предыдущей ставки ({existing_bid.amount:,} сум)")
    else:
        # Создаем новую ставку
        bid = Bid(
            auction_id=auction_id,
            user_id=user_id,
            amount=amount
        )
        session.add(bid)
    
    # Обновляем текущую цену аукциона и продлеваем время завершения на 2 часа от текущего момента
    # Используем timezone-aware datetime с явным указанием UTC
    now = datetime.now(timezone.utc)
    new_ends_at = now + timedelta(hours=settings.AUCTION_DURATION_HOURS)
    
    await session.execute(
        update(Auction)
        .where(Auction.id == auction_id)
        .values(
            current_price=amount,
            ends_at=new_ends_at
        )
    )
    
    await session.commit()
    await session.refresh(bid)
    return bid


async def finish_auction(
    session: AsyncSession,
    auction_id: int
) -> Auction:
    """Завершить аукцион и определить победителя"""
    result = await session.execute(
        select(Auction).where(Auction.id == auction_id)
    )
    auction = result.scalar_one_or_none()
    
    if not auction:
        raise ValueError("Аукцион не найден")
    
    # Находим выигрышную ставку
    result = await session.execute(
        select(Bid)
        .where(Bid.auction_id == auction_id)
        .order_by(Bid.amount.desc(), Bid.created_at.asc())
        .limit(1)
    )
    winning_bid = result.scalar_one_or_none()
    
    winner_id = winning_bid.user_id if winning_bid else None
    
    # Обновляем статус аукциона
    await session.execute(
        update(Auction)
        .where(Auction.id == auction_id)
        .values(
            status=AuctionStatus.FINISHED.value,
            winner_id=winner_id,
            finished_at=datetime.now(timezone.utc)
        )
    )
    
    if winning_bid:
        # Помечаем выигрышную ставку
        await session.execute(
            update(Bid)
            .where(Bid.id == winning_bid.id)
            .values(is_winning=True)
        )
    
    await session.commit()
    
    result = await session.execute(
        select(Auction).where(Auction.id == auction_id)
    )
    return result.scalar_one()


async def get_active_auctions(session: AsyncSession) -> list[Auction]:
    """Получить активные аукционы"""
    result = await session.execute(
        select(Auction)
        .where(Auction.status == AuctionStatus.ACTIVE.value)
        .order_by(Auction.ends_at.asc())
    )
    return list(result.scalars().all())

