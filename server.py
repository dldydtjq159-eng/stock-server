# server.py (최종 안정판)
import sqlite3
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

app = FastAPI(title="stock-server", version="4.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "/data/stock.db"

# ======================
# DB
# ======================
def get_db():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    db = get_db()
    cur = db.cursor()

    # stores
    cur.execute("""
    CREATE TABLE IF NOT EXISTS stores (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL
    )
    """)

    # categories meta
    cur.execute("""
    CREATE TABLE IF NOT EXISTS store_meta (
        store_id TEXT PRIMARY KEY,
        usage_text TEXT,
        categories TEXT
    )
    """)

    # items
    cur.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_id TEXT,
        category TEXT,
        name TEXT,
        real_stock INTEGER DEFAULT 0,
        min_stock INTEGER DEFAULT 0,
        price TEXT,
        updated_at TEXT
    )
    """)

    # ✅ 매장 중복 방지
    cur.execute("INSERT OR IGNORE INTO stores VALUES ('lab','김경영 요리 연구소')")
    cur.execute("INSERT OR IGNORE INTO stores VALUES ('youth','청년회관')")

    db.commit()
    db.close()

init_db()

# ======================
# API
# ======================
@app.get("/")
def root():
    return {"ok": True, "service": "stock-server", "version": "4.1"}

@app.get("/api/stores")
def stores():
    db = get_db()
    rows = db.execute("SELECT id,name FROM stores").fetchall()
    return {"stores": [{"id": r[0], "name": r[1]} for r in rows]}

@app.get("/api/stores/{store_id}/items/{category}")
def list_items(store_id: str, category: str):
    db = get_db()
    rows = db.execute("""
        SELECT id,name,real_stock,min_stock,price,updated_at
        FROM items WHERE store_id=? AND category=?
    """, (store_id, category)).fetchall()

    return {
        "items": [
            {
                "id": r[0],
                "name": r[1],
                "real_stock": r[2],
                "min_stock": r[3],
                "price": r[4],
                "updated_at": r[5],
            } for r in rows
        ]
    }

@app.get("/api/shortages/{store_id}")
def shortages(store_id: str):
    db = get_db()
    rows = db.execute("""
        SELECT category,name,real_stock,min_stock,price
        FROM items
        WHERE store_id=? AND real_stock < min_stock
    """, (store_id,)).fetchall()

    return {
        "shortages": [
            {
                "category": r[0],
                "name": r[1],
                "current": r[2],
                "need": r[3] - r[2],
                "price": r[4]
            } for r in rows
        ]
    }
