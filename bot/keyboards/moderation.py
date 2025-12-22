"""Клавиатуры для модерации"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_moderation_keyboard(product_id: int) -> InlineKeyboardMarkup:
    """Клавиатура модерации товара"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="✅ Одобрить",
        callback_data=f"moderation:approve:{product_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="❌ Отклонить",
        callback_data=f"moderation:reject:{product_id}"
    ))
    builder.row()
    builder.add(InlineKeyboardButton(
        text="👁️ Просмотр товара",
        callback_data=f"moderation:view:{product_id}"
    ))
    return builder.as_markup()

