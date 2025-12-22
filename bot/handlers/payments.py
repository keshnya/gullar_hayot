"""Обработчики оплаты публикаций"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.models.user import User
from database.models.payment import (
    Payment,
    PaymentStatus,
    PaymentType,
    PaymentProvider,
)


router = Router()


PUBLICATION_UNIT_PRICE = 30000


class PaymentStates(StatesGroup):
    """Состояния оплаты публикаций"""

    waiting_publication_count = State()
    waiting_custom_count = State()
    waiting_payment_screenshot = State()


def _build_publication_count_text(count: int) -> str:
    return (
        "Стоимость 1 публикации букета - 30 000 сум\n"
        "\n"
        "Пожалуйста, укажите количество публикаций:\n"
        "\n"
        'Если Вам нужна только 1 публикация, просто нажмите на "Перейти к оплате".'
    )


def _get_publication_count_keyboard(count: int) -> "InlineKeyboardMarkup":
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="-",
                    callback_data="pub_count:dec",
                ),
                InlineKeyboardButton(
                    text=str(count),
                    callback_data="pub_count:noop",
                ),
                InlineKeyboardButton(
                    text="+",
                    callback_data="pub_count:inc",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Указать своё число",
                    callback_data="pub_count:custom",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Перейти к оплате",
                    callback_data="pub_pay:go",
                )
            ],
        ]
    )


@router.callback_query(F.data.startswith("balance:topup:"))
async def start_publication_payment(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Старт покупки публикаций (от кнопки Пополнить баланс)"""
    parts = callback.data.split(":")
    publication_type = parts[2] if len(parts) > 2 else "auction"

    # Гарантируем, что пользователь существует
    result = await session.execute(
        select(User).where(User.telegram_id == callback.from_user.id)
    )
    user = result.scalar_one_or_none()

    if not user:
        await callback.answer("Ошибка: пользователь не найден", show_alert=True)
        return

    await state.update_data(
        payment_publication_type=publication_type,
        payment_count=1,
        payment_unit_price=PUBLICATION_UNIT_PRICE,
    )
    await state.set_state(PaymentStates.waiting_publication_count)

    text = _build_publication_count_text(1)
    keyboard = _get_publication_count_keyboard(1)

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(
    F.data.in_(["pub_count:inc", "pub_count:dec"]),
    PaymentStates.waiting_publication_count,
)
async def change_publication_count(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Обработка нажатий + / - для количества публикаций"""
    data = await state.get_data()
    count = int(data.get("payment_count", 1))

    if callback.data == "pub_count:inc":
        count = min(count + 1, 100)
    elif callback.data == "pub_count:dec":
        count = max(count - 1, 1)

    await state.update_data(payment_count=count)

    text = _build_publication_count_text(count)
    keyboard = _get_publication_count_keyboard(count)

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(
    F.data == "pub_count:custom",
    PaymentStates.waiting_publication_count,
)
async def ask_custom_publication_count(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Запрос ввода своего количества публикаций"""
    await state.set_state(PaymentStates.waiting_custom_count)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "Введите нужное количество публикаций (целое число от 1 до 100):"
    )
    await callback.answer()


@router.message(PaymentStates.waiting_custom_count)
async def process_custom_publication_count(
    message: Message,
    state: FSMContext,
) -> None:
    """Обработка своего числа публикаций"""
    try:
        count = int(message.text.replace(" ", ""))
    except (TypeError, ValueError):
        await message.answer("Пожалуйста, введите корректное целое число.")
        return

    if count <= 0 or count > 100:
        await message.answer("Число должно быть от 1 до 100.")
        return

    await state.update_data(payment_count=count)
    await state.set_state(PaymentStates.waiting_publication_count)

    text = _build_publication_count_text(count)
    keyboard = _get_publication_count_keyboard(count)

    await message.answer(text, reply_markup=keyboard)


@router.callback_query(
    F.data == "pub_pay:go",
    PaymentStates.waiting_publication_count,
)
async def go_to_payment(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Переход к оплате: показ суммы и реквизитов, ожидание скрина"""
    data = await state.get_data()
    count = int(data.get("payment_count", 1))
    unit_price = int(data.get("payment_unit_price", PUBLICATION_UNIT_PRICE))
    total = count * unit_price

    # Убираем кнопки у прошлого сообщения
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    # Создаём запись платежа (в ожидании)
    result = await session.execute(
        select(User).where(User.telegram_id == callback.from_user.id)
    )
    user = result.scalar_one_or_none()

    if not user:
        await callback.answer("Ошибка: пользователь не найден", show_alert=True)
        return

    payment = Payment(
        user_id=user.id,
        amount=total,
        payment_type=PaymentType.PUBLICATION.value,
        provider=PaymentProvider.CLICK.value,  # ручной перевод по реквизитам
        status=PaymentStatus.PENDING.value,
        payment_metadata=f"credits={count}",
    )
    session.add(payment)
    await session.commit()
    await session.refresh(payment)

    await state.update_data(payment_id=payment.id)
    await state.set_state(PaymentStates.waiting_payment_screenshot)

    text = (
        "Переход к оплате\n"
        f"Итого: за {count} публикаций - {total:,} сум\n\n"
        "Реквизиты для оплаты:\n"
        "💳 5614 6805 1045 9031\n"
        "👤 CHERNISHEVA YELENA\n\n"
        "Прикрепите, пожалуйста, скриншот оплаты в ответ на это сообщение."
    )

    await callback.message.answer(text)
    await callback.answer()


@router.message(
    PaymentStates.waiting_payment_screenshot,
    F.photo,
)
async def handle_payment_screenshot(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Приём скриншота оплаты и отправка модераторам"""
    data = await state.get_data()
    payment_id = data.get("payment_id")
    count = int(data.get("payment_count", 1))

    if not payment_id:
        await message.answer("Ошибка: не найдены данные оплаты.")
        await state.clear()
        return

    # Берём самое большое фото как основной скрин
    largest_photo = max(message.photo, key=lambda p: p.file_size or 0)
    photo_id = largest_photo.file_id

    # Получаем пользователя и платёж
    result = await session.execute(
        select(User).where(User.telegram_id == message.from_user.id)
    )
    user = result.scalar_one_or_none()

    payment_result = await session.execute(
        select(Payment).where(Payment.id == payment_id)
    )
    payment = payment_result.scalar_one_or_none()

    if not user or not payment:
        await message.answer("Ошибка: не удалось найти данные пользователя или платежа.")
        await state.clear()
        return

    from config import settings
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    caption = (
        "🧾 Новый платёж за публикации\n\n"
        f"Пользователь: @{user.username if user.username else f'ID: {user.telegram_id}'}\n"
        f"ID пользователя: {user.id}\n"
        f"Количество публикаций: {count}\n"
        f"Сумма: {payment.amount:,} сум\n"
        f"ID платежа: {payment.id}\n\n"
        "Подтвердить оплату?"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Подтвердить оплату",
                    callback_data=f"payment:approve:{payment.id}:{count}",
                ),
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=f"payment:reject:{payment.id}",
                ),
            ]
        ]
    )

    # Отправляем всем администраторам, как и уведомления о модерации
    for admin_id in settings.admin_ids_list:
        try:
            await message.bot.send_photo(
                chat_id=admin_id,
                photo=photo_id,
                caption=caption,
                reply_markup=kb,
            )
        except Exception:
            continue

    await message.answer(
        "Ваш платёж отправлен на проверку модератору. Ожидайте подтверждения."
    )
    await state.clear()

