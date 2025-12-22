"""Обработчики callback запросов"""
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from bot.keyboards.main import get_quantity_keyboard, get_payment_method_keyboard
from config import settings

router = Router()


@router.callback_query(F.data.startswith("quantity:"))
async def handle_quantity(callback: CallbackQuery, state: FSMContext):
    """Обработка изменения количества"""
    parts = callback.data.split(":")
    action = parts[1]
    
    if action == "current":
        await callback.answer()
        return
    
    current_qty = int(parts[2]) if len(parts) > 2 else 1
    
    if action == "inc":
        new_qty = current_qty + 1
    elif action == "dec":
        new_qty = max(1, current_qty - 1)
    else:
        await callback.answer()
        return
    
    text = (
        f"Стоимость 1 публикации букета — {settings.PUBLICATION_PRICE:,} сум\n"
        f"Пожалуйста, укажите количество публикаций:\n"
        f"Если Вам нужна только 1 публикация, просто нажмите на "
        f"✅ Перейти к оплате 👇"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_quantity_keyboard(new_qty)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("payment:proceed:"))
async def proceed_to_payment(callback: CallbackQuery, state: FSMContext):
    """Переход к оплате"""
    quantity = int(callback.data.split(":")[2])
    total = quantity * settings.PUBLICATION_PRICE
    
    await state.update_data(quantity=quantity, total_amount=total)
    
    text = (
        f"Переход к оплате\n\n"
        f"Итого: за {quantity} публикаций - {total:,} сум\n"
        f"Выберите способ оплаты 👇"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_payment_method_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("payment_method:"))
async def handle_payment_method(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора способа оплаты"""
    provider = callback.data.split(":")[1]
    data = await state.get_data()
    
    # Здесь будет интеграция с платежными системами
    # Пока просто подтверждаем
    await callback.answer("Платежная система будет интегрирована позже", show_alert=True)

