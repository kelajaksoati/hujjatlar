import aiosqlite
import os

class Database:
    def __init__(self, db_path="bot_database.db"):
        self.db_path = db_path

    async def create_tables(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS catalog (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    name TEXT, category TEXT, link TEXT, msg_id INTEGER
                )
            """)
            await db.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
            await db.execute("CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)")
            
            defaults = [
                ('quarter', '1'),
                ('post_caption', "📚 <b>{name}</b>\n\n✅ Kanal: @{channel}"),
                ('footer_text', "\n\n📩 Murojaat: @admin_user"),
                ('catalog_header', "📂 <b>FANLARDAN {quarter}-CHORAK REJALARI</b>")
            ]
            for key, val in defaults:
                await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))
            await db.commit()

    async def set_setting(self, key, value):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
            await db.commit()

    async def get_setting(self, key):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else ""

    async def is_admin(self, user_id, owner_id):
        if int(user_id) == int(owner_id): return True
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,)) as cursor:
                res = await cursor.fetchone()
                return res is not None

    async def add_admin(self, user_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,))
            await db.commit()

    async def add_to_catalog(self, name, category, link, msg_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT INTO catalog (name, category, link, msg_id) VALUES (?, ?, ?, ?)", 
                             (name, category, link, msg_id))
            await db.commit()
            
    async def get_stats(self):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM catalog") as cursor:
                res = await cursor.fetchone()
                return res[0] if res else 0
