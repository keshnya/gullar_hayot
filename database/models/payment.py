"""Модель платежа"""
from sqlalchemy import Column, BigInteger, Integer, DateTime, ForeignKey, String, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from database.connection import Base


class PaymentStatus(str, enum.Enum):
    """Статус платежа"""
    PENDING = "pending"  # Ожидает оплаты
    COMPLETED = "completed"  # Оплачен
    FAILED = "failed"  # Неудачный
    CANCELLED = "cancelled"  # Отменен


class PaymentType(str, enum.Enum):
    """Тип платежа"""
    BALANCE_TOPUP = "balance_topup"  # Пополнение баланса
    PUBLICATION = "publication"  # Публикация товара


class PaymentProvider(str, enum.Enum):
    """Провайдер платежа"""
    PAYME = "payme"
    CLICK = "click"


class Payment(Base):
    """Модель платежа"""
    __tablename__ = "payments"
    
    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    amount = Column(Integer, nullable=False)  # Сумма в сумах
    payment_type = Column(String(50), nullable=False, index=True)
    provider = Column(String(50), nullable=False)
    status = Column(String(50), default=PaymentStatus.PENDING.value, nullable=False, index=True)
    transaction_id = Column(String(255), unique=True, nullable=True, index=True)  # ID транзакции от провайдера
    external_id = Column(String(255), nullable=True)  # Внешний ID для связи с товаром/публикацией
    payment_metadata = Column(String(1000), nullable=True)  # Дополнительные данные (JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Связи
    user = relationship("User", backref="payments")

