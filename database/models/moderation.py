"""Модель очереди модерации"""
from sqlalchemy import Column, BigInteger, String, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from database.connection import Base


class ModerationStatus(str, enum.Enum):
    """Статус модерации"""
    PENDING = "pending"  # Ожидает модерации
    APPROVED = "approved"  # Одобрено
    REJECTED = "rejected"  # Отклонено


class ModerationQueue(Base):
    """Модель очереди модерации"""
    __tablename__ = "moderation_queue"
    
    id = Column(BigInteger, primary_key=True, index=True)
    product_id = Column(BigInteger, ForeignKey("products.id"), nullable=False, unique=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String(50), default=ModerationStatus.PENDING.value, nullable=False, index=True)
    moderator_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)  # ID модератора
    rejection_reason = Column(Text, nullable=True)  # Причина отклонения
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    moderated_at = Column(DateTime(timezone=True), nullable=True)
    
    # Связи
    product = relationship("Product", backref="moderation")
    user = relationship("User", foreign_keys=[user_id])
    moderator = relationship("User", foreign_keys=[moderator_id])

