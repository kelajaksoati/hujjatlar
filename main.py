import os
import logging
import sys
from datetime import datetime
import zipfile
import shutil

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from dotenv import load_dotenv

from database import Database
from processor import smart_rename, edit_excel, add_pdf_watermark, edit_docx

# --- SOZLAMALAR ---
load_dotenv()
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

# O'zgaruvchilarni olish
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
CHANNEL_ID = os.getenv("CHANNEL_ID")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "ish_reja_uz").replace("@", "")

# Webhook sozlamalari (Alwaysdata uchun muhim)
# WEBHOOK_HOST: https://sizning_loginingiz.alwaysdata.net
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST") 
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# Web server sozlamalari
WEB_SERVER_HOST = "::" # IPv6 va IPv4 uchun (Alwaysdata uchun mos)
WEB_SERVER_PORT = int(os.getenv("PORT", 8100))

# --- BOT VA BAZA ---
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
db = Database("bot_database.db")

class AdminStates(StatesGroup):
    waiting_for_time = State() # Apscheduler o'rniga oddiy yuborish qoldirildi (soddalik uchun)
    waiting_for_tpl = State()

# --- HANDLERLAR ---

@dp.message(F.text == "/start")
async def cmd_start(m: Message):
    if await db.is_admin(m.from_user.id, ADMIN_ID):
        await m.answer(f"👋 Salom Admin! Bot webhook rejimida ishlamoqda.\nURL: {WEBHOOK_URL}")
    else:
        await m.answer("Bot ishlamoqda.")

# Fayllarni ishlash (Eski kod mantig'i saqlandi)
async def process_and_send(file_path, original_name):
    try:
        new_name = smart_rename(original_name)
        new_path = os.path.join(os.path.dirname(file_path), new_name)
        os.rename(file_path, new_path)
        
        if new_name.lower().endswith(('.xlsx', '.xls')): edit_excel(new_path)
        elif new_name.lower().endswith('.pdf'): add_pdf_watermark(new_path)
        elif new_name.lower().endswith('.docx'): edit_docx(new_path)

        caption_tpl = await db.get_setting('post_caption') or "{name} | @{channel}"
        footer = await db.get_setting('footer_text') or ""
        
        sent = await bot.send_document(
            CHANNEL_ID, 
            FSInputFile(new_path), 
            caption=caption_tpl.format(name=new_name, channel=CHANNEL_USERNAME) + f"\n\n{footer}"
        )
        await db.add_to_catalog(new_name, "General", f"https://t.me/{CHANNEL_USERNAME}/{sent.message_id}", sent.message_id)
        if os.path.exists(new_path): os.remove(new_path)
    except Exception as e:
        logger.error(f"Error processing {original_name}: {e}")

@dp.message(F.document)
async def handle_doc(m: Message):
    if not await db.is_admin(m.from_user.id, ADMIN_ID): return
    os.makedirs("downloads", exist_ok=True)
    
    path = f"downloads/{m.document.file_name}"
    await bot.download(m.document, destination=path)
    
    msg = await m.answer("⏳ Fayl qabul qilindi, ishlanmoqda...")
    
    if m.document.file_name.endswith(".zip"):
        ex_dir = f"downloads/zip_{datetime.now().timestamp()}"
        with zipfile.ZipFile(path, 'r') as z: z.extractall(ex_dir)
        for r, d, fs in os.walk(ex_dir):
            for f in fs:
                if not f.startswith('.') and "__MACOSX" not in r: 
                    await process_and_send(os.path.join(r, f), f)
        shutil.rmtree(ex_dir)
    else:
        await process_and_send(path, m.document.file_name)
    
    await msg.edit_text("✅ Bajarildi!")

# --- ISHGA TUSHIRISH (LIFESPAN) ---
async def on_startup(bot: Bot):
    await db.create_tables()
    # Webhookni o'rnatish
    await bot.set_webhook(WEBHOOK_URL)
    logger.info(f"Webhook o'rnatildi: {WEBHOOK_URL}")

def main():
    # Web dasturni sozlash
    app = web.Application()
    
    # Telegramdan keladigan so'rovlarni qabul qiluvchi handler
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
    )
    # So'rov yo'nalishini ro'yxatga olish
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    
    # Ilova va botni bog'lash
    setup_application(app, dp, bot=bot)
    
    # Startup funksiyasini qo'shish
    app.on_startup.append(lambda x: on_startup(bot))

    # Serverni ishga tushirish
    web.run_app(app, host=WEB_SERVER_HOST, port=WEB_SERVER_PORT)

if __name__ == "__main__":
    main()
