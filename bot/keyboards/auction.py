"""Клавиатуры для аукционов"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_auction_keyboard(auction_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для аукциона"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="💰 Сделать ставку",
        callback_data=f"auction:bid:{auction_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="📊 История ставок",
        callback_data=f"auction:bids:{auction_id}"
    ))
    return builder.as_markup()


def get_bid_keyboard(auction_id: int, current_price: int) -> InlineKeyboardMarkup:
    """Клавиатура для ставки"""
    builder = InlineKeyboardBuilder()
    # Быстрые ставки: +10%, +20%, +50%
    step_10 = int(current_price * 0.1)
    step_20 = int(current_price * 0.2)
    step_50 = int(current_price * 0.5)
    
    builder.add(InlineKeyboardButton(
        text=f"+{step_10:,} сум",
        callback_data=f"bid:amount:{auction_id}:{current_price + step_10}"
    ))
    builder.add(InlineKeyboardButton(
        text=f"+{step_20:,} сум",
        callback_data=f"bid:amount:{auction_id}:{current_price + step_20}"
    ))
    builder.add(InlineKeyboardButton(
        text=f"+{step_50:,} сум",
        callback_data=f"bid:amount:{auction_id}:{current_price + step_50}"
    ))
    builder.add(InlineKeyboardButton(
        text="✏️ Указать свою сумму",
        callback_data=f"bid:custom:{auction_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="❌ Отмена",
        callback_data=f"bid:cancel:{auction_id}"
    ))
    # Каждая кнопка в своей строке
    builder.adjust(1)
    return builder.as_markup()
