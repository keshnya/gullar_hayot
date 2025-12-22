"""Модель аукциона"""
from sqlalchemy import Column, BigInteger, Integer, DateTime, ForeignKey, Boolean, String
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from database.connection import Base


class AuctionStatus(str, enum.Enum):
    """Статус аукциона"""
    PENDING = "pending"  # Ожидает модерации
    ACTIVE = "active"  # Активный
    FINISHED = "finished"  # Завершен
    CANCELLED = "cancelled"  # Отменен


class Auction(Base):
    """Модель аукциона"""
    __tablename__ = "auctions"
    
    id = Column(BigInteger, primary_key=True, index=True)
    product_id = Column(BigInteger, ForeignKey("products.id"), unique=True, nullable=False, index=True)
    start_price = Column(Integer, nullable=False)  # Начальная цена
    current_price = Column(Integer, nullable=False)  # Текущая цена
    winner_id = Column(BigInteger, ForeignKey("users.id"), nullable=True, index=True)
    status = Column(String(50), default=AuctionStatus.PENDING.value, nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    ends_at = Column(DateTime(timezone=True), nullable=True, index=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    channel_message_id = Column(BigInteger, nullable=True)  # ID сообщения в канале
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Связи
    product = relationship("Product", back_populates="auction")
    winner = relationship("User", foreign_keys=[winner_id])
    bids = relationship("Bid", back_populates="auction", order_by="Bid.created_at.desc()")

