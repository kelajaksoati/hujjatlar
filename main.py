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
from aiogram.types import Message, FSInputFile, ReplyKeyboardMarkup, KeyboardButton
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

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
db = Database("bot_database.db")

# --- ADMIN TUGMALARI ---
def get_admin_kb():
    kb = [
        [KeyboardButton(text="📊 Statistika")],
        [KeyboardButton(text="📂 Katalog"), KeyboardButton(text="⚙️ Sozlamalar")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# --- FUNKSIYALAR ---
async def process_and_send(file_path, original_name):
    try:
        new_name = smart_rename(original_name)
        new_path = os.path.join(os.path.dirname(file_path), new_name)
        os.rename(file_path, new_path)
        
        ext = new_name.lower()
        if ext.endswith(('.xlsx', '.xls')):
            edit_excel(new_path)
        elif ext.endswith('.pdf'):
            add_pdf_watermark(new_path)
        elif ext.endswith('.docx'):
            edit_docx(new_path)

        caption_tpl = await db.get_setting('post_caption')
        footer = await db.get_setting('footer_text')
        
        sent = await bot.send_document(
            CHANNEL_ID, 
            FSInputFile(new_path), 
            caption=caption_tpl.format(name=new_name, channel=CHANNEL_USERNAME) + f"\n\n{footer}"
        )
        
        await db.add_to_catalog(new_name, "General", f"https://t.me/{CHANNEL_USERNAME}/{sent.message_id}", sent.message_id)
        if os.path.exists(new_path): os.remove(new_path)
    except Exception as e:
        logger.error(f"Xatolik: {e}")

# --- HANDLERLAR ---
@dp.message(F.text == "/start")
async def cmd_start(m: Message):
    is_admin = await db.is_admin(m.from_user.id, ADMIN_ID)
    if is_admin:
        await m.answer(
            "👋 <b>Xush kelibsiz, Admin!</b>\nMenyudan foydalaning yoki fayl yuboring.", 
            reply_markup=get_admin_kb()
        )
    else:
        await m.answer(f"Ushbu bot faqat adminlar uchun. Fayllar kanalda: @{CHANNEL_USERNAME}")

@dp.message(F.text == "📊 Statistika")
async def show_stats(m: Message):
    if await db.is_admin(m.from_user.id, ADMIN_ID):
        count = await db.get_stats()
        await m.answer(f"📊 Bazadagi jami fayllar soni: <b>{count}</b> ta")

@dp.message(F.document)
async def handle_doc(m: Message):
    if not await db.is_admin(m.from_user.id, ADMIN_ID): return
    
    os.makedirs("downloads", exist_ok=True)
    path = f"downloads/{m.document.file_name}"
    await bot.download(m.document, destination=path)
    
    msg = await m.answer("⏳ Fayl brendlanmoqda...")
    # ZIP yoki oddiy faylni qayta ishlash mantiqi bu yerda
    await process_and_send(path, m.document.file_name)
    await msg.edit_text("✅ Fayl tayyor va kanalga yuborildi!")

async def main():
    await db.create_tables()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
