"""Модель интереса к покупке"""
from sqlalchemy import Column, BigInteger, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database.connection import Base


class SaleInterest(Base):
    """Модель для отслеживания интересов покупателей к продажам"""
    __tablename__ = "sale_interests"
    
    id = Column(BigInteger, primary_key=True, index=True)
    sale_id = Column(BigInteger, ForeignKey("regular_sales.id"), nullable=False, index=True)
    buyer_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Уникальное ограничение - один покупатель может нажать только 1 раз на продажу
    __table_args__ = (
        UniqueConstraint('sale_id', 'buyer_id', name='uq_sale_buyer'),
    )
    
    # Связи
    sale = relationship("RegularSale", backref="interests")
    buyer = relationship("User")

