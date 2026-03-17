import asyncio
import logging
import os
import json
import pathlib

import aiohttp
from aiohttp import web

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
    WebAppInfo,
)
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from database import Database

# ─── Настройки ────────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "ВАШ_ТОКЕН")
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "123456789").split(",")]
PORT      = int(os.getenv("PORT", "8080"))
BASE_URL  = os.getenv("BASE_URL", f"http://localhost:{PORT}")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher(storage=MemoryStorage())
db  = Database()


# ─── FSM: добавление товара ───────────────────────────────────
class AddProduct(StatesGroup):
    photo       = State()
    name        = State()
    price       = State()
    description = State()
    sizes       = State()


# ─── Вспомогательные функции ──────────────────────────────────
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def main_menu(is_admin_user=False) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(
            text="🛍 Открыть каталог",
            web_app=WebAppInfo(url=f"{BASE_URL}/catalog")
        )],
        [KeyboardButton(text="ℹ️ О нас"),
         KeyboardButton(text="📞 Контакты")],
    ]
    if is_admin_user:
        rows.append([
            KeyboardButton(text="➕ Добавить товар"),
            KeyboardButton(text="📋 Все товары")
        ])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )


# ─── /start ───────────────────────────────────────────────────
@dp.message(CommandStart())
async def cmd_start(message: Message):
    admin = is_admin(message.from_user.id)
    await message.answer(
        f"👋 Привет, <b>{message.from_user.first_name}</b>!\n\n"
        "Добро пожаловать в наш магазин.\n"
        + ("👑 Вы вошли как администратор.\n" if admin else "")
        + "\nВыберите раздел в меню:",
        parse_mode="HTML",
        reply_markup=main_menu(admin)
    )


# ─── /help ────────────────────────────────────────────────────
@dp.message(Command("help"))
async def cmd_help(message: Message):
    text = (
        "📖 <b>Команды бота:</b>\n\n"
        "🛍 <b>Открыть каталог</b> — Mini App с товарами\n"
        "ℹ️ <b>О нас</b> — информация о магазине\n"
        "📞 <b>Контакты</b> — связаться с нами\n"
    )
    if is_admin(message.from_user.id):
        text += (
            "\n<b>Команды администратора:</b>\n"
            "➕ <b>Добавить товар</b> — загрузить новый товар\n"
            "📋 <b>Все товары</b> — список с кнопками удаления\n"
        )
    await message.answer(text, parse_mode="HTML")


# ─── Отмена ───────────────────────────────────────────────────
@dp.message(F.text == "❌ Отмена")
async def cancel_handler(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Действие отменено.",
        reply_markup=main_menu(is_admin(message.from_user.id))
    )


# ══════════════════════════════════════════════════════════════
#  БЛОК АДМИНИСТРАТОРА
# ══════════════════════════════════════════════════════════════

@dp.message(F.text == "➕ Добавить товар")
async def admin_add_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        "📸 Отправьте <b>фото товара</b>:",
        parse_mode="HTML",
        reply_markup=cancel_kb()
    )
    await state.set_state(AddProduct.photo)


@dp.message(AddProduct.photo, F.photo)
async def add_photo(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo_id=photo_id)
    await message.answer("✏️ Введите <b>название товара</b>:", parse_mode="HTML")
    await state.set_state(AddProduct.name)


@dp.message(AddProduct.photo)
async def add_photo_wrong(message: Message):
    await message.answer("❗ Пожалуйста, отправьте именно <b>фото</b>.", parse_mode="HTML")


@dp.message(AddProduct.name, F.text)
async def add_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("💰 Введите <b>цену</b> (только цифры, в рублях):", parse_mode="HTML")
    await state.set_state(AddProduct.price)


@dp.message(AddProduct.price, F.text)
async def add_price(message: Message, state: FSMContext):
    if not message.text.strip().isdigit():
        await message.answer("❗ Введите только <b>цифры</b>, например: 1500", parse_mode="HTML")
        return
    await state.update_data(price=int(message.text.strip()))
    await message.answer("📝 Введите <b>описание товара</b>:", parse_mode="HTML")
    await state.set_state(AddProduct.description)


@dp.message(AddProduct.description, F.text)
async def add_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text.strip())
    await message.answer(
        "📐 Введите <b>доступные размеры</b> через запятую\n"
        "Например: <code>XS, S, M, L, XL</code>\n"
        "Или напишите <code>-</code> если размеры не нужны.",
        parse_mode="HTML"
    )
    await state.set_state(AddProduct.sizes)


@dp.message(AddProduct.sizes, F.text)
async def add_sizes(message: Message, state: FSMContext):
    raw = message.text.strip()
    sizes = [] if raw == "-" else [s.strip() for s in raw.split(",") if s.strip()]
    data = await state.get_data()
    await state.clear()

    product_id = await db.add_product(
        name=data["name"],
        price=data["price"],
        description=data["description"],
        sizes=sizes,
        photo_id=data["photo_id"],
    )

    sizes_text = ", ".join(sizes) if sizes else "—"
    await message.answer_photo(
        photo=data["photo_id"],
        caption=(
            f"✅ <b>Товар добавлен!</b> (ID: {product_id})\n\n"
            f"📌 <b>{data['name']}</b>\n"
            f"💰 {data['price']} ₽\n"
            f"📝 {data['description']}\n"
            f"📐 Размеры: {sizes_text}"
        ),
        parse_mode="HTML",
        reply_markup=main_menu(True)
    )


@dp.message(F.text == "📋 Все товары")
async def admin_list_products(message: Message):
    if not is_admin(message.from_user.id):
        return
    products = await db.get_products()
    if not products:
        await message.answer("📭 Товаров пока нет.")
        return

    for p in products:
        sizes_text = ", ".join(p["sizes"]) if p["sizes"] else "—"
        caption = (
            f"🆔 ID: {p['id']}\n"
            f"📌 <b>{p['name']}</b>\n"
            f"💰 {p['price']} ₽\n"
            f"📝 {p['description']}\n"
            f"📐 Размеры: {sizes_text}"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🗑 Удалить", callback_data=f"del_{p['id']}")
        ]])
        try:
            await message.answer_photo(
                photo=p["photo_id"], caption=caption,
                parse_mode="HTML", reply_markup=kb
            )
        except Exception:
            await message.answer(caption, parse_mode="HTML", reply_markup=kb)


@dp.callback_query(F.data.startswith("del_"))
async def delete_product(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа!")
        return
    product_id = int(callback.data.split("_")[1])
    await db.delete_product(product_id)
    await callback.message.delete()
    await callback.answer(f"✅ Товар #{product_id} удалён.")


# ══════════════════════════════════════════════════════════════
#  ИНФОРМАЦИОННЫЕ РАЗДЕЛЫ
# ══════════════════════════════════════════════════════════════

@dp.message(F.text == "ℹ️ О нас")

async def about(message: Message):

    await message.answer(

        "🏪 <b>О нашем магазине</b>\n\nБолее 300 успешных сделок🤝 \nГарантия возврата 14 дней ✅ \nЛюбые способы доставки📦 \nДоставлю все что угодно из разных стран мира🚚 \nВозврата нет❌ \nРеклама 900₽/24ч, 4100₽/7д",

        parse_mode="HTML"

    )

@dp.message(F.text == "📞 Контакты")

async def contacts(message: Message):

    await message.answer(

        "📞 <b>Контакты</b>\n\nВопросы, покупка \n@Isochrone_supply \n@O0XPANA",

        parse_mode="HTML"
    )


# ══════════════════════════════════════════════════════════════
#  ВЕБ-СЕРВЕР
# ══════════════════════════════════════════════════════════════

async def api_products(request: web.Request):
    products = await db.get_products()
    return web.json_response(products, headers={"Access-Control-Allow-Origin": "*"})


async def api_photo(request: web.Request):
    file_id = request.match_info["file_id"]
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.telegram.org/bot{BOT_TOKEN}/getFile",
                params={"file_id": file_id}
            ) as resp:
                data = await resp.json()
                if data.get("ok"):
                    file_path = data["result"]["file_path"]
                    raise web.HTTPFound(
                        f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
                    )
    except web.HTTPFound:
        raise
    except Exception as e:
        log.error(f"Photo proxy error: {e}")
    raise web.HTTPNotFound()


async def serve_catalog(request: web.Request):
    html_path = pathlib.Path(__file__).parent / "mini_app" / "index.html"
    return web.FileResponse(html_path)


def make_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/api/products",        api_products)
    app.router.add_get("/api/photo/{file_id}", api_photo)
    app.router.add_get("/catalog",             serve_catalog)
    return app


# ══════════════════════════════════════════════════════════════
#  ЗАПУСК
# ══════════════════════════════════════════════════════════════

async def main():
    await db.init()

    app = make_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    log.info(f"Web server started on port {PORT}")

    log.info("Bot polling started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
