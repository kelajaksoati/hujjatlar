import os
import logging
import sys
import asyncio
import zipfile
import shutil
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Message, FSInputFile
from aiogram.fsm.state import State, StatesGroup
from dotenv import load_dotenv

from database import Database
from processor import smart_rename, edit_excel, add_pdf_watermark, edit_docx

# --- SOZLAMALAR ---
load_dotenv()
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
CHANNEL_ID = os.getenv("CHANNEL_ID")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "ish_reja_uz").replace("@", "")

# --- BOT VA BAZA ---
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
db = Database("bot_database.db")

class AdminStates(StatesGroup):
    waiting_for_time = State()
    waiting_for_tpl = State()

# --- FUNKSIYALAR ---
async def process_and_send(file_path, original_name):
    try:
        new_name = smart_rename(original_name)
        new_path = os.path.join(os.path.dirname(file_path), new_name)
        os.rename(file_path, new_path)
        
        # Fayl turini tekshirish va tahrirlash
        ext = new_name.lower()
        if ext.endswith(('.xlsx', '.xls')):
            edit_excel(new_path)
        elif ext.endswith('.pdf'):
            add_pdf_watermark(new_path)
        elif ext.endswith('.docx'):
            edit_docx(new_path)

        caption_tpl = await db.get_setting('post_caption') or "{name} | @{channel}"
        footer = await db.get_setting('footer_text') or ""
        
        # Kanalga yuborish
        sent = await bot.send_document(
            CHANNEL_ID, 
            FSInputFile(new_path), 
            caption=caption_tpl.format(name=new_name, channel=CHANNEL_USERNAME) + f"\n\n{footer}"
        )
        
        # Bazaga qo'shish
        await db.add_to_catalog(new_name, "General", f"https://t.me/{CHANNEL_USERNAME}/{sent.message_id}", sent.message_id)
        
        if os.path.exists(new_path):
            os.remove(new_path)
    except Exception as e:
        logger.error(f"Xatolik yuz berdi ({original_name}): {e}")

# --- HANDLERLAR ---
@dp.message(F.text == "/start")
async def cmd_start(m: Message):
    if await db.is_admin(m.from_user.id, ADMIN_ID):
        await m.answer("👋 Salom Admin! Bot <b>Polling</b> rejimida muvaffaqiyatli ishlamoqda.")
    else:
        await m.answer("Bot ishlamoqda. Fayllar kanalda: @ish_reja_uz")

@dp.message(F.document)
async def handle_doc(m: Message):
    if not await db.is_admin(m.from_user.id, ADMIN_ID):
        return
    
    os.makedirs("downloads", exist_ok=True)
    path = f"downloads/{m.document.file_name}"
    await bot.download(m.document, destination=path)
    
    msg = await m.answer("⏳ Fayl ishlanmoqda...")
    
    if m.document.file_name.lower().endswith(".zip"):
        ex_dir = f"downloads/zip_{datetime.now().timestamp()}"
        with zipfile.ZipFile(path, 'r') as z:
            z.extractall(ex_dir)
        for r, d, fs in os.walk(ex_dir):
            for f in fs:
                if not f.startswith('.') and "__MACOSX" not in r:
                    await process_and_send(os.path.join(r, f), f)
        shutil.rmtree(ex_dir)
    else:
        await process_and_send(path, m.document.file_name)
    
    await msg.edit_text("✅ Bajarildi!")

async def main():
    await db.create_tables()
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
