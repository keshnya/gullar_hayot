"""Клавиатуры для админов и модераторов"""
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from bot.keyboards.main import get_main_keyboard


def get_moderator_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для модераторов (обычные кнопки + кнопка модерации)"""
    keyboard = [
        [KeyboardButton(text="➕ Товарный аукцион")],
        [KeyboardButton(text="💐 Выставить букет")],
        # [KeyboardButton(text="💰 Пополнить баланс")],  # Временно закомментировано
        # [KeyboardButton(text="📊 Мой профиль")],  # Временно закомментировано
        [KeyboardButton(text="🆔 Узнать свой ID")],
        [KeyboardButton(text="👮 Модерация")]  # Кнопка модерации
    ]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True
    )


def get_admin_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для админов (обычные кнопки + кнопки модерации и админ панели)"""
    keyboard = [
        [KeyboardButton(text="➕ Товарный аукцион")],
        [KeyboardButton(text="💐 Выставить букет")],
        # [KeyboardButton(text="💰 Пополнить баланс")],  # Временно закомментировано
        # [KeyboardButton(text="📊 Мой профиль")],  # Временно закомментировано
        [KeyboardButton(text="🆔 Узнать свой ID")],
        [KeyboardButton(text="👮 Модерация")],  # Кнопка модерации
        [KeyboardButton(text="📋 Админ панель")]  # Кнопка админ панели
    ]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True
    )

