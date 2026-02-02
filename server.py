import os
import sqlite3
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# =========================
SERVICE = "stock-server"
VERSION = "v5.0"

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "dldydtjq159")
DATA_DIR = os.getenv("DATA_DIR", "/data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "stock.db")

app = FastAPI(title=SERVICE, version=VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_headers=["*"],
    allow_methods=["*"],
)

# =========================
def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def admin_required(token: Optional[str]):
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="ADMIN_TOKEN invalid")

# =========================
def init_db():
    con = db()
    cur = con.cursor()

    cur.executescript("""
    CREATE TABLE IF NOT EXISTS stores(
        id TEXT PRIMARY KEY,
        name TEXT
    );

    CREATE TABLE IF NOT EXISTS meta(
        store_id TEXT PRIMARY KEY,
        usage_text TEXT
    );

    CREATE TABLE IF NOT EXISTS categories(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_id TEXT,
        key TEXT,
        label TEXT,
        sort INTEGER
    );

    CREATE TABLE IF NOT EXISTS items(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_id TEXT,
        category_key TEXT,
        name TEXT,
        current_stock REAL,
        min_stock REAL,
        unit TEXT,
        price TEXT,
        vendor TEXT,
        storage TEXT,
        origin TEXT,
        buy_link TEXT,
        memo TEXT,
        updated_at TEXT
    );
    """)

    cur.execute("INSERT OR IGNORE INTO stores VALUES ('lab','김경영 요리 연구소')")
    cur.execute("INSERT OR IGNORE INTO stores VALUES ('youth','청년회관')")
    cur.execute("INSERT OR IGNORE INTO meta VALUES ('lab','')")
    cur.execute("INSERT OR IGNORE INTO meta VALUES ('youth','')")

    con.commit()
    con.close()

init_db()

# =========================
@app.get("/")
def root():
    return {"ok": True, "service": SERVICE, "version": VERSION}

# =========================
@app.get("/api/stores")
def stores():
    con = db()
    rows = con.execute("SELECT * FROM stores").fetchall()
    con.close()
    return {"stores": [dict(r) for r in rows]}

# =========================
@app.get("/api/stores/{store_id}/meta")
def store_meta(store_id: str):
    con = db()
    meta = con.execute("SELECT usage_text FROM meta WHERE store_id=?", (store_id,)).fetchone()
    cats = con.execute(
        "SELECT key,label,sort FROM categories WHERE store_id=? ORDER BY sort",
        (store_id,)
    ).fetchall()
    con.close()
    return {
        "meta": {
            "usage_text": meta["usage_text"] if meta else "",
            "categories": [dict(c) for c in cats]
        }
    }

# =========================
@app.put("/api/stores/{store_id}/meta")
def save_meta(
    store_id: str,
    payload: dict,
    x_admin_token: Optional[str] = Header(None)
):
    admin_required(x_admin_token)
    con = db()
    cur = con.cursor()

    usage = payload.get("usage_text", "")
    cats = payload.get("categories", [])

    cur.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (store_id, usage))
    cur.execute("DELETE FROM categories WHERE store_id=?", (store_id,))
    for c in cats:
        cur.execute(
            "INSERT INTO categories(store_id,key,label,sort) VALUES(?,?,?,?)",
            (store_id, c["key"], c["label"], c.get("sort", 0))
        )

    con.commit()
    con.close()
    return {"ok": True}

# =========================
@app.get("/api/stores/{store_id}/items/{category_key}")
def items(store_id: str, category_key: str):
    con = db()
    rows = con.execute("""
        SELECT * FROM items
        WHERE store_id=? AND category_key=?
        ORDER BY name
    """, (store_id, category_key)).fetchall()
    con.close()
    return {"items": [dict(r) for r in rows]}

# =========================
@app.post("/api/stores/{store_id}/items/{category_key}")
def add_item(store_id: str, category_key: str, payload: dict):
    con = db()
    cur = con.cursor()

    cur.execute("""
        INSERT INTO items
        (store_id,category_key,name,current_stock,min_stock,unit,price,vendor,storage,origin,buy_link,memo,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        store_id,
        category_key,
        payload["name"],
        payload.get("current_stock", 0),
        payload.get("min_stock", 0),
        payload.get("unit", ""),
        payload.get("price", ""),
        payload.get("vendor", ""),
        payload.get("storage", ""),
        payload.get("origin", ""),
        payload.get("buy_link", ""),
        payload.get("memo", ""),
        now()
    ))

    con.commit()
    con.close()
    return {"ok": True}

# =========================
@app.put("/api/stores/{store_id}/items/{category_key}/{item_id}")
def update_item(store_id: str, category_key: str, item_id: int, payload: dict):
    con = db()
    cur = con.cursor()

    sets = []
    values = []
    for k, v in payload.items():
        sets.append(f"{k}=?")
        values.append(v)

    values.append(now())
    values.append(item_id)

    cur.execute(
        f"UPDATE items SET {','.join(sets)}, updated_at=? WHERE id=?",
        values
    )

    con.commit()
    con.close()
    return {"updated_at": now()}

# =========================
@app.delete("/api/stores/{store_id}/items/{category_key}/{item_id}")
def delete_item(store_id: str, category_key: str, item_id: int):
    con = db()
    con.execute("DELETE FROM items WHERE id=?", (item_id,))
    con.commit()
    con.close()
    return {"ok": True}

# =========================
@app.get("/api/shortages/{store_id}")
def shortages(store_id: str):
    con = db()
    rows = con.execute("""
        SELECT * FROM items
        WHERE store_id=? AND current_stock < min_stock
    """, (store_id,)).fetchall()
    con.close()

    result = []
    for r in rows:
        need = (r["min_stock"] or 0) - (r["current_stock"] or 0)
        result.append({
            "id": r["id"],
            "category_key": r["category_key"],
            "category_label": r["category_key"],
            "name": r["name"],
            "current_stock": r["current_stock"],
            "min_stock": r["min_stock"],
            "need": need,
            "unit": r["unit"],
            "price": r["price"],
            "buy_link": r["buy_link"]
        })

    return {"shortages": result}
