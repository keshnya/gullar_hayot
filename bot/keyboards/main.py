"""Основные клавиатуры"""
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Главная клавиатура"""
    keyboard = [
        [KeyboardButton(text="➕ Товарный аукцион")],
        [KeyboardButton(text="➕ Выставить букет")],
        [KeyboardButton(text="🆔 Узнать свой ID")]
    ]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True
    )


def get_publication_type_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора типа публикации"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="📈 Создать аукцион",
        callback_data="publication_type:auction"
    ))
    builder.add(InlineKeyboardButton(
        text="🛍️ Обычная продажа",
        callback_data="publication_type:regular"
    ))
    return builder.as_markup()


def get_quantity_keyboard(quantity: int = 1) -> InlineKeyboardMarkup:
    """Клавиатура выбора количества публикаций"""
    keyboard = [
        [
            InlineKeyboardButton(text="-", callback_data=f"quantity:dec:{quantity}"),
            InlineKeyboardButton(text=str(quantity), callback_data="quantity:current"),
            InlineKeyboardButton(text="+", callback_data=f"quantity:inc:{quantity}")
        ],
        [
            InlineKeyboardButton(
                text="✏️ Указать своё число",
                callback_data="quantity:custom"
            )
        ],
        [
            InlineKeyboardButton(
                text="✅ Перейти к оплате",
                callback_data=f"payment:proceed:{quantity}"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_payment_method_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора способа оплаты"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="💳 Оплатить через Payme",
        callback_data="payment_method:payme"
    ))
    builder.add(InlineKeyboardButton(
        text="💳 Оплатить через Click",
        callback_data="payment_method:click"
    ))
    return builder.as_markup()

