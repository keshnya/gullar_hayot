"""Модель ставки"""
from sqlalchemy import Column, BigInteger, Integer, DateTime, ForeignKey, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database.connection import Base


class Bid(Base):
    """Модель ставки на аукционе"""
    __tablename__ = "bids"
    
    id = Column(BigInteger, primary_key=True, index=True)
    auction_id = Column(BigInteger, ForeignKey("auctions.id"), nullable=False, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    amount = Column(Integer, nullable=False)  # Сумма ставки
    is_winning = Column(Boolean, default=False, nullable=False)  # Является ли выигрышной
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    # Связи
    auction = relationship("Auction", back_populates="bids")
    user = relationship("User", backref="bids")

