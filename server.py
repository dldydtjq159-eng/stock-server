# server.py (STABLE FINAL)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import sqlite3, os
from datetime import datetime

DATA_DIR = "/data"
os.makedirs(DATA_DIR, exist_ok=True)
DB = f"{DATA_DIR}/stock.db"

app = FastAPI(title="stock-server", version="FINAL")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

@app.on_event("startup")
def init():
    con = db()
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS stores(
        id TEXT PRIMARY KEY,
        name TEXT
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS categories(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_id TEXT,
        name TEXT
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS items(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_id TEXT,
        category_id INTEGER,
        name TEXT,
        stock REAL,
        min_stock REAL,
        unit TEXT,
        price TEXT,
        buy_link TEXT
    )""")

    if cur.execute("SELECT COUNT(*) FROM stores").fetchone()[0] == 0:
        cur.execute("INSERT INTO stores VALUES('s1','김경영 요리 연구소')")
        cur.execute("INSERT INTO stores VALUES('s2','청년회관')")

    con.commit()
    con.close()

@app.get("/api/stores")
def stores():
    con = db()
    rows = con.execute("SELECT * FROM stores").fetchall()
    con.close()
    return {"stores": [dict(r) for r in rows]}

@app.get("/api/categories")
def categories(store_id: str):
    con = db()
    rows = con.execute(
        "SELECT * FROM categories WHERE store_id=?", (store_id,)
    ).fetchall()
    con.close()
    return {"categories": [dict(r) for r in rows]}

@app.post("/api/categories")
def add_category(store_id: str, name: str):
    con = db()
    con.execute("INSERT INTO categories(store_id,name) VALUES(?,?)",
                (store_id, name))
    con.commit()
    con.close()
    return {"ok": True}

@app.get("/api/items")
def items(store_id: str, category_id: int):
    con = db()
    rows = con.execute("""
        SELECT * FROM items
        WHERE store_id=? AND category_id=?
    """, (store_id, category_id)).fetchall()
    con.close()
    return {"items": [dict(r) for r in rows]}

@app.post("/api/items")
def add_item(data: dict):
    con = db()
    con.execute("""
        INSERT INTO items(store_id,category_id,name,stock,min_stock,unit,price,buy_link)
        VALUES(?,?,?,?,?,?,?,?)
    """, (
        data["store_id"],
        data["category_id"],
        data["name"],
        data.get("stock", 0),
        data.get("min_stock", 0),
        data.get("unit", ""),
        data.get("price", ""),
        data.get("buy_link", "")
    ))
    con.commit()
    con.close()
    return {"ok": True}

@app.get("/api/shortages")
def shortages(store_id: str):
    con = db()
    rows = con.execute("""
        SELECT c.name category, i.name, i.stock, i.min_stock,
               (i.min_stock - i.stock) need, i.unit, i.price, i.buy_link
        FROM items i
        JOIN categories c ON c.id=i.category_id
        WHERE i.store_id=? AND i.stock < i.min_stock
    """, (store_id,)).fetchall()
    con.close()
    return {"shortages": [dict(r) for r in rows]}
