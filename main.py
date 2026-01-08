import asyncio, os, zipfile, shutil, aiohttp, logging
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

# Loyiha joylashgan papkani aniqlash (Alwaysdata uchun muhim)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ma'lumotlar bazasiga to'liq yo'lni ko'rsatamiz
db = Database(os.path.join(BASE_DIR, "bot_database.db"))

bot = Bot(
    token=os.getenv("BOT_TOKEN"), 
    default=DefaultBotProperties(parse_mode="HTML")
)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

OWNER_ID = int(os.getenv("ADMIN_ID", 0))
CH_ID = os.getenv("CHANNEL_ID")
CH_NAME = os.getenv("CHANNEL_USERNAME", "ish_reja_uz").replace("@", "")

class AdminStates(StatesGroup):
    waiting_for_time = State()
    waiting_for_tpl = State()
    waiting_for_footer = State()

# --- KLAVIATURALAR ---
def get_main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📅 Rejalarni ko'rish"), KeyboardButton(text="📈 Batafsil statistika")],
        [KeyboardButton(text="📁 Kategoriyalar"), KeyboardButton(text="⚙️ Sozlamalar")],
        [KeyboardButton(text="💎 Adminlarni boshqarish")]
    ], resize_keyboard=True)

def get_settings_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Shablon", callback_data="set_tpl"), InlineKeyboardButton(text="🖋 Footer", callback_data="set_footer")],
        [InlineKeyboardButton(text="📅 Chorak", callback_data="choose_q"), InlineKeyboardButton(text="🗑 Tozalash", callback_data="clear_cat")]
    ])

# --- ASOSIY FUNKSIYALAR ---
async def process_and_send(file_path, original_name):
    try:
        new_name = smart_rename(original_name)
        new_path = os.path.join(os.path.dirname(file_path), new_name)
        os.rename(file_path, new_path)
        
        if new_name.lower().endswith(('.xlsx', '.xls')): edit_excel(new_path)
        elif new_name.lower().endswith('.pdf'): add_pdf_watermark(new_path)
        elif new_name.lower().endswith('.docx'): edit_docx(new_path)

        cat = "BSB_CHSB" if any(x in new_name.lower() for x in ["bsb", "chsb"]) else \
              ("Yuqori" if any(x in new_name.lower() for x in ["5-","6-","7-","8-","9-","10-","11-"]) else "Boshlang'ich")

        caption_tpl = await db.get_setting('post_caption') or "{name} | @{channel}"
        footer = await db.get_setting('footer_text') or ""
        
        sent = await bot.send_document(
            CH_ID, 
            FSInputFile(new_path), 
            caption=caption_tpl.format(name=new_name, channel=CH_NAME) + f"\n\n{footer}"
        )
        
        await db.add_to_catalog(new_name, cat, f"https://t.me/{CH_NAME}/{sent.message_id}", sent.message_id)
        if os.path.exists(new_path): os.remove(new_path)
    except Exception as e:
        logger.error(f"Fayl yuborishda xatolik: {e}")

# --- HANDLERLAR ---
@dp.message(F.text == "/start")
async def cmd_start(m: Message):
    if await db.is_admin(m.from_user.id, OWNER_ID):
        await m.answer("🛡 <b>Admin Panel yuklandi.</b>", reply_markup=get_main_kb())

@dp.message(F.text.startswith("/add_admin"))
async def add_admin_handler(m: Message):
    if m.from_user.id != OWNER_ID:
        return await m.answer("❌ Bu buyruq faqat asosiy ega uchun!")
    try:
        new_id = int(m.text.split()[1])
        await db.add_admin(new_id)
        await m.answer(f"✅ Yangi admin qo'shildi! ID: <code>{new_id}</code>")
    except:
        await m.answer("⚠️ Format: <code>/add_admin ID</code>")

# (Boshqa handlerlar o'zgarishsiz qoladi - set_tpl, save_tpl, show_stats va h.k.)
# ... [Sizning original handlerlaringiz] ...

# --- WEB SERVER & MAIN ---
async def handle_root(request): 
    return web.Response(text="Bot Alwaysdata'da ishlamoqda 🚀")

async def main():
    await db.create_tables()
    scheduler.start()
    
    app = web.Application()
    app.router.add_get('/', handle_root)
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Alwaysdata PORT o'zgaruvchisini avtomatik beradi, IP '0.0.0.0' bo'lishi shart
    port = int(os.environ.get("PORT", 8100))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    logger.info(f"Server {port}-portda ishga tushdi")
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
