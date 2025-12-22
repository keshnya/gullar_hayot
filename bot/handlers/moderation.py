"""Обработчики модерации"""
from math import ceil
import json

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.models.moderation import ModerationQueue, ModerationStatus
from database.models.product import Product
from database.models.auction import Auction
from database.models.regular_sale import RegularSale
from database.models.user import User
from database.models.payment import Payment, PaymentStatus, PaymentType
from services.moderation import approve_product, reject_product, get_pending_moderations
from bot.keyboards.moderation import get_moderation_keyboard
from config import settings

router = Router()

ITEMS_PER_PAGE = 3


class RejectReasonStates(StatesGroup):
    """FSM для ввода причины отклонения"""
    waiting_reason = State()


async def _build_product_text(
    session: AsyncSession,
    product_id: int,
    status_text: str = "На модерации",
) -> str:
    """Сформировать текст описания товара для модерации"""
    result = await session.execute(
        select(Product, User).join(User, Product.user_id == User.id).where(Product.id == product_id)
    )
    data = result.first()

    if not data:
        return "Товар не найден"

    product, user = data

    product_type_names = {
        "flowers": "🌹 Цветы",
        "gift": "🎁 Подарок",
        "other": "📦 Другое",
    }

    text = (
        f"📦 Товар #{product.id}\n"
        f"Статус: {status_text}\n\n"
        f"Название: {product.title}\n"
        f"Тип: {product_type_names.get(product.product_type, product.product_type)}\n"
        f"Цена: {product.price:,} сум\n\n"
    )

    if product.description:
        text += f"Описание: {product.description}\n\n"

    text += f"📞 Контакты: {product.contact_info or 'Не указано'}\n"
    text += (
        f"👤 Продавец: @{user.username if user.username else f'ID: {user.telegram_id}'}"
    )

    return text


async def send_moderation_page(
    message: Message,
    session: AsyncSession,
    page: int = 1,
) -> None:
    """Отправить модератору страницу товаров (по 3 шт.)"""
    moderations = await get_pending_moderations(session)

    if not moderations:
        await message.answer("✅ Нет товаров на модерации")
        return

    total = len(moderations)
    total_pages = max(1, ceil(total / ITEMS_PER_PAGE))
    page = max(1, min(page, total_pages))

    start_idx = (page - 1) * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    page_items = moderations[start_idx:end_idx]

    for mod in page_items:
        product_id = mod.product_id
        text = await _build_product_text(session, product_id, status_text="На модерации")

        # Пытаемся отправить фото, если есть
        result = await session.execute(select(Product).where(Product.id == product_id))
        product = result.scalar_one_or_none()

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Одобрить",
                        callback_data=f"moderation:approve:{product_id}",
                    ),
                    InlineKeyboardButton(
                        text="❌ Отклонить",
                        callback_data=f"moderation:reject:{product_id}",
                    ),
                ]
            ]
        )

        if product and product.photos:
            try:
                photos = json.loads(product.photos)
            except Exception:
                photos = []

            if photos:
                # Сначала отправляем все фото без подписи,
                # под последней картинкой — полное описание товара с кнопками
                last_index = len(photos) - 1
                for idx, photo_id in enumerate(photos):
                    if idx == last_index:
                        await message.bot.send_photo(
                            chat_id=message.chat.id,
                            photo=photo_id,
                            caption=text,
                            reply_markup=kb,
                        )
                    else:
                        await message.bot.send_photo(
                            chat_id=message.chat.id,
                            photo=photo_id,
                        )
                continue

        # Если фото нет или ошибка парсинга
        await message.answer(text, reply_markup=kb)

    # Кнопки пагинации
    nav_buttons = []
    if page > 1:
        nav_buttons.append(
            InlineKeyboardButton(
                text="⬅️ Предыдущие",
                callback_data=f"moderation_page:{page-1}",
            )
        )
    if page < total_pages:
        nav_buttons.append(
            InlineKeyboardButton(
                text="➡️ Следующие",
                callback_data=f"moderation_page:{page+1}",
            )
        )

    if nav_buttons:
        await message.answer(
            f"Страница {page} из {total_pages}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[nav_buttons]),
        )


@router.callback_query(F.data.startswith("moderation_page:"))
async def handle_moderation_page(callback: CallbackQuery, session: AsyncSession):
    """Переключение страниц модерации"""
    from bot.handlers.admin import is_admin_or_moderator

    if not await is_admin_or_moderator(callback.from_user.id, session):
        await callback.answer("У вас нет прав для модерации", show_alert=True)
        return

    parts = callback.data.split(":")
    page = int(parts[1]) if len(parts) > 1 else 1

    await send_moderation_page(callback.message, session, page)
    await callback.answer()


@router.callback_query(F.data.startswith("moderation:"))
async def handle_moderation(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
):
    """Обработка действий модерации (approve/reject)"""
    from bot.handlers.admin import is_admin_or_moderator

    if not await is_admin_or_moderator(callback.from_user.id, session):
        await callback.answer("У вас нет прав для модерации", show_alert=True)
        return

    parts = callback.data.split(":")
    action = parts[1]
    product_id = int(parts[2])

    if action == "approve":
        try:
            # находим модератора по telegram_id
            result = await session.execute(
                select(User).where(User.telegram_id == callback.from_user.id)
            )
            moderator = result.scalar_one_or_none()
            moderator_db_id = moderator.id if moderator else None

            await approve_product(
                session,
                product_id,
                moderator_db_id or 0,
            )

            # Публикуем в канал
            from services.channel import publish_auction_to_channel, publish_sale_to_channel
            from aiogram import Bot

            bot_instance = Bot(token=settings.BOT_TOKEN)

            # Проверяем, есть ли аукцион
            result = await session.execute(
                select(Auction).where(Auction.product_id == product_id)
            )
            auction = result.scalar_one_or_none()

            if auction:
                channel_message_id = await publish_auction_to_channel(
                    bot_instance,
                    session,
                    product_id,
                )
            else:
                # Проверяем обычную продажу
                result = await session.execute(
                    select(RegularSale).where(RegularSale.product_id == product_id)
                )
                sale = result.scalar_one_or_none()

                if not sale:
                    await callback.answer(
                        "Товар одобрен, но не найден тип публикации", show_alert=True
                    )
                    await bot_instance.session.close()
                    return

                channel_message_id = await publish_sale_to_channel(
                    bot_instance,
                    session,
                    product_id,
                )

            await bot_instance.session.close()

            # DEBUG
            print(f"[DEBUG] moderation approve OK, product_id={product_id}, channel_message_id={channel_message_id}")

            # Обновляем статус в карточке: Одобрен, убираем кнопки
            new_text = await _build_product_text(session, product_id, status_text="Одобрен")
            try:
                if callback.message.photo:
                    await callback.message.edit_caption(new_text)
                else:
                    await callback.message.edit_text(new_text)
                await callback.message.edit_reply_markup(reply_markup=None)
            except Exception as e:
                print(f"[DEBUG] failed to update message after approve: {e!r}")

            await callback.answer("Товар одобрен и опубликован в канал ✅", show_alert=True)
        except Exception as e:
            await callback.answer(f"Ошибка: {str(e)}", show_alert=True)
            import logging

            logging.error(
                f"Ошибка при публикации товара {product_id}: {e}",
                exc_info=True,
            )
            print(f"[DEBUG] moderation approve ERROR, product_id={product_id}, error={e!r}")

    elif action == "reject":
        # Запоминаем product_id и данные исходного сообщения, просим причину
        await state.update_data(
            product_id=product_id,
            origin_chat_id=callback.message.chat.id,
            origin_message_id=callback.message.message_id,
            origin_has_photo=bool(callback.message.photo),
        )
        await state.set_state(RejectReasonStates.waiting_reason)
        await callback.message.answer(
            f"❌ Введите причину отклонения для товара #{product_id}:"
        )
        await callback.answer()


@router.message(RejectReasonStates.waiting_reason)
async def process_reject_reason(message: Message, session: AsyncSession, state: FSMContext):
    """Обработка ввода причины отклонения"""
    print(f"[DEBUG] process_reject_reason called, text={message.text!r}")

    data = await state.get_data()
    product_id = data.get("product_id")
    origin_chat_id = data.get("origin_chat_id")
    origin_message_id = data.get("origin_message_id")
    origin_has_photo = data.get("origin_has_photo")

    reason = (message.text or "").strip()
    if not reason:
        await message.answer("Пожалуйста, введите не пустую причину отклонения.")
        return

    try:
        # находим модератора по telegram_id
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        moderator = result.scalar_one_or_none()
        moderator_db_id = moderator.id if moderator else None

        await reject_product(
            session,
            product_id,
            moderator_db_id or 0,
            reason,
        )
        print(f"[DEBUG] reject_product OK, product_id={product_id}, reason={reason!r}")
        # Обновляем статус в карточке: Отклонён, убираем кнопки
        new_text = await _build_product_text(session, product_id, status_text="Отклонён")
        try:
            if origin_chat_id and origin_message_id:
                # Пытаемся обновить исходное сообщение модерации
                if origin_has_photo:
                    await message.bot.edit_message_caption(
                        chat_id=origin_chat_id,
                        message_id=origin_message_id,
                        caption=new_text,
                    )
                else:
                    await message.bot.edit_message_text(
                        chat_id=origin_chat_id,
                        message_id=origin_message_id,
                        text=new_text,
                    )
                await message.bot.edit_message_reply_markup(
                    chat_id=origin_chat_id,
                    message_id=origin_message_id,
                    reply_markup=None,
                )
            # Дополнительно отправляем краткое подтверждение модератору
            await message.answer(f"❌ Товар #{product_id} отклонён.")
        except Exception as e:
            print(f"[DEBUG] failed to update message after reject: {e!r}")
            await message.answer(f"❌ Товар #{product_id} отклонён.")
    except Exception as e:
        print(f"[DEBUG] reject_product ERROR, product_id={product_id}, error={e!r}")
        await message.answer("Ошибка при отклонении товара. Подробности записаны в логах.")

    await state.clear()


@router.callback_query(F.data.startswith("payment:"))
async def handle_payment_moderation(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """Обработка подтверждения/отклонения оплат за публикации"""
    parts = callback.data.split(":")
    if len(parts) < 2:
        await callback.answer("Неверные данные платежа", show_alert=True)
        return

    action = parts[1]

    # payment:approve:{payment_id}:{count}
    # payment:reject:{payment_id}
    if action == "approve" and len(parts) >= 4:
        payment_id = int(parts[2])
        credits = int(parts[3])

        result = await session.execute(
            select(Payment).where(Payment.id == payment_id)
        )
        payment = result.scalar_one_or_none()

        if not payment:
            await callback.answer("Платёж не найден", show_alert=True)
            return

        if payment.status == PaymentStatus.COMPLETED.value:
            await callback.answer("Этот платёж уже подтверждён.", show_alert=True)
            return

        # Находим пользователя
        user_result = await session.execute(
            select(User).where(User.id == payment.user_id)
        )
        user = user_result.scalar_one_or_none()

        if not user:
            await callback.answer("Пользователь не найден", show_alert=True)
            return

        # Обновляем статус платежа и начисляем публикации
        payment.status = PaymentStatus.COMPLETED.value
        user.publication_credits = (user.publication_credits or 0) + credits
        await session.commit()

        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

        await callback.answer("Оплата подтверждена ✅", show_alert=True)

        # Уведомляем пользователя
        await callback.bot.send_message(
            chat_id=user.telegram_id,
            text=(
                "✅ Оплата за публикации подтверждена.\n"
                f"Теперь у вас доступно {user.publication_credits} публикаций."
            ),
        )

    elif action == "reject" and len(parts) >= 3:
        payment_id = int(parts[2])

        result = await session.execute(
            select(Payment).where(Payment.id == payment_id)
        )
        payment = result.scalar_one_or_none()

        if not payment:
            await callback.answer("Платёж не найден", show_alert=True)
            return

        if payment.status in (
            PaymentStatus.COMPLETED.value,
            PaymentStatus.CANCELLED.value,
            PaymentStatus.FAILED.value,
        ):
            await callback.answer("Этот платёж уже обработан.", show_alert=True)
            return

        # Находим пользователя
        user_result = await session.execute(
            select(User).where(User.id == payment.user_id)
        )
        user = user_result.scalar_one_or_none()

        if not user:
            await callback.answer("Пользователь не найден", show_alert=True)
            return

        payment.status = PaymentStatus.FAILED.value
        await session.commit()

        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

        await callback.answer("Платёж отклонён ❌", show_alert=True)

        await callback.bot.send_message(
            chat_id=user.telegram_id,
            text=(
                "❌ Оплата за публикации не подтверждена.\n"
                "Если вы уверены, что всё оплатили верно, свяжитесь, пожалуйста, с поддержкой."
            ),
        )



async def send_moderation_notification(
    bot,
    session: AsyncSession,
    product_id: int,
):
    """Отправить уведомление о новом товаре на модерацию (кратко)"""
    result = await session.execute(
        select(Product).where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()

    if not product:
        return

    text = (
        f"🆕 Новый товар на модерацию\n\n"
        f"ID: {product.id}\n"
        f"Название: {product.title}\n"
        f"Цена: {product.price:,} сум\n\n"
        "Откройте меню бота и нажмите кнопку "
        "<b>👮 Модерация</b>, чтобы просмотреть и обработать товары."
    )

    for admin_id in settings.admin_ids_list:
        try:
            await bot.send_message(
                admin_id,
                text,
                parse_mode="HTML",
            )
        except Exception as e:
            print(f"Ошибка отправки админу {admin_id}: {e}")

