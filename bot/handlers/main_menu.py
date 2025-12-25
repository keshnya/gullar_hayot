"""Обработчики главного меню"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from bot.keyboards.main import get_balance_keyboard
from database.models.user import User
from config import settings

router = Router()


@router.message(F.text == "🆔 Узнать свой ID")
async def get_user_id(message: Message, session: AsyncSession):
    """Получить ID пользователя"""
    from bot.keyboards.main import get_user_keyboard
    from bot.handlers.admin import is_admin_or_moderator
    from config import settings
    
    user_id = message.from_user.id
    is_admin = user_id in settings.admin_ids_list
    is_moderator = await is_admin_or_moderator(user_id, session)
    
    keyboard = await get_user_keyboard(user_id, session, is_admin, is_moderator)
    await message.answer(f"Ваш ID: `{user_id}`", parse_mode="Markdown", reply_markup=keyboard)


@router.message(F.text == "➕ Товарный аукцион")
async def start_auction_publication(message: Message, state: FSMContext, session: AsyncSession):
    """Начать процесс создания аукциона"""
    from services.user import get_or_create_user
    from bot.handlers.publication import PublicationStates
    from bot.keyboards.main import get_user_keyboard
    from bot.handlers.admin import is_admin_or_moderator
    
    # Получаем или создаем пользователя
    user = await get_or_create_user(
        session,
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
        message.from_user.last_name,
    )
    
    # Проверка доступных публикаций
    if user.publication_credits <= 0:
        from aiogram.types import InlineKeyboardButton
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        
        text = (
            "У Вас 0 доступных публикаций, пополните баланс, "
            "чтобы опубликовать аукцион."
        )
        
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(
                text="Пополнить баланс",
                callback_data="balance:topup:auction",
            )
        )
        
        user_id = message.from_user.id
        is_admin = user_id in settings.admin_ids_list
        is_moderator = await is_admin_or_moderator(user_id, session)
        reply_keyboard = await get_user_keyboard(user_id, session, is_admin, is_moderator)
        
        await message.answer(
            text,
            reply_markup=builder.as_markup(),
        )
        await message.answer("💡 Используйте кнопки ниже для навигации:", reply_markup=reply_keyboard)
        return
    
    # Показываем описание аукциона
    description_text = (
        "📈 <b>Создать аукцион</b>\n\n"
        "В данном случае, за Ваш букет буду сражаться покупатели в течении 2х часов, "
        "тот чья ставка окажется наивысшей побеждает.\n\n"
        "📝 Введите название товара:"
    )
    
    await state.update_data(publication_type="auction")
    await state.set_state(PublicationStates.waiting_title)
    
    user_id = message.from_user.id
    is_admin = user_id in settings.admin_ids_list
    is_moderator = await is_admin_or_moderator(user_id, session)
    reply_keyboard = await get_user_keyboard(user_id, session, is_admin, is_moderator)
    
    await message.answer(description_text, parse_mode="HTML", reply_markup=reply_keyboard)


@router.message(F.text == "💐 Выставить букет")
async def start_regular_sale_publication(message: Message, state: FSMContext, session: AsyncSession):
    """Начать процесс создания обычной продажи"""
    from services.user import get_or_create_user
    from bot.handlers.publication import PublicationStates
    from bot.keyboards.main import get_user_keyboard
    from bot.handlers.admin import is_admin_or_moderator
    
    # Получаем или создаем пользователя
    user = await get_or_create_user(
        session,
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
        message.from_user.last_name,
    )
    
    # Проверка доступных публикаций
    if user.publication_credits <= 0:
        from aiogram.types import InlineKeyboardButton
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        
        text = (
            "У Вас 0 доступных публикаций, пополните баланс, "
            "чтобы опубликовать обычную продажу."
        )
        
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(
                text="Пополнить баланс",
                callback_data="balance:topup:regular",
            )
        )
        
        user_id = message.from_user.id
        is_admin = user_id in settings.admin_ids_list
        is_moderator = await is_admin_or_moderator(user_id, session)
        reply_keyboard = await get_user_keyboard(user_id, session, is_admin, is_moderator)
        
        await message.answer(
            text,
            reply_markup=builder.as_markup(),
        )
        await message.answer("💡 Используйте кнопки ниже для навигации:", reply_markup=reply_keyboard)
        return
    
    # Показываем описание обычной продажи
    description_text = (
        "🛍️ <b>Обычная продажа</b>\n\n"
        "Тут Вы пишите желаемую цену, тот кого устраивает цена, дает о себе знать "
        "и бот пришлет Вам его контакты для связи.\n\n"
        "📝 Введите название товара:"
    )
    
    await state.update_data(publication_type="regular")
    await state.set_state(PublicationStates.waiting_title)
    
    user_id = message.from_user.id
    is_admin = user_id in settings.admin_ids_list
    is_moderator = await is_admin_or_moderator(user_id, session)
    reply_keyboard = await get_user_keyboard(user_id, session, is_admin, is_moderator)
    
    await message.answer(description_text, parse_mode="HTML", reply_markup=reply_keyboard)


@router.message(F.text == "💰 Баланс")
async def show_balance_menu(message: Message, session: AsyncSession):
    """Показать меню баланса"""
    from bot.keyboards.main import get_user_keyboard
    from bot.handlers.admin import is_admin_or_moderator
    from config import settings
    
    result = await session.execute(
        select(User).where(User.telegram_id == message.from_user.id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        await message.answer("Пользователь не найден. Используйте /start")
        return
    
    user_id = message.from_user.id
    is_admin = user_id in settings.admin_ids_list
    is_moderator = await is_admin_or_moderator(user_id, session)
    reply_keyboard = await get_user_keyboard(user_id, session, is_admin, is_moderator)
    
    text = (
        "💰 <b>Баланс</b>\n\n"
        f"📊 Доступно публикаций: <b>{user.publication_credits or 0}</b>\n\n"
        "Выберите действие:"
    )
    
    await message.answer(
        text,
        reply_markup=get_balance_keyboard(),
        parse_mode="HTML"
    )
    
    # Отправляем reply-клавиатуру отдельным сообщением, чтобы она всегда была видна
    await message.answer("💡 Используйте кнопки ниже для навигации:", reply_markup=reply_keyboard)


@router.callback_query(F.data == "balance:check")
async def check_balance(callback: CallbackQuery, session: AsyncSession):
    """Проверить баланс"""
    result = await session.execute(
        select(User).where(User.telegram_id == callback.from_user.id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        await callback.answer("Пользователь не найден", show_alert=True)
        return
    
    text = (
        "💰 <b>Ваш баланс</b>\n\n"
        f"📊 Доступно публикаций: <b>{user.publication_credits or 0}</b>\n\n"
        "1 публикация = 30 000 сум"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_balance_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "balance:topup:menu")
async def topup_balance_menu(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Пополнение баланса: покупка публикаций"""
    from bot.handlers.payments import (
        PaymentStates,
        _build_publication_count_text,
        _get_publication_count_keyboard,
    )

    result = await session.execute(
        select(User).where(User.telegram_id == callback.from_user.id)
    )
    user = result.scalar_one_or_none()

    if not user:
        await callback.answer("Пользователь не найден", show_alert=True)
        return

    await state.update_data(
        payment_publication_type="auction",
        payment_count=1,
        payment_unit_price=30000,
    )
    await state.set_state(PaymentStates.waiting_publication_count)

    text = _build_publication_count_text(1)
    keyboard = _get_publication_count_keyboard(1)

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


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

