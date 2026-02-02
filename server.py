from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
from datetime import datetime
from typing import Optional

DB = "data.db"
ADMIN_TOKEN = "dldydtjq159"

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# =====================
# DB
# =====================
def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def init_db():
    c = db()
    c.execute("""
    CREATE TABLE IF NOT EXISTS stores (
        id TEXT PRIMARY KEY,
        name TEXT
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        store_id TEXT,
        key TEXT,
        label TEXT,
        sort INTEGER
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS items (
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
    )
    """)
    c.commit()
    c.close()

init_db()

# =====================
# STORES
# =====================
@app.get("/api/stores")
def stores():
    c = db()
    rows = c.execute("SELECT * FROM stores").fetchall()
    if not rows:
        c.execute("INSERT INTO stores VALUES (?,?)", ("lab", "기본매장"))
        c.execute("INSERT INTO categories VALUES (?,?,?,?)", ("lab","default","기본",0))
        c.commit()
        rows = c.execute("SELECT * FROM stores").fetchall()
    return {"stores":[dict(r) for r in rows]}

@app.get("/api/stores/{store_id}/meta")
def store_meta(store_id: str):
    c = db()
    cats = c.execute(
        "SELECT key,label,sort FROM categories WHERE store_id=? ORDER BY sort",
        (store_id,)
    ).fetchall()
    return {
        "meta":{
            "categories":[dict(r) for r in cats],
            "usage_text":""
        }
    }

@app.put("/api/stores/{store_id}/meta")
def update_meta(
    store_id: str,
    payload: dict,
    x_admin_token: Optional[str] = Header(None)
):
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(401,"unauthorized")

    c = db()
    c.execute("DELETE FROM categories WHERE store_id=?", (store_id,))
    for cat in payload.get("categories",[]):
        c.execute(
            "INSERT INTO categories VALUES (?,?,?,?)",
            (store_id,cat["key"],cat["label"],cat.get("sort",0))
        )
    c.commit()
    return {"ok":True}

# =====================
# ITEMS
# =====================
@app.get("/api/stores/{store_id}/items/{category_key}")
def items(store_id:str, category_key:str):
    c = db()
    rows = c.execute("""
        SELECT * FROM items
        WHERE store_id=? AND category_key=?
        ORDER BY name
    """,(store_id,category_key)).fetchall()
    return {"items":[dict(r) for r in rows]}

@app.post("/api/stores/{store_id}/items/{category_key}")
def add_item(store_id:str, category_key:str, payload:dict):
    c = db()
    c.execute("""
    INSERT INTO items
    (store_id,category_key,name,current_stock,min_stock,unit,price,vendor,storage,origin,buy_link,memo,updated_at)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
    """,(
        store_id,category_key,payload["name"],
        payload.get("current_stock",0),
        payload.get("min_stock",0),
        payload.get("unit",""),
        payload.get("price",""),
        payload.get("vendor",""),
        payload.get("storage",""),
        payload.get("origin",""),
        payload.get("buy_link",""),
        payload.get("memo",""),
        now()
    ))
    c.commit()
    return {"ok":True}

@app.put("/api/stores/{store_id}/items/{category_key}/{item_id}")
def update_item(store_id:str, category_key:str, item_id:int, payload:dict):
    c = db()
    c.execute("""
    UPDATE items SET
    current_stock=?,
    min_stock=?,
    unit=?,
    price=?,
    vendor=?,
    storage=?,
    origin=?,
    buy_link=?,
    memo=?,
    updated_at=?
    WHERE id=?
    """,(
        payload.get("current_stock",0),
        payload.get("min_stock",0),
        payload.get("unit",""),
        payload.get("price",""),
        payload.get("vendor",""),
        payload.get("storage",""),
        payload.get("origin",""),
        payload.get("buy_link",""),
        payload.get("memo",""),
        now(),
        item_id
    ))
    c.commit()
    return {"ok":True,"updated_at":now()}

@app.delete("/api/stores/{store_id}/items/{category_key}/{item_id}")
def delete_item(store_id:str, category_key:str, item_id:int):
    c = db()
    c.execute("DELETE FROM items WHERE id=?", (item_id,))
    c.commit()
    return {"ok":True}

# =====================
# SHORTAGES
# =====================
@app.get("/api/shortages/{store_id}")
def shortages(store_id:str):
    c = db()
    rows = c.execute("""
    SELECT i.*, c.label as category_label
    FROM items i
    JOIN categories c
    ON i.category_key=c.key AND i.store_id=c.store_id
    WHERE i.store_id=? AND i.current_stock < i.min_stock
    """,(store_id,)).fetchall()

    out=[]
    for r in rows:
        d=dict(r)
        d["need"]=round(d["min_stock"]-d["current_stock"],2)
        out.append(d)
    return {"shortages":out}
