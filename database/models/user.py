"""Модель пользователя"""
from sqlalchemy import Column, BigInteger, String, DateTime, Boolean, Integer
from sqlalchemy.sql import func
from database.connection import Base


class User(Base):
    """Модель пользователя Telegram"""
    __tablename__ = "users"
    
    id = Column(BigInteger, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)
    contact_info = Column(String(500), nullable=True)
    balance = Column(Integer, default=0, nullable=False)  # Баланс в сумах
    publication_credits = Column(Integer, default=0, nullable=False)  # Количество доступных публикаций
    is_seller = Column(Boolean, default=False, nullable=False)
    is_moderator = Column(Boolean, default=False, nullable=False)  # Является ли модератором
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

