import asyncio
import random
import logging
from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

# ======================================================
# ⚙️ БЛОК УПРАВЛЕНИЯ ЦЕНАМИ (МЕНЯЙТЕ ЗДЕСЬ)
# ======================================================

TOKEN = "8712313430:AAH2piHnnVm6z_uKR7sr1ygStQlt5E-748E"
ADMIN_ID = 6370436328  # Ваш ID

# Список услуг и базовые цены (ЗА 1 ЧАС)
SERVICES_CONFIG = {
    "Массаж 🥂": {
        "Specialist Zlata": 5000,
        "Specialist Kristina": 7500,
        "Specialist Milana": 3500,
        "Specialist Diana": 5500,
        "Specialist Arina": 9500,
    },
    "VIP 🏎️": {
        "Отель": 15000,
        "Апартаменты": 25000,
    },
    "События ✨": {
        "Standard Pass": 7000,
        "VIP Pass": 20000
    }
}

# Множители для длительности
# Текст кнопки : Множитель цены
TIME_OPTIONS = {
    "1 час ⏱️": 1,
    "2 часа ⏳": 1.8,  # Сделал чуть дешевле (коэфф 1.8 вместо 2)
    "На ночь 🌙": 4  # Цена за ночь = база * 3.5
}

REQUISITES = "💳 `2204120137230120` (Юмани)\n📍 Получатель: Куратор"


# ======================================================

class OrderProcess(StatesGroup):
    choosing_service = State()
    choosing_option = State()
    choosing_duration = State()
    waiting_for_payment = State()


router = Router()


# --- Логика бота ---

@router.message(Command("start"))
async def start_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    kb = ReplyKeyboardBuilder()
    kb.row(types.KeyboardButton(text="💎 Забронировать"))
    await message.answer(
        "🌃 **MOSCOW NIGHT**\nДобро пожаловать в систему бронирования.",
        reply_markup=kb.as_markup(resize_keyboard=True),
        parse_mode="Markdown"
    )


@router.message(F.text == "💎 Забронировать")
async def show_cats(message: types.Message, state: FSMContext):
    builder = InlineKeyboardBuilder()
    for cat in SERVICES_CONFIG.keys():
        builder.row(types.InlineKeyboardButton(text=cat, callback_data=f"cat_{cat}"))
    await message.answer("Выберите категорию:", reply_markup=builder.as_markup())
    await state.set_state(OrderProcess.choosing_service)


@router.callback_query(OrderProcess.choosing_service, F.data.startswith("cat_"))
async def cat_selected(callback: types.CallbackQuery, state: FSMContext):
    cat = callback.data.split("_")[1]
    await state.update_data(current_cat=cat)

    builder = InlineKeyboardBuilder()
    for name, base_price in SERVICES_CONFIG[cat].items():
        # Бот сам пишет базовую цену в кнопке
        builder.row(types.InlineKeyboardButton(
            text=f"{name} — от {base_price}₽",
            callback_data=f"target_{name}")
        )

    await callback.message.edit_text(f"📍 Категория: **{cat}**\nВыберите вариант:",
                                     reply_markup=builder.as_markup(), parse_mode="Markdown")
    await state.set_state(OrderProcess.choosing_option)


@router.callback_query(OrderProcess.choosing_option, F.data.startswith("target_"))
async def target_selected(callback: types.CallbackQuery, state: FSMContext):
    target_name = callback.data.split("_")[1]
    data = await state.get_data()
    cat = data['current_cat']

    # Достаем базовую цену из настроек
    base_price = SERVICES_CONFIG[cat][target_name]
    await state.update_data(selected_name=target_name, base_price=base_price)

    builder = InlineKeyboardBuilder()
    for label, mult in TIME_OPTIONS.items():
        # Сразу считаем и показываем итоговую цену на кнопках времени!
        calculated_price = int(base_price * mult)
        builder.row(types.InlineKeyboardButton(
            text=f"{label} — {calculated_price}₽",
            callback_data=f"dur_{label}_{calculated_price}")
        )

    await callback.message.edit_text("⏳ **Выберите длительность:**",
                                     reply_markup=builder.as_markup(), parse_mode="Markdown")
    await state.set_state(OrderProcess.choosing_duration)


@router.callback_query(OrderProcess.choosing_duration, F.data.startswith("dur_"))
async def dur_selected(callback: types.CallbackQuery, state: FSMContext):
    _, label, final_price = callback.data.split("_")
    order_id = random.randint(100, 999)
    data = await state.get_data()

    await state.update_data(final_price=final_price, duration_label=label, order_id=order_id)

    msg = (
        f"🧾 **ВАШ ЗАКАЗ №{order_id}**\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"🔹 Категория: `{data['current_cat']}`\n"
        f"🔹 Выбор: `{data['selected_name']}`\n"
        f"🔹 Время: **{label}**\n"
        f"💰 Итого: **{final_price} ₽**\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"**Для подтверждения оплатите на карту:**\n"
        f"{REQUISITES}\n\n"
        f"⚠️ Отправьте фото чека сюда."
    )
    await callback.message.edit_text(msg, parse_mode="Markdown")
    await state.set_state(OrderProcess.waiting_for_payment)


@router.message(OrderProcess.waiting_for_payment, F.photo)
async def payment_done(message: types.Message, state: FSMContext, bot: Bot):
    info = await state.get_data()
    await message.answer("✅ Чек принят. Ожидайте в течении 5 минут вам напишет менеджер.")

    # Отчет вам
    await bot.send_photo(
        ADMIN_ID,
        photo=message.photo[-1].file_id,
        caption=(
            f"🔔 **НОВЫЙ ЗАКАЗ #{info['order_id']}**\n"
            f"👤 Клиент: @{message.from_user.username}\n"
            f"🛠 Услуга: {info['current_cat']} ({info['selected_name']})\n"
            f"⏳ Длительность: {info['duration_label']}\n"
            f"💵 К получению: **{info['final_price']} ₽**"
        ),
        parse_mode="Markdown"
    )
    await state.clear()


async def main():
    bot = Bot(token=TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())