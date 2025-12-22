"""Обработчики публикации товаров"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, PhotoSize
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models.product import Product, ProductType
from database.models.auction import Auction
from database.models.regular_sale import RegularSale
from database.models.user import User
from services.user import get_or_create_user
from services.moderation import add_to_moderation
from services.auction import create_auction
import json

router = Router()


class PublicationStates(StatesGroup):
    """Состояния для публикации товара"""
    waiting_type = State()  # Ожидание выбора типа публикации
    waiting_title = State()  # Ожидание названия
    waiting_product_type = State()  # Ожидание типа товара
    waiting_photos = State()  # Ожидание фото (до 3)
    waiting_video = State()  # Ожидание видео (опционально)
    waiting_condition = State()  # Ожидание свежести/износа
    waiting_price = State()  # Ожидание цены
    waiting_contact = State()  # Ожидание контактов
    confirming = State()  # Подтверждение


@router.callback_query(F.data.startswith("publication_type:"))
async def handle_publication_type(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
):
    """Обработка выбора типа публикации"""
    pub_type = callback.data.split(":")[1]

    # Получаем или создаем пользователя
    user = await get_or_create_user(
        session,
        callback.from_user.id,
        callback.from_user.username,
        callback.from_user.first_name,
        callback.from_user.last_name,
    )

    await state.update_data(publication_type=pub_type)

    # Проверка доступных публикаций
    if user.publication_credits <= 0:
        from aiogram.types import InlineKeyboardButton
        from aiogram.utils.keyboard import InlineKeyboardBuilder

        publication_label = "аукцион" if pub_type == "auction" else "обычную продажу"

        text = (
            f"У Вас 0 доступных публикаций, пополните баланс, "
            f"чтобы опубликовать {publication_label}."
        )

        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(
                text="Пополнить баланс",
                callback_data=f"balance:topup:{pub_type}",
            )
        )

        await callback.message.edit_text(
            text,
            reply_markup=builder.as_markup(),
        )
        await callback.answer()
        return

    await state.set_state(PublicationStates.waiting_title)

    text = "📝 Создание публикации\n\nВведите название товара:"

    await callback.message.edit_text(text)
    await callback.answer()


@router.message(PublicationStates.waiting_title)
async def process_title(message: Message, state: FSMContext):
    """Обработка названия товара"""
    if len(message.text) > 255:
        await message.answer("Название слишком длинное (максимум 255 символов). Введите короче:")
        return
    
    await state.update_data(title=message.text)
    await state.set_state(PublicationStates.waiting_product_type)
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="🌹 Цветы",
        callback_data="product_type:flowers"
    ))
    builder.add(InlineKeyboardButton(
        text="🎁 Подарок",
        callback_data="product_type:gift"
    ))
    builder.add(InlineKeyboardButton(
        text="📦 Другое",
        callback_data="product_type:other"
    ))
    
    await message.answer(
        "Выберите тип товара:",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data.startswith("product_type:"), PublicationStates.waiting_product_type)
async def process_product_type(callback: CallbackQuery, state: FSMContext):
    """Обработка типа товара"""
    product_type = callback.data.split(":")[1]
    
    await state.update_data(product_type=product_type)
    await state.set_state(PublicationStates.waiting_photos)
    
    await callback.message.edit_text(
        "📸 Загрузите фото товара (до 3 штук):\n"
        "Отправьте фото одним или несколькими сообщениями.\n"
        "После загрузки фото используйте кнопки для продолжения."
    )
    await callback.answer()


@router.message(PublicationStates.waiting_photos, F.photo)
async def process_photo(message: Message, state: FSMContext):
    """Обработка загрузки фото"""
    data = await state.get_data()
    
    # Проверяем, что название товара уже введено
    if 'title' not in data or not data.get('title'):
        await message.answer(
            "❌ Сначала необходимо ввести название товара.\n\n"
            "Введите название товара:"
        )
        await state.set_state(PublicationStates.waiting_title)
        return
    
    # Проверяем, что тип товара выбран
    if 'product_type' not in data or not data.get('product_type'):
        await message.answer(
            "❌ Сначала необходимо выбрать тип товара.\n\n"
            "Выберите тип товара:"
        )
        await state.set_state(PublicationStates.waiting_product_type)
        return
    
    photos = data.get("photos", [])
    
    if len(photos) >= 3:
        await message.answer("Максимум 3 фото. Переходим к следующему шагу...")
        await finish_photos_auto(message, state)
        return
    
    # Сохраняем file_id самого большого фото
    largest_photo = max(message.photo, key=lambda p: p.file_size)
    photos.append(largest_photo.file_id)
    
    await state.update_data(photos=photos)
    
    # Если загружено 3 фото, автоматически переходим дальше
    if len(photos) >= 3:
        await message.answer("✅ Загружено максимальное количество фото (3/3). Переходим дальше...")
        await finish_photos_auto(message, state)
        return
    
    # Показываем кнопки для продолжения
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="✅ Продолжить",
        callback_data="photos:continue"
    ))
    
    remaining = 3 - len(photos)
    if remaining > 0:
        builder.add(InlineKeyboardButton(
            text=f"➕ Добавить еще фото ({len(photos) + 1}/3)",
            callback_data="photos:add_more"
        ))
    
    await message.answer(
        f"📸 Фото добавлено ({len(photos)}/3)\n\n"
        "Выберите действие:",
        reply_markup=builder.as_markup()
    )


@router.message(PublicationStates.waiting_photos, ~F.photo)
async def handle_non_photo_in_photos_state(message: Message, state: FSMContext):
    """Обработка не-фото сообщений в состоянии ожидания фото"""
    data = await state.get_data()
    
    # Если пользователь отправил текст, напоминаем о необходимости загрузить фото
    if message.text:
        await message.answer(
            "📸 Пожалуйста, загрузите фото товара.\n"
            "Отправьте фото одним или несколькими сообщениями (до 3 штук)."
        )
    else:
        await message.answer(
            "📸 Пожалуйста, загрузите фото товара (до 3 штук)."
        )


@router.callback_query(F.data == "photos:continue", PublicationStates.waiting_photos)
async def continue_after_photos(callback: CallbackQuery, state: FSMContext):
    """Продолжить после загрузки фото"""
    data = await state.get_data()
    photos = data.get("photos", [])
    
    if not photos:
        await callback.answer("Пожалуйста, загрузите хотя бы одно фото", show_alert=True)
        return
    
    await callback.answer()
    await finish_photos_auto(callback.message, state)


@router.callback_query(F.data == "photos:add_more", PublicationStates.waiting_photos)
async def add_more_photos(callback: CallbackQuery, state: FSMContext):
    """Добавить еще фото"""
    data = await state.get_data()
    photos = data.get("photos", [])
    
    if len(photos) >= 3:
        await callback.answer("Максимум 3 фото", show_alert=True)
        return
    
    await callback.answer()
    await callback.message.answer(
        f"📸 Отправьте следующее фото ({len(photos) + 1}/3):"
    )


async def finish_photos_auto(message: Message, state: FSMContext):
    """Автоматический переход к следующему шагу после фото"""
    await state.set_state(PublicationStates.waiting_video)
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="⏭️ Пропустить",
        callback_data="video:skip"
    ))
    
    await message.answer(
        "🎥 Хотите добавить видео? (опционально)\n"
        "Отправьте видео или нажмите 'Пропустить'",
        reply_markup=builder.as_markup()
    )


@router.message(PublicationStates.waiting_video, F.video)
async def process_video(message: Message, state: FSMContext):
    """Обработка загрузки видео"""
    await state.update_data(video=message.video.file_id)
    await state.set_state(PublicationStates.waiting_condition)
    
    await message.answer(
        "🕒 Укажите свежесть/износ букета.\n"
        "Например: «Получила 30 минут назад», «Стоял сутки» и т.п."
    )


@router.callback_query(F.data == "video:skip", PublicationStates.waiting_video)
async def skip_video(callback: CallbackQuery, state: FSMContext):
    """Пропустить загрузку видео"""
    await state.set_state(PublicationStates.waiting_condition)
    
    await callback.message.edit_text(
        "🕒 Укажите свежесть/износ букета.\n"
        "Например: «Получила 30 минут назад», «Стоял сутки» и т.п."
    )
    await callback.answer()


@router.message(PublicationStates.waiting_condition)
async def process_condition(message: Message, state: FSMContext):
    """Обработка свежести/износа"""
    condition = (message.text or "").strip()
    if not condition:
        await message.answer(
            "Пожалуйста, укажите свежесть/износ букета текстом.\n"
            "Например: «Получила 30 минут назад», «Новый», «Стоял сутки»."
        )
        return
    
    await state.update_data(condition=condition)
    await state.set_state(PublicationStates.waiting_price)
    
    await message.answer(
        "💰 Введите цену товара в сумах (только число):"
    )


@router.message(PublicationStates.waiting_price)
async def process_price(message: Message, state: FSMContext):
    """Обработка цены"""
    try:
        price = int(message.text.replace(" ", "").replace(",", ""))
        
        if price <= 0:
            await message.answer("Цена должна быть положительным числом. Введите еще раз:")
            return
        
        await state.update_data(price=price)
        
        # Получаем контактные данные пользователя
        data = await state.get_data()
        user_id = message.from_user.id
        
        # Проверяем, есть ли контакты у пользователя
        await state.set_state(PublicationStates.waiting_contact)
        
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(
            text="✅ Использовать мои данные из профиля",
            callback_data="contact:use_profile"
        ))
        builder.add(InlineKeyboardButton(
            text="✏️ Указать вручную",
            callback_data="contact:manual"
        ))
        
        await message.answer(
            "📞 Контактные данные:\n"
            "Выберите способ указания контактов:",
            reply_markup=builder.as_markup()
        )
        
    except ValueError:
        await message.answer("Пожалуйста, введите корректное число:")


@router.callback_query(F.data == "contact:use_profile", PublicationStates.waiting_contact)
async def use_profile_contact(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Использовать контакты из профиля"""
    result = await session.execute(
        select(User).where(User.telegram_id == callback.from_user.id)
    )
    user = result.scalar_one_or_none()
    
    contact_info = ""
    if user:
        parts = []
        if user.phone:
            parts.append(f"Телефон: {user.phone}")
        if user.username:
            parts.append(f"Telegram: @{user.username}")
        if user.contact_info:
            parts.append(user.contact_info)
        contact_info = ", ".join(parts) if parts else "Не указано"
    
    await state.update_data(contact_info=contact_info)
    await state.set_state(PublicationStates.confirming)
    
    await show_confirmation(callback.message, state, session)
    await callback.answer()


@router.callback_query(F.data == "contact:manual", PublicationStates.waiting_contact)
async def manual_contact(callback: CallbackQuery, state: FSMContext):
    """Ввод контактов вручную"""
    await callback.message.edit_text(
        "✏️ Введите контактные данные (телефон, Telegram, или другой способ связи):"
    )
    await callback.answer()


@router.message(PublicationStates.waiting_contact)
async def process_contact(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка контактов"""
    await state.update_data(contact_info=message.text)
    await state.set_state(PublicationStates.confirming)
    
    await show_confirmation(message, state, session)


async def show_confirmation(message: Message, state: FSMContext, session: AsyncSession):
    """Показать подтверждение публикации"""
    data = await state.get_data()
    
    product_type_names = {
        "flowers": "🌹 Цветы",
        "gift": "🎁 Подарок",
        "other": "📦 Другое"
    }
    
    text = (
        "📋 Подтвердите данные публикации:\n\n"
        f"Название: {data['title']}\n"
        f"Тип товара: {product_type_names.get(data['product_type'], data['product_type'])}\n"
        f"Фото: {len(data.get('photos', []))} шт.\n"
        f"Видео: {'Да' if data.get('video') else 'Нет'}\n"
        f"Свежесть/износ: {data.get('condition', 'Не указано')}\n"
        f"Цена: {data['price']:,} сум\n"
        f"Контакт: {data.get('contact_info', 'Не указано')}\n"
        f"Тип публикации: {'Аукцион' if data['publication_type'] == 'auction' else 'Обычная продажа'}\n\n"
        "Всё верно?"
    )
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="✅ Подтвердить",
        callback_data="publication:confirm"
    ))
    builder.add(InlineKeyboardButton(
        text="❌ Отменить",
        callback_data="publication:cancel"
    ))
    
    await message.answer(text, reply_markup=builder.as_markup())


@router.callback_query(F.data == "publication:confirm", PublicationStates.confirming)
async def confirm_publication(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Подтверждение и сохранение публикации"""
    data = await state.get_data()
    
    # Получаем или создаем пользователя
    user = await get_or_create_user(
        session,
        callback.from_user.id,
        callback.from_user.username,
        callback.from_user.first_name,
        callback.from_user.last_name
    )

    # Списываем одну доступную публикацию, если есть
    if user.publication_credits <= 0:
        await callback.answer(
            "У вас больше нет доступных публикаций. Пополните баланс.", show_alert=True
        )
        return

    user.publication_credits -= 1
    await session.commit()
    
    # Создаем товар
    condition = data.get("condition")
    description = None
    if condition:
        description = f"Свежесть: {condition}"
    
    product = Product(
        user_id=user.id,
        title=data['title'],
        product_type=data['product_type'],
        description=description,
        photos=json.dumps(data.get('photos', [])),
        video=data.get('video'),
        price=data['price'],
        contact_info=data.get('contact_info', '')
    )
    session.add(product)
    await session.commit()
    await session.refresh(product)
    
    # Создаем аукцион или обычную продажу
    if data['publication_type'] == 'auction':
        auction = await create_auction(session, product.id, data['price'])
        await add_to_moderation(session, product.id, user.id)
        
        # Отправляем уведомление админам
        from bot.handlers.moderation import send_moderation_notification
        from aiogram import Bot
        from config import settings
        bot_instance = Bot(token=settings.BOT_TOKEN)
        await send_moderation_notification(bot_instance, session, product.id)
        await bot_instance.session.close()
        
        await callback.message.edit_text(
            "✅ Товар создан и отправлен на модерацию!\n\n"
            "После одобрения модератором ваш товар будет опубликован в канале."
        )
    else:
        # Обычная продажа
        from database.models.regular_sale import RegularSale, SaleStatus
        sale = RegularSale(
            product_id=product.id,
            price=data['price'],
            status=SaleStatus.PENDING.value
        )
        session.add(sale)
        await add_to_moderation(session, product.id, user.id)
        await session.commit()
        
        # Отправляем уведомление админам
        from bot.handlers.moderation import send_moderation_notification
        from aiogram import Bot
        from config import settings
        bot_instance = Bot(token=settings.BOT_TOKEN)
        await send_moderation_notification(bot_instance, session, product.id)
        await bot_instance.session.close()
        
        await callback.message.edit_text(
            "✅ Товар создан и отправлен на модерацию!\n\n"
            "После одобрения модератором ваш товар будет опубликован в канале."
        )
    
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "publication:cancel", PublicationStates.confirming)
async def cancel_publication(callback: CallbackQuery, state: FSMContext):
    """Отмена публикации"""
    await state.clear()
    await callback.message.edit_text("❌ Публикация отменена")
    await callback.answer()

