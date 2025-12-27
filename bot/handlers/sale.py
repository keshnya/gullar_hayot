"""Обработчики обычных продаж"""
import logging
from datetime import datetime, timezone
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from database.models.regular_sale import RegularSale, SaleStatus
from database.models.product import Product
from database.models.user import User
from services.user import get_or_create_user
from config import settings

logger = logging.getLogger(__name__)

router = Router()


@router.callback_query(F.data.startswith("sale:buy:"))
async def handle_buy_interest(callback: CallbackQuery, session: AsyncSession):
    """Обработка интереса к покупке - отправляем контакты покупателя только продавцу"""
    sale_id = int(callback.data.split(":")[2])
    
    # Получаем продажу и товар
    result = await session.execute(
        select(RegularSale, Product, User)
        .join(Product, RegularSale.product_id == Product.id)
        .join(User, Product.user_id == User.id)
        .where(RegularSale.id == sale_id)
    )
    data = result.first()
    
    if not data:
        await callback.answer("Товар не найден", show_alert=True)
        return
    
    sale, product, seller = data
    
    if sale.status != "active":
        await callback.answer("Товар уже продан или недоступен", show_alert=True)
        return
    
    # Получаем покупателя
    buyer = await get_or_create_user(
        session,
        callback.from_user.id,
        callback.from_user.username,
        callback.from_user.first_name,
        callback.from_user.last_name
    )
    
    # Уведомляем продавца о заинтересованном покупателе с его контактами
    buyer_info = (
        f"👤 Покупатель заинтересовался вашим товаром '{product.title}':\n\n"
    )
    
    if buyer.username:
        buyer_info += f"Telegram: @{buyer.username}\n"
    if buyer.phone:
        buyer_info += f"Телефон: {buyer.phone}\n"
    buyer_info += f"ID: {buyer.telegram_id}\n"
    buyer_info += f"\n💰 Цена: {sale.price:,} сум"
    
    # Кнопка "Отметить как продано" прикреплена к каждому уведомлению
    sold_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Отметить как продано",
                callback_data=f"sale:sold:{sale.id}"
            )
        ]
    ])
    
    try:
        bot = Bot(token=settings.BOT_TOKEN)
        await bot.send_message(
            chat_id=seller.telegram_id,
            text=buyer_info,
            reply_markup=sold_keyboard
        )
        await bot.session.close()
        await callback.answer("Ваш запрос отправлен продавцу ✅", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления продавцу: {e}")
        await callback.answer("Ошибка при отправке запроса", show_alert=True)


@router.callback_query(F.data.startswith("sale:sold:"))
async def handle_mark_as_sold(callback: CallbackQuery, session: AsyncSession):
    """Обработка кнопки 'Продано' - продавец отмечает товар как проданный"""
    sale_id = int(callback.data.split(":")[2])
    
    # Получаем продажу и проверяем права
    result = await session.execute(
        select(RegularSale, Product, User)
        .join(Product, RegularSale.product_id == Product.id)
        .join(User, Product.user_id == User.id)
        .where(RegularSale.id == sale_id)
    )
    data = result.first()
    
    if not data:
        await callback.answer("Объявление не найдено", show_alert=True)
        return
    
    sale, product, seller = data
    
    # Проверяем что это продавец
    if callback.from_user.id != seller.telegram_id:
        await callback.answer("Только продавец может отметить товар как проданный", show_alert=True)
        return
    
    if sale.status == SaleStatus.SOLD.value:
        await callback.answer("Товар уже отмечен как проданный", show_alert=True)
        return
    
    # Обновляем статус продажи
    await session.execute(
        update(RegularSale)
        .where(RegularSale.id == sale_id)
        .values(
            status=SaleStatus.SOLD.value,
            sold_at=datetime.now(timezone.utc)
        )
    )
    await session.commit()
    
    # Обновляем сообщение в канале - убираем кнопку и добавляем текст "ПРОДАНО"
    if sale.channel_message_id:
        try:
            bot = Bot(token=settings.BOT_TOKEN)
            # Редактируем reply_markup - убираем кнопку "Хочу купить"
            await bot.edit_message_reply_markup(
                chat_id=settings.CHANNEL_ID,
                message_id=sale.channel_message_id,
                reply_markup=None
            )
            # Редактируем caption фото - добавляем "ПРОДАНО"
            # Формируем новый текст
            product_type_names = {
                "flowers": "🌹 Цветы",
                "gift": "🎁 Подарок",
                "other": "📦 Другое"
            }
            
            sold_text = (
                f"🎉 <b>ПРОДАНО</b> 🎉\n\n"
                f"📦 <b>{product.title}</b>\n\n"
                f"Тип: {product_type_names.get(product.product_type, product.product_type)}\n"
                f"Цена: <b>{sale.price:,} сум</b>\n"
            )
            
            await bot.edit_message_caption(
                chat_id=settings.CHANNEL_ID,
                message_id=sale.channel_message_id,
                caption=sold_text,
                parse_mode="HTML"
            )
            await bot.session.close()
        except Exception as e:
            logger.error(f"Ошибка при обновлении сообщения в канале: {e}")
    
    # Обновляем сообщение у продавца - убираем кнопку
    await callback.message.edit_text(
        f"✅ Товар '{product.title}' отмечен как проданный!",
        reply_markup=None
    )
    await callback.answer("Товар отмечен как проданный ✅")

