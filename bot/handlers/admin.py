"""Обработчики для админов"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models.moderation import ModerationQueue, ModerationStatus
from database.models.product import Product
from database.models.user import User
from services.moderation import get_pending_moderations
from bot.keyboards.moderation import get_moderation_keyboard
from config import settings
from aiogram import Bot

router = Router()

# FSM состояния для управления модераторами
from aiogram.fsm.state import State, StatesGroup


class ModeratorManagementStates(StatesGroup):
    """Состояния для управления модераторами"""
    waiting_add_telegram_id = State()
    waiting_remove_telegram_id = State()


async def is_admin_or_moderator(user_id: int, session: AsyncSession) -> bool:
    """Проверить, является ли пользователь админом или модератором"""
    from config import settings
    
    # Проверяем, является ли админом из .env
    if user_id in settings.admin_ids_list:
        return True
    
    # Проверяем, является ли модератором из БД
    result = await session.execute(
        select(User).where(
            User.telegram_id == user_id,
            User.is_moderator == True
        )
    )
    user = result.scalar_one_or_none()
    
    return user is not None


@router.message(F.text == "👮 Модерация")
async def cmd_moderation_button(message: Message, session: AsyncSession):
    """Показать товары на модерации (через кнопку)"""
    if not await is_admin_or_moderator(message.from_user.id, session):
        await message.answer("У вас нет прав для модерации")
        return
    await cmd_moderation(message, session)


@router.message(Command("moderation"))
async def cmd_moderation(message: Message, session: AsyncSession):
    """Показать товары на модерации"""
    if not await is_admin_or_moderator(message.from_user.id, session):
        await message.answer("У вас нет прав для модерации")
        return

    # Используем новый постраничный вывод в handlers.moderation
    from bot.handlers.moderation import send_moderation_page
    await send_moderation_page(message, session, page=1)


@router.message(F.text == "📋 Админ панель")
async def cmd_admin_button(message: Message, session: AsyncSession):
    """Админ панель (через кнопку)"""
    await cmd_admin(message, session)


@router.message(Command("admin"))
async def cmd_admin(message: Message, session: AsyncSession):
    """Админ панель"""
    if not await is_admin_or_moderator(message.from_user.id, session):
        await message.answer("У вас нет прав администратора")
        return
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="➕ Добавить модератора",
        callback_data="admin:add_moderator"
    ))
    builder.add(InlineKeyboardButton(
        text="📋 Список модераторов",
        callback_data="admin:list_moderators"
    ))
    builder.row()
    builder.add(InlineKeyboardButton(
        text="❌ Удалить модератора",
        callback_data="admin:remove_moderator"
    ))
    
    text = (
        "👮 Админ панель\n\n"
        "Доступные действия:\n"
        "• Добавить/удалить модератора\n"
        "• Просмотр списка модераторов\n\n"
        "Команды:\n"
        "/moderation - Показать товары на модерации\n"
        "/stats - Статистика (через API)"
    )
    
    await message.answer(text, reply_markup=builder.as_markup())


async def is_admin_or_moderator(user_id: int, session: AsyncSession) -> bool:
    """Проверить, является ли пользователь админом или модератором"""
    from config import settings
    
    # Проверяем, является ли админом из .env
    if user_id in settings.admin_ids_list:
        return True
    
    # Проверяем, является ли модератором из БД
    result = await session.execute(
        select(User).where(
            User.telegram_id == user_id,
            User.is_moderator == True
        )
    )
    user = result.scalar_one_or_none()
    
    return user is not None


@router.callback_query(F.data == "admin:add_moderator")
async def add_moderator_start(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Начать процесс добавления модератора"""
    if callback.from_user.id not in settings.admin_ids_list:
        await callback.answer("Только главные админы могут добавлять модераторов", show_alert=True)
        return
    
    await callback.message.answer(
        "➕ Добавление модератора\n\n"
        "Введите Telegram ID пользователя, которого хотите сделать модератором:"
    )
    await callback.answer()
    
    await state.set_state(ModeratorManagementStates.waiting_add_telegram_id)


@router.message(ModeratorManagementStates.waiting_add_telegram_id)
async def process_add_moderator(message: Message, session: AsyncSession, state: FSMContext):
    """Обработать добавление модератора"""
    if not message.text or not message.text.isdigit():
        await message.answer("Пожалуйста, введите корректный Telegram ID (число)")
        return
    
    if message.from_user.id not in settings.admin_ids_list:
        await message.answer("Только главные админы могут добавлять модераторов")
        await state.clear()
        return
    
    try:
        telegram_id = int(message.text)
        
        # Проверяем, существует ли пользователь
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await message.answer(
                f"Пользователь с ID {telegram_id} не найден в базе.\n"
                f"Попросите его сначала написать боту /start"
            )
            await state.clear()
            return
        
        if user.is_moderator:
            await message.answer(f"Пользователь {telegram_id} уже является модератором")
            await state.clear()
            return
        
        # Делаем модератором
        user.is_moderator = True
        await session.commit()
        
        await message.answer(
            f"✅ Пользователь {telegram_id} теперь модератор!\n"
            f"Имя: {user.first_name or 'Не указано'}\n"
            f"Username: @{user.username or 'Не указано'}"
        )
        
        # Уведомляем нового модератора
        try:
            from aiogram import Bot
            from bot.keyboards.admin import get_moderator_keyboard
            bot_instance = Bot(token=settings.BOT_TOKEN)
            await bot_instance.send_message(
                telegram_id,
                "🎉 Поздравляем! Вам выданы права модератора.\n"
                "Теперь вы можете модерировать товары через кнопку '👮 Модерация'",
                reply_markup=get_moderator_keyboard()
            )
            await bot_instance.session.close()
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Ошибка отправки уведомления модератору: {e}")
        
        await state.clear()
        
    except ValueError:
        await message.answer("Пожалуйста, введите корректный Telegram ID (число)")


@router.callback_query(F.data == "admin:list_moderators")
async def list_moderators(callback: CallbackQuery, session: AsyncSession):
    """Показать список модераторов"""
    if callback.from_user.id not in settings.admin_ids_list:
        await callback.answer("Только главные админы могут просматривать список", show_alert=True)
        return
    
    result = await session.execute(
        select(User).where(User.is_moderator == True)
    )
    moderators = result.scalars().all()
    
    if not moderators:
        await callback.message.answer("📋 Список модераторов пуст")
        await callback.answer()
        return
    
    text = "📋 Список модераторов:\n\n"
    for mod in moderators:
        text += (
            f"• ID: {mod.telegram_id}\n"
            f"  Имя: {mod.first_name or 'Не указано'}\n"
            f"  Username: @{mod.username or 'Не указано'}\n\n"
        )
    
    await callback.message.answer(text)
    await callback.answer()


@router.callback_query(F.data == "admin:remove_moderator")
async def remove_moderator_start(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Начать процесс удаления модератора"""
    if callback.from_user.id not in settings.admin_ids_list:
        await callback.answer("Только главные админы могут удалять модераторов", show_alert=True)
        return
    
    await callback.message.answer(
        "❌ Удаление модератора\n\n"
        "Введите Telegram ID модератора, которого хотите удалить:"
    )
    await callback.answer()
    
    await state.set_state(ModeratorManagementStates.waiting_remove_telegram_id)


@router.message(ModeratorManagementStates.waiting_remove_telegram_id)
async def process_remove_moderator(message: Message, session: AsyncSession, state: FSMContext):
    """Обработать удаление модератора"""
    if not message.text or not message.text.isdigit():
        await message.answer("Пожалуйста, введите корректный Telegram ID (число)")
        return
    
    if message.from_user.id not in settings.admin_ids_list:
        await message.answer("Только главные админы могут удалять модераторов")
        await state.clear()
        return
    
    try:
        telegram_id = int(message.text)
        
        # Проверяем, существует ли пользователь
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await message.answer(f"Пользователь с ID {telegram_id} не найден")
            await state.clear()
            return
        
        if not user.is_moderator:
            await message.answer(f"Пользователь {telegram_id} не является модератором")
            await state.clear()
            return
        
        # Убираем права модератора
        user.is_moderator = False
        await session.commit()
        
        await message.answer(
            f"✅ Права модератора у пользователя {telegram_id} удалены"
        )
        
        await state.clear()
        
    except ValueError:
        await message.answer("Пожалуйста, введите корректный Telegram ID (число)")

