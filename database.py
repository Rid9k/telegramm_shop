import os
import json
import asyncpg

class Database:
    def __init__(self):
        self.url = os.getenv("DATABASE_URL")
        self.pool = None

    async def init(self):
        self.pool = await asyncpg.create_pool(self.url)
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id          SERIAL PRIMARY KEY,
                    name        TEXT    NOT NULL,
                    price       INTEGER NOT NULL,
                    description TEXT,
                    sizes       TEXT,
                    photo_id    TEXT,
                    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    async def add_product(self, name, price, description, sizes, photo_id):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO products (name, price, description, sizes, photo_id) "
                "VALUES ($1, $2, $3, $4, $5) RETURNING id",
                name, price, description,
                json.dumps(sizes, ensure_ascii=False), photo_id
            )
            return row["id"]

    async def get_products(self):
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM products ORDER BY created_at DESC"
            )
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
        async with self.pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM products WHERE id = $1", product_id
            )

    async def get_product(self, product_id):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM products WHERE id = $1", product_id
            )
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
