import aiosqlite
import json

DB_PATH = "shop.db"

class Database:
    def __init__(self):
        self.path = DB_PATH

    async def init(self):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    name        TEXT    NOT NULL,
                    price       INTEGER NOT NULL,
                    description TEXT,
                    sizes       TEXT,
                    photo_id    TEXT,
                    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()

    async def add_product(self, name, price, description, sizes, photo_id):
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                "INSERT INTO products (name, price, description, sizes, photo_id) VALUES (?,?,?,?,?)",
                (name, price, description, json.dumps(sizes, ensure_ascii=False), photo_id)
            )
            await db.commit()
            return cursor.lastrowid

    async def get_products(self):
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM products ORDER BY created_at DESC") as cursor:
                rows = await cursor.fetchall()
                result = []
                for row in rows:
                    result.append({
                        "id":          row["id"],
                        "name":        row["name"],
                        "price":       row["price"],
                        "description": row["description"] or "",
                        "sizes":       json.loads(row["sizes"]) if row["sizes"] else [],
                        "photo_id":    row["photo_id"] or "",
                    })
                return result

    async def delete_product(self, product_id):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("DELETE FROM products WHERE id = ?", (product_id,))
            await db.commit()

    async def get_product(self, product_id):
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM products WHERE id = ?", (product_id,)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None
                return {
                    "id":          row["id"],
                    "name":        row["name"],
                    "price":       row["price"],
                    "description": row["description"] or "",
                    "sizes":       json.loads(row["sizes"]) if row["sizes"] else [],
                    "photo_id":    row["photo_id"] or "",
                }
