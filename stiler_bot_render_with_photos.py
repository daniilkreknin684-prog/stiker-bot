import asyncio
import csv
import os
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from dotenv import load_dotenv

# ====== ЗАГРУЗКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ======
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
ADMIN_LINK = os.getenv("ADMIN_LINK")

# ====== ЦЕНЫ И НАСТРОЙКИ ======
PRICES = {
    "2.5x2.5": 55,
    "3x3": 60,
    "3x4": 70,
    "6x8": 195
}

DATA_DIR = "data"
FILE_PATH = os.path.join(DATA_DIR, "orders.csv")
os.makedirs(DATA_DIR, exist_ok=True)

bot = Bot(token=TOKEN)
dp = Dispatcher()


# ====== СОХРАНЕНИЕ ЗАКАЗОВ ======
def save_order(user_id, username, qty, fmt, total, file_ids):
    file_exists = os.path.isfile(FILE_PATH)
    with open(FILE_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["user_id", "username", "quantity", "format", "total_price", "file_ids"])
        writer.writerow([user_id, username, qty, fmt, total, ";".join(file_ids)])


# ====== КОМАНДА /START ======
@dp.message(Command("start"))
async def start(message: Message):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🧾 Оформить заказ", callback_data="order")]]
    )
    await message.answer("Привет 👋\nЯ помогу оформить заказ на 3D-стикеры!", reply_markup=kb)
    print(f"[INFO] Пользователь @{message.from_user.username} запустил бота")


# ====== НАЧАЛО ОФОРМЛЕНИЯ ======
@dp.callback_query(F.data == "order")
async def order_start(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="2.5x2.5", callback_data="fmt_2.5x2.5"),
                InlineKeyboardButton(text="3x3", callback_data="fmt_3x3"),
            ],
            [
                InlineKeyboardButton(text="3x4", callback_data="fmt_3x4"),
                InlineKeyboardButton(text="6x8", callback_data="fmt_6x8"),
            ],
        ]
    )
    await callback.message.answer("Выбери формат стикеров:", reply_markup=kb)


# ====== ВЫБОР ФОРМАТА ======
@dp.callback_query(F.data.startswith("fmt_"))
async def choose_format(callback: CallbackQuery):
    fmt = callback.data.split("_")[1]
    price = PRICES[fmt]
    dp.workflow_data[callback.from_user.id] = {"format": fmt, "files": []}
    await callback.message.answer(
        f"Формат выбран: {fmt}\nЦена: {price}₽ за штуку\n\nОтправь количество стикеров числом:"
    )


# ====== ВВОД КОЛИЧЕСТВА ======
@dp.message(F.text.regexp(r'^\d+$'))
async def get_quantity(message: Message):
    user_data = dp.workflow_data.get(message.from_user.id, {})
    if not user_data:
        await message.answer("Сначала выбери формат!")
        return

    qty = int(message.text)
    fmt = user_data["format"]
    total = PRICES[fmt] * qty

    user_data["quantity"] = qty
    user_data["total"] = total

    await message.answer(f"Количество: {qty}\nИтого: {total}₽\nТеперь отправь фото для печати.")


# ====== ПОЛУЧЕНИЕ ФОТО ======
@dp.message(F.photo)
async def get_photos(message: Message):
    user_data = dp.workflow_data.get(message.from_user.id, {})
    if not user_data:
        await message.answer("Сначала выбери формат и количество!")
        return

    file_id = message.photo[-1].file_id
    user_data["files"].append(file_id)
    await message.answer("Фото добавлено ✅\nКогда все фото отправлены — напиши 'готово'.")


# ====== ЗАВЕРШЕНИЕ ЗАКАЗА ======
@dp.message(F.text.lower() == "готово")
async def finalize_order(message: Message):
    user_data = dp.workflow_data.pop(message.from_user.id, None)
    if not user_data:
        await message.answer("Нет активного заказа.")
        return

    save_order(
        message.from_user.id,
        message.from_user.username or "unknown",
        user_data["quantity"],
        user_data["format"],
        user_data["total"],
        user_data["files"]
    )

    # Сообщение пользователю
    await message.answer(
        f"✅ Заказ оформлен!\n"
        f"Формат: {user_data['format']}\n"
        f"Количество: {user_data['quantity']}\n"
        f"Сумма: {user_data['total']}₽\n\n"
        f"Свяжись с мастером для оплаты: {ADMIN_LINK}"
    )

    # Сообщение админу
    admin_msg = (
        f"📦 Новый заказ!\n"
        f"От: @{message.from_user.username or 'unknown'} (ID: {message.from_user.id})\n"
        f"Формат: {user_data['format']}\n"
        f"Количество: {user_data['quantity']}\n"
        f"Сумма: {user_data['total']}₽"
    )
    await bot.send_message(ADMIN_ID, admin_msg)

    # Отправка всех фото админу
    for file_id in user_data["files"]:
        try:
            await bot.send_photo(ADMIN_ID, file_id)
        except Exception as e:
            print(f"[ERROR] Ошибка при отправке фото админу: {e}")

    print(f"[INFO] Заказ от @{message.from_user.username} успешно отправлен админу.")


# ====== ЗАПУСК БОТА ======
async def main():
    dp.workflow_data = {}
    print("[INFO] Бот запущен и ожидает сообщения...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
