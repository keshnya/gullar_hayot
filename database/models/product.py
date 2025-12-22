"""Модель товара"""
from sqlalchemy import Column, BigInteger, String, Text, Integer, DateTime, ForeignKey, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from database.connection import Base


class ProductType(str, enum.Enum):
    """Тип товара"""
    FLOWERS = "flowers"
    GIFT = "gift"
    OTHER = "other"


class Product(Base):
    """Модель товара"""
    __tablename__ = "products"
    
    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    product_type = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    photos = Column(Text, nullable=True)  # JSON массив путей к фото
    video = Column(String(500), nullable=True)  # Путь к видео
    price = Column(Integer, nullable=False)  # Цена в сумах
    contact_info = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Связи
    user = relationship("User", backref="products")
    auction = relationship("Auction", back_populates="product", uselist=False)
    regular_sale = relationship("RegularSale", back_populates="product", uselist=False)

