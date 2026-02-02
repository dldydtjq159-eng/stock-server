import os
import re
import sqlite3
from datetime import datetime
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

APP_VERSION = "6.0"

# ===============================
# ENV
# ===============================
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "dldydtjq159").strip()
DATA_DIR = os.getenv("DATA_DIR", "/data").strip()
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "stock.db")

# ===============================
# APP
# ===============================
app = FastAPI(title="stock-server", version=APP_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===============================
# UTILS
# ===============================
def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def require_admin(token: Optional[str]):
    if not token or token.strip() != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

def num(v) -> float:
    try:
        return float(v)
    except Exception:
        return 0.0

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

# ===============================
# INIT DB
# ===============================
def init_db():
    con = db()
    cur = con.cursor()

    # 매장
    cur.execute("""
    CREATE TABLE IF NOT EXISTS stores (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL
    )
    """)

    # 카테고리
    cur.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_id TEXT,
        key TEXT,
        label TEXT,
        sort INTEGER
    )
    """)

    # 재고 아이템
    cur.execute("""
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

    # ✅ 레시피
    cur.execute("""
    CREATE TABLE IF NOT EXISTS recipes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_id TEXT,
        menu_name TEXT,
        item_name TEXT,
        amount REAL,
        unit TEXT
    )
    """)

    # ✅ 판매 이력
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_id TEXT,
        menu_name TEXT,
        qty INTEGER,
        sold_at TEXT
    )
    """)

    # 기본 매장
    cur.execute("INSERT OR IGNORE INTO stores VALUES ('lab','김경영 요리 연구소')")
    cur.execute("INSERT OR IGNORE INTO stores VALUES ('youth','청년회관')")

    con.commit()
    con.close()

init_db()

# ===============================
# BASIC
# ===============================
@app.get("/")
def root():
    return {"ok": True, "service": "stock-server", "version": APP_VERSION}

# ===============================
# STORES
# ===============================
@app.get("/api/stores")
def stores():
    con = db()
    rows = con.execute("SELECT * FROM stores").fetchall()
    con.close()
    return {"stores": [dict(r) for r in rows]}

# ===============================
# ITEMS
# ===============================
@app.get("/api/stores/{store_id}/items/{category}")
def list_items(store_id: str, category: str):
    con = db()
    rows = con.execute(
        "SELECT * FROM items WHERE store_id=? AND category_key=?",
        (store_id, category)
    ).fetchall()
    con.close()
    return {"items": [dict(r) for r in rows]}

@app.put("/api/stores/{store_id}/items/{category}/{item_id}")
def update_item(store_id: str, category: str, item_id: int, payload: Dict[str, Any]):
    con = db()
    cur = con.cursor()
    cur.execute("""
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
    """, (
        num(payload.get("current_stock")),
        num(payload.get("min_stock")),
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
    con.commit()
    con.close()
    return {"ok": True, "updated_at": now()}

# ===============================
# RECIPES
# ===============================
@app.post("/api/recipes/{store_id}")
def add_recipe(store_id: str, payload: Dict[str, Any], x_admin_token: Optional[str] = Header(None)):
    require_admin(x_admin_token)
    con = db()
    con.execute("""
        INSERT INTO recipes(store_id, menu_name, item_name, amount, unit)
        VALUES (?,?,?,?,?)
    """, (
        store_id,
        payload["menu_name"],
        payload["item_name"],
        num(payload["amount"]),
        payload.get("unit","")
    ))
    con.commit()
    con.close()
    return {"ok": True}

@app.get("/api/recipes/{store_id}/{menu}")
def get_recipe(store_id: str, menu: str):
    con = db()
    rows = con.execute(
        "SELECT * FROM recipes WHERE store_id=? AND menu_name=?",
        (store_id, menu)
    ).fetchall()
    con.close()
    return {"recipe": [dict(r) for r in rows]}

# ===============================
# SALE + AUTO DEDUCT
# ===============================
@app.post("/api/sales/{store_id}")
def sell(store_id: str, payload: Dict[str, Any]):
    menu = payload["menu_name"]
    qty = int(payload.get("qty",1))

    con = db()
    cur = con.cursor()

    # 판매 기록
    cur.execute("""
        INSERT INTO sales(store_id, menu_name, qty, sold_at)
        VALUES (?,?,?,?)
    """, (store_id, menu, qty, now()))

    # 레시피 불러오기
    recipe = cur.execute(
        "SELECT * FROM recipes WHERE store_id=? AND menu_name=?",
        (store_id, menu)
    ).fetchall()

    if not recipe:
        con.close()
        raise HTTPException(status_code=400, detail="레시피 없음")

    # 재고 차감
    for r in recipe:
        cur.execute("""
            UPDATE items
            SET current_stock = current_stock - ?
            WHERE store_id=? AND name=?
        """, (r["amount"] * qty, store_id, r["item_name"]))

    con.commit()
    con.close()
    return {"ok": True}

# ===============================
# SHORTAGE
# ===============================
@app.get("/api/shortages/{store_id}")
def shortage(store_id: str):
    con = db()
    rows = con.execute("""
        SELECT * FROM items
        WHERE store_id=? AND current_stock < min_stock
    """, (store_id,)).fetchall()
    con.close()

    out = []
    for r in rows:
        out.append({
            "category_key": r["category_key"],
            "category_label": r["category_key"],
            "item_id": r["id"],
            "name": r["name"],
            "current_stock": r["current_stock"],
            "min_stock": r["min_stock"],
            "need": r["min_stock"] - r["current_stock"],
            "unit": r["unit"],
            "price": r["price"],
            "buy_link": r["buy_link"],
            "updated_at": r["updated_at"]
        })
    return {"shortages": out}
