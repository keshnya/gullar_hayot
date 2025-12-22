"""Обработчики обычных продаж"""
from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models.regular_sale import RegularSale
from database.models.product import Product
from database.models.user import User
from services.user import get_or_create_user

router = Router()


@router.callback_query(F.data.startswith("sale:buy:"))
async def handle_buy_interest(callback: CallbackQuery, session: AsyncSession):
    """Обработка интереса к покупке"""
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
    
    # Отправляем контакты продавца покупателю
    contact_text = (
        f"📞 Контакты продавца для товара '{product.title}':\n\n"
    )
    
    if seller.phone:
        contact_text += f"Телефон: {seller.phone}\n"
    if seller.username:
        contact_text += f"Telegram: @{seller.username}\n"
    if product.contact_info:
        contact_text += f"Дополнительно: {product.contact_info}\n"
    
    contact_text += f"\nЦена: {sale.price:,} сум"
    
    await callback.message.answer(contact_text)
    await callback.answer("Контакты отправлены ✅")
    
    # Уведомляем продавца о заинтересованном покупателе
    buyer_info = (
        f"👤 Покупатель заинтересовался вашим товаром '{product.title}':\n\n"
    )
    
    if buyer.username:
        buyer_info += f"Telegram: @{buyer.username}\n"
    if buyer.phone:
        buyer_info += f"Телефон: {buyer.phone}\n"
    buyer_info += f"ID: {buyer.telegram_id}"
    
    try:
        from config import settings
        from aiogram import Bot
        bot = Bot(token=settings.BOT_TOKEN)
        await bot.send_message(
            chat_id=seller.telegram_id,
            text=buyer_info
        )
        await bot.session.close()
    except Exception as e:
        import logging
        logging.error(f"Ошибка при отправке уведомления продавцу: {e}")

