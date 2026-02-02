import os
import re
import sqlite3
from datetime import datetime
from typing import Optional, Dict, Any

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# =====================
# 기본 설정
# =====================
APP_VERSION = "5.0"
SERVICE_NAME = "stock-server"

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "dldydtjq159")
DATA_DIR = os.getenv("DATA_DIR", "/data")

os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "stock.db")

# =====================
# FastAPI
# =====================
app = FastAPI(title=SERVICE_NAME, version=APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =====================
# 유틸
# =====================
def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"[^a-z0-9\-]", "", text)
    return text[:32] or "cat"

def parse_float(v):
    try:
        return float(v)
    except Exception:
        return 0.0

def require_admin(token: Optional[str]):
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid admin token")

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

# =====================
# DB 초기화
# =====================
def init_db():
    con = db()
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS stores (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_id TEXT NOT NULL,
        key TEXT NOT NULL,
        label TEXT NOT NULL,
        sort INTEGER DEFAULT 0,
        UNIQUE(store_id, key)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_id TEXT NOT NULL,
        category_key TEXT NOT NULL,
        name TEXT NOT NULL,

        current_stock REAL DEFAULT 0,
        min_stock REAL DEFAULT 0,
        unit TEXT DEFAULT "",

        price TEXT DEFAULT "",
        vendor TEXT DEFAULT "",
        storage TEXT DEFAULT "",
        origin TEXT DEFAULT "",

        buy_link TEXT DEFAULT "",
        memo TEXT DEFAULT "",

        updated_at TEXT NOT NULL,

        UNIQUE(store_id, category_key, name)
    )
    """)

    # 기본 매장 (중복 방지)
    stores = [
        ("lab", "김경영 요리 연구소"),
        ("youth", "청년회관"),
    ]

    for sid, name in stores:
        cur.execute(
            "INSERT OR IGNORE INTO stores (id, name) VALUES (?, ?)",
            (sid, name)
        )

    # 기본 카테고리
    default_categories = [
        ("ingredient", "식재료", 0),
        ("recipe", "레시피", 10),
    ]

    for sid, _ in stores:
        cnt = cur.execute(
            "SELECT COUNT(*) FROM categories WHERE store_id=?",
            (sid,)
        ).fetchone()[0]

        if cnt == 0:
            for key, label, sort in default_categories:
                cur.execute(
                    "INSERT INTO categories (store_id, key, label, sort) VALUES (?, ?, ?, ?)",
                    (sid, key, label, sort)
                )

    con.commit()
    con.close()

init_db()

# =====================
# API
# =====================
@app.get("/")
def root():
    return {
        "ok": True,
        "service": SERVICE_NAME,
        "version": APP_VERSION
    }

@app.get("/api/stores")
def get_stores():
    con = db()
    rows = con.execute("SELECT id, name FROM stores ORDER BY name").fetchall()
    con.close()
    return {"stores": [dict(r) for r in rows]}

@app.get("/api/stores/{store_id}/categories")
def get_categories(store_id: str):
    con = db()
    rows = con.execute(
        "SELECT key, label, sort FROM categories WHERE store_id=? ORDER BY sort",
        (store_id,)
    ).fetchall()
    con.close()
    return {"categories": [dict(r) for r in rows]}

@app.get("/api/stores/{store_id}/items/{category_key}")
def list_items(store_id: str, category_key: str):
    con = db()
    rows = con.execute(
        "SELECT * FROM items WHERE store_id=? AND category_key=? ORDER BY name",
        (store_id, category_key)
    ).fetchall()
    con.close()
    return {"items": [dict(r) for r in rows]}

@app.post("/api/stores/{store_id}/items/{category_key}")
def add_item(store_id: str, category_key: str, payload: Dict[str, Any]):
    name = payload.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name required")

    con = db()
    try:
        con.execute("""
        INSERT INTO items (
            store_id, category_key, name,
            current_stock, min_stock, unit,
            price, vendor, storage, origin,
            buy_link, memo, updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            store_id,
            category_key,
            name,
            parse_float(payload.get("current_stock")),
            parse_float(payload.get("min_stock")),
            payload.get("unit", ""),
            payload.get("price", ""),
            payload.get("vendor", ""),
            payload.get("storage", ""),
            payload.get("origin", ""),
            payload.get("buy_link", ""),
            payload.get("memo", ""),
            now_str()
        ))
        con.commit()
    except sqlite3.IntegrityError:
        con.close()
        raise HTTPException(status_code=409, detail="Item already exists")

    con.close()
    return {"ok": True}

@app.get("/api/shortages/{store_id}")
def shortages(store_id: str):
    con = db()
    rows = con.execute(
        "SELECT * FROM items WHERE store_id=?",
        (store_id,)
    ).fetchall()

    result = []
    for r in rows:
        need = (r["min_stock"] or 0) - (r["current_stock"] or 0)
        if need > 0:
            result.append({
                "category": r["category_key"],
                "name": r["name"],
                "current_stock": r["current_stock"],
                "min_stock": r["min_stock"],
                "need": need,
                "unit": r["unit"],
                "price": r["price"],
                "buy_link": r["buy_link"],
                "updated_at": r["updated_at"]
            })

    con.close()
    return {"shortages": result}
