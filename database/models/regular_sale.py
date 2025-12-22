"""Модель обычной продажи"""
from sqlalchemy import Column, BigInteger, Integer, DateTime, ForeignKey, Boolean, String
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from database.connection import Base


class SaleStatus(str, enum.Enum):
    """Статус продажи"""
    PENDING = "pending"  # Ожидает модерации
    ACTIVE = "active"  # Активна
    SOLD = "sold"  # Продана
    CANCELLED = "cancelled"  # Отменена


class RegularSale(Base):
    """Модель обычной продажи"""
    __tablename__ = "regular_sales"
    
    id = Column(BigInteger, primary_key=True, index=True)
    product_id = Column(BigInteger, ForeignKey("products.id"), unique=True, nullable=False, index=True)
    price = Column(Integer, nullable=False)  # Цена продажи
    buyer_id = Column(BigInteger, ForeignKey("users.id"), nullable=True, index=True)
    status = Column(String(50), default=SaleStatus.PENDING.value, nullable=False, index=True)
    channel_message_id = Column(BigInteger, nullable=True)  # ID сообщения в канале
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sold_at = Column(DateTime(timezone=True), nullable=True)
    
    # Связи
    product = relationship("Product", back_populates="regular_sale")
    buyer = relationship("User", foreign_keys=[buyer_id])

