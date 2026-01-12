import asyncio, os, logging, sys
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
        [InlineKeyboardButton(text="📅 Chorak", callback_data="choose_q"), InlineKeyboardButton(text="🗑 Tozalash", callback_data="clear_cat")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_main")]
    ])

def get_back_to_settings_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="back_to_settings")]
    ])

# --- ASOSIY FUNKSIYA ---
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
        
        sent = await bot.send_document(CH_ID, FSInputFile(new_path), 
            caption=caption_tpl.format(name=new_name, channel=CH_NAME) + f"\n\n{footer}")
        
        await db.add_to_catalog(new_name, cat, f"https://t.me/{CH_NAME}/{sent.message_id}", sent.message_id)
        if os.path.exists(new_path): os.remove(new_path)
    except Exception as e:
        logger.error(f"Xatolik process_and_send'da: {e}")

# --- HANDLERLAR ---

# ORQAGA QAYTISH HANDLERLARI
@dp.callback_query(F.data == "back_to_main")
async def back_to_main_handler(c: CallbackQuery):
    await c.message.delete()
    await c.message.answer("🏠 Asosiy menyu:", reply_markup=get_main_kb())
    await c.answer()

@dp.callback_query(F.data == "back_to_settings")
async def back_to_settings_handler(c: CallbackQuery, state: FSMContext):
    await state.clear()
    await c.message.edit_text("⚙️ <b>Sozlamalar bo'limi:</b>", reply_markup=get_settings_kb())
    await c.answer()

@dp.message(F.text == "/start")
async def cmd_start(m: Message):
    if await db.is_admin(m.from_user.id, OWNER_ID):
        await m.answer("🛡 <b>Admin Panel yuklandi.</b>", reply_markup=get_main_kb())

@dp.message(F.text == "⚙️ Sozlamalar")
async def settings_menu(m: Message):
    if await db.is_admin(m.from_user.id, OWNER_ID):
        await m.answer("⚙️ <b>Sozlamalar bo'limi:</b>", reply_markup=get_settings_kb())

@dp.callback_query(F.data == "set_tpl")
async def set_tpl_start(c: CallbackQuery, state: FSMContext):
    await c.message.edit_text("📝 Yangi shablonni yuboring.\nNamuna: <code>{name} fayli @{channel} kanalidan</code>", reply_markup=get_back_to_settings_kb())
    await state.set_state(AdminStates.waiting_for_tpl)
    await c.answer()

@dp.message(AdminStates.waiting_for_tpl)
async def save_tpl(m: Message, state: FSMContext):
    await db.set_setting('post_caption', m.text)
    await m.answer("✅ Post shabloni saqlandi.", reply_markup=get_main_kb())
    await state.clear()

@dp.callback_query(F.data == "set_footer")
async def set_footer_start(c: CallbackQuery, state: FSMContext):
    await c.message.edit_text("🖋 Post tagiga chiqadigan footer matnini yuboring:", reply_markup=get_back_to_settings_kb())
    await state.set_state(AdminStates.waiting_for_footer)
    await c.answer()

@dp.message(AdminStates.waiting_for_footer)
async def save_footer(m: Message, state: FSMContext):
    await db.set_setting('footer_text', m.text)
    await m.answer("✅ Footer matni saqlandi.", reply_markup=get_main_kb())
    await state.clear()

@dp.callback_query(F.data == "choose_q")
async def choose_quarter(c: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1-chorak", callback_data="q_1"), InlineKeyboardButton(text="2-chorak", callback_data="q_2")],
        [InlineKeyboardButton(text="3-chorak", callback_data="q_3"), InlineKeyboardButton(text="4-chorak", callback_data="q_4")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_settings")]
    ])
    await c.message.edit_text("📅 Chorakni tanlang:", reply_markup=kb)

@dp.callback_query(F.data.startswith("q_"))
async def save_quarter(c: CallbackQuery):
    q = c.data.split("_")[1]
    await db.set_setting('quarter', q)
    await c.message.edit_text(f"✅ Tizim <b>{q}-chorak</b>ga sozlandi.", reply_markup=get_settings_kb())
    await c.answer()

@dp.callback_query(F.data == "clear_cat")
async def clear_catalog_confirm(c: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ HA, o'chirish", callback_data="confirm_clear")],
        [InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="back_to_settings")]
    ])
    await c.message.edit_text("⚠️ <b>DIQQAT!</b> Katalogni tozalamoqchimisiz?", reply_markup=kb)

@dp.callback_query(F.data == "confirm_clear")
async def clear_catalog_done(c: CallbackQuery):
    await db.clear_catalog()
    await c.message.edit_text("🗑 Katalog tozalandi!", reply_markup=get_settings_kb())
    await c.answer()

@dp.message(F.text == "💎 Adminlarni boshqarish")
async def manage_admins(m: Message):
    if not await db.is_admin(m.from_user.id, OWNER_ID): return
    admins = await db.get_admins()
    text = f"👥 <b>Adminlar ro'yxati:</b>\n\n👑 Asosiy: <code>{OWNER_ID}</code>\n"
    for adm in admins: text += f"👤 Yordamchi: <code>{adm[0]}</code>\n"
    text += "\nQo'shish: <code>/add_admin ID</code>"
    await m.answer(text)

@dp.message(F.text.startswith("/add_admin"))
async def process_add_admin(m: Message):
    if m.from_user.id != OWNER_ID: return
    try:
        new_id = int(m.text.split()[1])
        await db.add_admin(new_id)
        await m.answer(f"✅ Foydalanuvchi <code>{new_id}</code> qo'shildi.")
    except:
        await m.answer("❌ Xato! Foydalanish: /add_admin ID")

@dp.message(F.text == "📅 Rejalarni ko'rish")
async def view_plans(m: Message):
    if not await db.is_admin(m.from_user.id, OWNER_ID): return
    plans = scheduler.get_jobs()
    if not plans: return await m.answer("📭 Rejalashtirilgan fayllar yo'q.")
    text = "⏳ <b>Kutilayotgan rejalar:</b>\n\n"
    for job in plans: text += f"📄 {job.args[1]}\n⏰ {job.next_run_time.strftime('%d.%m.%Y %H:%M')}\n\n"
    await m.answer(text)

@dp.message(F.document)
async def handle_doc(m: Message, state: FSMContext):
    if not await db.is_admin(m.from_user.id, OWNER_ID): return
    os.makedirs(os.path.join(BASE_DIR, "downloads"), exist_ok=True)
    path = os.path.join(BASE_DIR, "downloads", m.document.file_name)
    await bot.download(m.document, destination=path)
    await state.update_data(f_path=path, f_name=m.document.file_name)
    await m.answer("📅 Vaqtni kiriting (DD.MM.YYYY HH:MM)\nHozir yuborish uchun <b>0</b>:")
    await state.set_state(AdminStates.waiting_for_time)

@dp.message(AdminStates.waiting_for_time)
async def schedule_step(m: Message, state: FSMContext):
    data = await state.get_data()
    if m.text == "0":
        await process_and_send(data['f_path'], data['f_name'])
        await m.answer("✅ Fayl kanalga yuborildi.")
    else:
        try:
            run_time = datetime.strptime(m.text, "%d.%m.%Y %H:%M")
            scheduler.add_job(process_and_send, 'date', run_date=run_time, args=[data['f_path'], data['f_name']])
            await m.answer(f"⏳ Fayl rejalashtirildi: {m.text}")
        except: 
            await m.answer("❌ Xato format. Namuna: 10.01.2026 23:00")
            return
    await state.clear()

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
async def create_catalog_handler(c: CallbackQuery):
    cat = c.data.split("_", 1)[1]
    items = await db.get_catalog(cat)
    if not items: 
        await c.answer("Ushbu kategoriya bo'yicha fayllar topilmadi", show_alert=True)
        return
    q = await db.get_setting('quarter') or "?"
    text = f"📂 <b>{q}-CHORAK REJALARI ({cat})</b>\n\n"
    for i, (name, link) in enumerate(items, 1): 
        text += f"{i}. <a href='{link}'>{name}</a>\n"
    await bot.send_message(CH_ID, text, disable_web_page_preview=True)
    await c.answer("Katalog kanalga yuborildi!")

@dp.message(F.text == "📈 Batafsil statistika")
async def show_stats(m: Message):
    if not await db.is_admin(m.from_user.id, OWNER_ID): return
    count = await db.get_stats()
    await m.answer(f"📊 <b>Statistika</b>\n\n✅ Jami fayllar: <b>{count} ta</b>\n📡 Kanal: @{CH_NAME}")

async def handle_root(request): return web.Response(text="Bot Live 🚀")

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
