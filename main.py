import asyncio, os, zipfile, shutil, aiohttp, logging, sys
from datetime import datetime
from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties 
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, FSInputFile
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiohttp import web
from dotenv import load_dotenv

from database import Database
from processor import smart_rename, edit_excel, add_pdf_watermark, edit_docx

# --- SOZLAMALAR ---
load_dotenv()
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, "bot_database.db")
db = Database(db_path) 

bot = Bot(token=os.getenv("BOT_TOKEN"), default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
scheduler = AsyncIOScheduler()

OWNER_ID = int(os.getenv("ADMIN_ID", 0))
CH_ID = os.getenv("CHANNEL_ID")
CH_NAME = os.getenv("CHANNEL_USERNAME", "ish_reja_uz").replace("@", "")

class AdminStates(StatesGroup):
    waiting_for_time = State()

# --- KLAVIATURALAR ---
def get_main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📅 Rejalarni ko'rish"), KeyboardButton(text="📈 Batafsil statistika")],
        [KeyboardButton(text="📁 Kategoriyalar"), KeyboardButton(text="⚙️ Sozlamalar")],
        [KeyboardButton(text="💎 Adminlarni boshqarish")]
    ], resize_keyboard=True)

# --- HANDLERLAR ---
@dp.message(F.text == "/start")
async def cmd_start(m: Message):
    if await db.is_admin(m.from_user.id, OWNER_ID):
        await m.answer("🛡 <b>Admin Panel yuklandi.</b>", reply_markup=get_main_kb())

@dp.message(F.text == "💎 Adminlarni boshqarish")
async def manage_admins(m: Message):
    # Faqat OWNER_ID emas, barcha adminlar ko'ra olishi uchun tekshiruvni yumshatdik
    if not await db.is_admin(m.from_user.id, OWNER_ID): return 
    
    admins = await db.get_admins()
    text = f"👥 <b>Adminlar ro'yxati:</b>\n\n👑 Asosiy: <code>{OWNER_ID}</code>\n"
    for adm in admins: 
        text += f"👤 Yordamchi: <code>{adm[0]}</code>\n"
    text += "\nQo'shish: <code>/add_admin ID</code>"
    await m.answer(text)

@dp.message(F.text.startswith("/add_admin"))
async def add_admin_handler(m: Message):
    if m.from_user.id != OWNER_ID: return
    try:
        new_id = int(m.text.split()[1])
        await db.add_admin(new_id)
        await m.answer(f"✅ Yangi admin qo'shildi: <code>{new_id}</code>")
    except:
        await m.answer("⚠️ Format: <code>/add_admin ID</code>")

@dp.message(F.text == "📁 Kategoriyalar")
async def show_cats(m: Message):
    if not await db.is_admin(m.from_user.id, OWNER_ID): return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Boshlang'ich", callback_data="cat_Boshlang'ich")],
        [InlineKeyboardButton(text="Yuqori sinflar", callback_data="cat_Yuqori")],
        [InlineKeyboardButton(text="BSB/CHSB", callback_data="cat_BSB_CHSB")]
    ])
    await m.answer("📁 Kategoriyani tanlang:", reply_markup=kb)

@dp.callback_query(F.data.startswith("cat_"))
async def create_catalog(c: CallbackQuery):
    cat = c.data.split("_", 1)[1]
    items = await db.get_catalog(cat)
    if not items: return await c.answer("Fayllar topilmadi", show_alert=True)
    text = f"<b>Katalog: {cat}</b>\n\n"
    for i, (name, link) in enumerate(items, 1): 
        text += f"{i}. <a href='{link}'>{name}</a>\n"
    await bot.send_message(CH_ID, text, disable_web_page_preview=True)
    await c.answer("Kanalga yuborildi!")

@dp.message(F.text == "📈 Batafsil statistika")
async def show_stats(m: Message):
    if not await db.is_admin(m.from_user.id, OWNER_ID): return
    count = await db.get_stats()
    await m.answer(f"📊 <b>Statistika</b>\n\n✅ Jami fayllar: <b>{count} ta</b>\n📡 Kanal: @{CH_NAME}")

# --- ASOSIY ISHGA TUSHIRISH (Alwaysdata) ---
async def handle_root(request): return web.Response(text="Bot is running")

async def main():
    await db.create_tables()
    scheduler.start()
    app = web.Application()
    app.router.add_get('/', handle_root)
    runner = web.AppRunner(app); await runner.setup()
    port = int(os.environ.get("PORT", 8100))
    await web.TCPSite(runner, '0.0.0.0', port).start()
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
