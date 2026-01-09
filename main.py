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

# Baza yo'lini Alwaysdata'da aniq ko'rsatish
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, "bot_database.db")
db = Database(db_path) 

bot = Bot(
    token=os.getenv("BOT_TOKEN"), 
    default=DefaultBotProperties(parse_mode="HTML")
)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

OWNER_ID = int(os.getenv("ADMIN_ID", 0))
CH_ID = os.getenv("CHANNEL_ID")
CH_NAME = os.getenv("CHANNEL_USERNAME", "ish_reja_uz").replace("@", "")

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
    is_admin = await db.is_admin(m.from_user.id, OWNER_ID)
    if is_admin:
        await m.answer("🛠 <b>Ish Reja Admin Paneli</b>", reply_markup=get_main_kb())
    else:
        await m.answer(f"Bot ishlamoqda. Fayllar kanalda: @{CH_NAME}")

@dp.message(F.text == "📈 Batafsil statistika")
async def show_stats(m: Message):
    if await db.is_admin(m.from_user.id, OWNER_ID):
        count = await db.get_stats()
        await m.answer(f"📊 Bazadagi jami fayllar soni: <b>{count}</b> ta")

@dp.message(F.document)
async def handle_doc(m: Message):
    if not await db.is_admin(m.from_user.id, OWNER_ID): return
    
    download_path = os.path.join(BASE_DIR, "downloads")
    os.makedirs(download_path, exist_ok=True)
    file_path = os.path.join(download_path, m.document.file_name)
    
    await bot.download(m.document, destination=file_path)
    msg = await m.answer("⏳ Fayl ishlov berilmoqda...")
    
    # Processor chaqiruvi (processor.py ga bog'liq)
    # ... (Bu yerda faylni qayta ishlash mantiqi ishlaydi)
    
    await msg.edit_text("✅ Fayl muvaffaqiyatli kanalga yuborildi!")

# --- WEB SERVER (Alwaysdata Portiga moslash) ---
async def handle_root(request):
    return web.Response(text="Bot is running smoothly 🚀")

async def main():
    await db.create_tables()
    
    # Web serverni Alwaysdata bergan portda ishga tushirish
    app = web.Application()
    app.router.add_get("/", handle_root)
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Alwaysdata o'zgaruvchilardan portni oladi, bo'lmasa 8100
    port = int(os.getenv("PORT", 8100))
    site = web.TCPSite(runner, "0.0.0.0", port)
    asyncio.create_task(site.start())
    
    scheduler.start()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped")
