"""Обработчики команды /start"""
from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models.user import User
from bot.keyboards.main import get_main_keyboard

router = Router()


class StartState(StatesGroup):
    """Состояния для регистрации при /start"""
    waiting_contact = State()


@router.message(Command("start"))
async def cmd_start(message: Message, session: AsyncSession, state: FSMContext):
    """Обработчик команды /start"""
    from config import settings
    from bot.keyboards.admin import get_admin_keyboard
    
    user_id = message.from_user.id
    
    # Проверяем параметры команды (deep-link)
    command_args = message.text.split()[1:] if len(message.text.split()) > 1 else []
    
    # Если есть параметр типа "auction_123", обрабатываем участие в аукционе
    if command_args and command_args[0].startswith("auction_"):
        try:
            auction_id = int(command_args[0].split("_")[1])
            # Обрабатываем участие в аукционе через deep-link
            await _handle_auction_deeplink(message, session, state, auction_id)
            return
        except (ValueError, IndexError):
            # Если параметр некорректный, продолжаем обычную обработку
            pass
    
    # Проверяем, есть ли пользователь в базе
    result = await session.execute(
        select(User).where(User.telegram_id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        # Создаем нового пользователя
        user = User(
            telegram_id=user_id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    
    # Проверяем наличие телефона
    if not user.phone:
        # Пользователь не зарегистрирован - просим контакт
        await state.set_state(StartState.waiting_contact)
        
        contact_keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="📱 Поделиться контактом", request_contact=True)]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        
        await message.answer(
            "Чтобы воспользоваться сервисом, подключите свой номер телефона",
            reply_markup=contact_keyboard
        )
        return
    
    # Пользователь зарегистрирован - показываем главное меню
    welcome_text = (
        "👋 Добро пожаловать в бот аукциона цветов и подарков!\n\n"
        "Выберите раздел:"
    )
    
    # Проверяем права и устанавливаем соответствующую клавиатуру
    from bot.keyboards.admin import get_moderator_keyboard, get_admin_keyboard
    from bot.handlers.admin import is_admin_or_moderator

    is_admin_env = user_id in settings.admin_ids_list
    is_moderator_db = await is_admin_or_moderator(user_id, session)

    if is_admin_env:
        # Админ - все кнопки + модерация + админ панель
        await message.answer(
            welcome_text,
            reply_markup=get_admin_keyboard()
        )
    elif is_moderator_db:
        # Модератор - все кнопки + модерация
        await message.answer(
            welcome_text,
            reply_markup=get_moderator_keyboard()
        )
    else:
        # Обычный пользователь - обычные кнопки
        await message.answer(
            welcome_text,
            reply_markup=get_main_keyboard()
        )


async def _handle_auction_deeplink(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    auction_id: int
):
    """Обработка deep-link для участия в аукционе"""
    from database.models.auction import Auction, AuctionStatus
    from database.models.product import Product
    from services.user import get_or_create_user
    from bot.handlers.auction import _send_product_to_user, BidState
    from sqlalchemy import select
    
    user_id = message.from_user.id
    
    # Получаем или создаем пользователя
    user = await get_or_create_user(
        session,
        user_id,
        message.from_user.username,
        message.from_user.first_name,
        message.from_user.last_name
    )
    
    # Проверяем наличие телефона
    if not user.phone:
        # Пользователь не зарегистрирован - просим контакт
        await state.update_data(auction_id=auction_id)
        await state.set_state(StartState.waiting_contact)
        
        contact_keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="📱 Поделиться контактом", request_contact=True)]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        
        await message.answer(
            "Чтобы воспользоваться сервисом, подключите свой номер телефона",
            reply_markup=contact_keyboard
        )
        return
    
    # Получаем аукцион
    result = await session.execute(
        select(Auction).where(Auction.id == auction_id)
    )
    auction = result.scalar_one_or_none()
    
    if not auction or auction.status != AuctionStatus.ACTIVE.value:
        await message.answer("Аукцион не активен")
        return
    
    # Получаем товар
    result = await session.execute(
        select(Product).where(Product.id == auction.product_id)
    )
    product = result.scalar_one()
    
    # Показываем товар и просим ставку
    await state.update_data(auction_id=auction_id)
    await state.set_state(BidState.waiting_amount)
    
    try:
        await _send_product_to_user(message.bot, user_id, product, auction, session)
    except Exception as e:
        await message.answer(f"Ошибка при отправке информации о товаре: {str(e)}")


@router.message(StartState.waiting_contact, F.contact)
async def process_start_contact(message: Message, session: AsyncSession, state: FSMContext):
    """Обработка контакта при команде /start"""
    contact = message.contact
    
    # Получаем пользователя
    result = await session.execute(
        select(User).where(User.telegram_id == message.from_user.id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        await message.answer("Ошибка: пользователь не найден")
        await state.clear()
        return
    
    # Сохраняем телефон
    if contact.phone_number:
        user.phone = contact.phone_number
        await session.commit()
    
    # Убираем клавиатуру
    await message.answer("✅ Регистрация завершена!", reply_markup=ReplyKeyboardRemove())
    
    # Проверяем, есть ли в состоянии auction_id (если пришли через deep-link)
    data = await state.get_data()
    auction_id = data.get("auction_id")
    
    if auction_id:
        # Если есть auction_id, обрабатываем участие в аукционе
        from database.models.auction import Auction, AuctionStatus
        from database.models.product import Product
        from bot.handlers.auction import _send_product_to_user, BidState
        
        # Получаем аукцион
        result = await session.execute(
            select(Auction).where(Auction.id == auction_id)
        )
        auction = result.scalar_one_or_none()
        
        if auction and auction.status == AuctionStatus.ACTIVE.value:
            # Получаем товар
            result = await session.execute(
                select(Product).where(Product.id == auction.product_id)
            )
            product = result.scalar_one()
            
            # Показываем товар и просим ставку
            await state.update_data(auction_id=auction_id)
            await state.set_state(BidState.waiting_amount)
            
            try:
                await _send_product_to_user(message.bot, message.from_user.id, product, auction, session)
            except Exception:
                await message.answer("Ошибка при отправке информации о товаре")
            return
    
    # Показываем главное меню
    welcome_text = (
        "👋 Добро пожаловать в бот аукциона цветов и подарков!\n\n"
        "Выберите раздел:"
    )
    
    from config import settings
    from bot.keyboards.admin import get_moderator_keyboard, get_admin_keyboard
    from bot.handlers.admin import is_admin_or_moderator
    
    user_id = message.from_user.id
    is_admin_env = user_id in settings.admin_ids_list
    is_moderator_db = await is_admin_or_moderator(user_id, session)

    if is_admin_env:
        # Админ - все кнопки + модерация + админ панель
        await message.answer(
            welcome_text,
            reply_markup=get_admin_keyboard()
        )
    elif is_moderator_db:
        # Модератор - все кнопки + модерация
        await message.answer(
            welcome_text,
            reply_markup=get_moderator_keyboard()
        )
    else:
        # Обычный пользователь - обычные кнопки
        await message.answer(
            welcome_text,
            reply_markup=get_main_keyboard()
        )
    
    await state.clear()

