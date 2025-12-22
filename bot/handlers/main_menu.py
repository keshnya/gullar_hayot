"""Обработчики главного меню"""
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from bot.keyboards.main import get_publication_type_keyboard
from config import settings

router = Router()


@router.message(F.text == "🆔 Узнать свой ID")
async def get_user_id(message: Message):
    """Получить ID пользователя"""
    user_id = message.from_user.id
    await message.answer(f"Ваш ID: `{user_id}`", parse_mode="Markdown")


@router.message(F.text.in_(["➕ Товарный аукцион", "💐 Выставить букет"]))
async def start_publication(message: Message):
    """Начать процесс публикации товара"""
    
    text = (
        "Пожалуйста выберите, как Вы хотите выставить товар? 👇\n\n"
        "1. Создать аукцион\n"
        "В данном случае, за Ваш букет буду сражаться покупатели в течении 2х часов, "
        "тот чья ставка окажется наивысшей побеждает\n\n"
        "2. Обычная продажа\n"
        "Тут Вы пишите желаемую цену, тот кого устраивает цена, дает о себе знать "
        "и бот пришлет Вам его контакты для связи."
    )
    
    await message.answer(
        text,
        reply_markup=get_publication_type_keyboard()
    )


# Временно закомментировано
# @router.message(F.text == "💰 Пополнить баланс")
# async def topup_balance(
#     message: Message,
#     state: FSMContext,
#     session: AsyncSession,
# ):
#     """Пополнение баланса: покупка публикаций"""
#     from sqlalchemy import select
#     from database.models.user import User
#     from bot.handlers.payments import (
#         PaymentStates,
#         _build_publication_count_text,
#         _get_publication_count_keyboard,
#     )
#
#     result = await session.execute(
#         select(User).where(User.telegram_id == message.from_user.id)
#     )
#     user = result.scalar_one_or_none()
#
#     if not user:
#         await message.answer("Пользователь не найден. Используйте /start")
#         return
#
#     await state.update_data(
#         payment_publication_type="auction",
#         payment_count=1,
#         payment_unit_price=30000,
#     )
#     await state.set_state(PaymentStates.waiting_publication_count)
#
#     text = _build_publication_count_text(1)
#     keyboard = _get_publication_count_keyboard(1)
#
#     await message.answer(text, reply_markup=keyboard)


# Временно закомментировано
# @router.message(F.text == "📊 Мой профиль")
# async def my_profile(message: Message, session: AsyncSession):
#     """Профиль пользователя"""
#     from sqlalchemy import select
#     from database.models.user import User
#     from bot.keyboards.main import get_main_keyboard
#     from bot.keyboards.admin import get_moderator_keyboard, get_admin_keyboard
#     from bot.handlers.admin import is_admin_or_moderator
#     from config import settings
#     
#     result = await session.execute(
#         select(User).where(User.telegram_id == message.from_user.id)
#     )
#     user = result.scalar_one_or_none()
#     
#     if not user:
#         await message.answer("Пользователь не найден. Используйте /start")
#         return
#     
#     text = (
#         f"📊 Ваш профиль\n\n"
#         f"ID: {user.telegram_id}\n"
#         f"Имя: {user.first_name or 'Не указано'}\n"
#         f"Username: @{user.username or 'Не указано'}\n"
#         f"Публикаций: {user.publication_credits}\n"
#         f"Статус продавца: {'✅ Да' if user.is_seller else '❌ Нет'}\n"
#         f"Контактные данные: {user.contact_info or 'Не указано'}"
#     )
#     
#     # Определяем клавиатуру в зависимости от прав
#     user_id = message.from_user.id
#     if user_id in settings.admin_ids_list:
#         # Админ - все кнопки + модерация + админ панель
#         await message.answer(text, reply_markup=get_admin_keyboard())
#     elif await is_admin_or_moderator(user_id, session):
#         # Модератор - все кнопки + модерация
#         await message.answer(text, reply_markup=get_moderator_keyboard())
#     else:
#         # Обычный пользователь - обычные кнопки
#         await message.answer(text, reply_markup=get_main_keyboard())

