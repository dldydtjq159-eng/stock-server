import os
import sqlite3
from datetime import datetime
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from typing import List, Optional

# =====================
# 기본 설정
# =====================
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "dldydtjq159")
DATA_DIR = os.environ.get("DATA_DIR", "/data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "stock.db")

app = FastAPI(title="stock-server", version="4.1")

# =====================
# DB 연결
# =====================
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# =====================
# 초기화 (🔥 핵심)
# =====================
def init_db():
    conn = db()
    cur = conn.cursor()

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
        store_id TEXT NOT NULL,
        key TEXT NOT NULL,
        label TEXT NOT NULL,
        sort INTEGER DEFAULT 0
    )
    """)

    # 품목
    cur.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_id TEXT NOT NULL,
        category TEXT NOT NULL,
        name TEXT NOT NULL,
        real_stock TEXT,
        price TEXT,
        vendor TEXT,
        storage TEXT,
        origin TEXT,
        updated_at TEXT
    )
    """)

    # 메타
    cur.execute("""
    CREATE TABLE IF NOT EXISTS store_meta (
        store_id TEXT PRIMARY KEY,
        usage_text TEXT
    )
    """)

    # 🔥 깨진 데이터 정리
    cur.execute("DELETE FROM categories WHERE store_id IS NULL")
    cur.execute("DELETE FROM items WHERE store_id IS NULL")

    # 기본 매장
    stores = [
        ("lab", "김경영 요리 연구소"),
        ("youth", "청년회관"),
    ]
    for sid, name in stores:
        cur.execute("INSERT OR IGNORE INTO stores (id, name) VALUES (?,?)", (sid, name))

    # 기본 카테고리
    default_categories = [
        ("조미료", "seasoning"),
        ("식용유", "oil"),
        ("떡", "ricecake"),
        ("면", "noodle"),
        ("야채", "veggie"),
    ]

    for sid, _ in stores:
        for i, (label, key) in enumerate(default_categories):
            cur.execute("""
            INSERT OR IGNORE INTO categories (store_id, key, label, sort)
            VALUES (?,?,?,?)
            """, (sid, key, label, i))

        cur.execute("""
        INSERT OR IGNORE INTO store_meta (store_id, usage_text)
        VALUES (?,?)
        """, (sid, "카테고리 클릭 → 품목 추가/선택 → 저장"))

    conn.commit()
    conn.close()

init_db()

# =====================
# 모델
# =====================
class ItemIn(BaseModel):
    name: str
    real_stock: Optional[str] = ""
    price: Optional[str] = ""
    vendor: Optional[str] = ""
    storage: Optional[str] = ""
    origin: Optional[str] = ""

class ItemUpdate(BaseModel):
    real_stock: str
    price: str
    vendor: str
    storage: str
    origin: str

class MetaUpdate(BaseModel):
    usage_text: str
    categories: List[dict]

# =====================
# API
# =====================
@app.get("/")
def root():
    return {"ok": True, "service": "stock-server", "version": "4.1"}

@app.get("/api/stores")
def stores():
    conn = db()
    rows = conn.execute("SELECT * FROM stores").fetchall()
    return {"stores": [dict(r) for r in rows]}

@app.get("/api/stores/{store_id}/meta")
def store_meta(store_id: str):
    conn = db()
    meta = conn.execute("SELECT * FROM store_meta WHERE store_id=?", (store_id,)).fetchone()
    cats = conn.execute(
        "SELECT key,label,sort FROM categories WHERE store_id=? ORDER BY sort",
        (store_id,)
    ).fetchall()
    return {
        "meta": {
            "usage_text": meta["usage_text"] if meta else "",
            "categories": [dict(c) for c in cats]
        }
    }

@app.put("/api/stores/{store_id}/meta")
def update_meta(store_id: str, body: MetaUpdate, x_admin_token: str = Header("")):
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(401)

    conn = db()
    conn.execute("UPDATE store_meta SET usage_text=? WHERE store_id=?",
                 (body.usage_text, store_id))

    conn.execute("DELETE FROM categories WHERE store_id=?", (store_id,))
    for c in body.categories:
        conn.execute("""
        INSERT INTO categories (store_id,key,label,sort)
        VALUES (?,?,?,?)
        """, (store_id, c["key"], c["label"], c.get("sort", 0)))

    conn.commit()
    return {"ok": True}

@app.get("/api/stores/{store_id}/items/{category}")
def items(store_id: str, category: str):
    conn = db()
    rows = conn.execute("""
    SELECT * FROM items
    WHERE store_id=? AND category=?
    ORDER BY name
    """, (store_id, category)).fetchall()
    return {"items": [dict(r) for r in rows]}

@app.post("/api/stores/{store_id}/items/{category}")
def add_item(store_id: str, category: str, item: ItemIn):
    conn = db()
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute("""
    INSERT INTO items (store_id,category,name,real_stock,price,vendor,storage,origin,updated_at)
    VALUES (?,?,?,?,?,?,?,?,?)
    """, (store_id, category, item.name,
          item.real_stock, item.price, item.vendor,
          item.storage, item.origin, now))
    conn.commit()
    return {"ok": True}

@app.put("/api/stores/{store_id}/items/{category}/{item_id}")
def update_item(store_id: str, category: str, item_id: int, body: ItemUpdate):
    conn = db()
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute("""
    UPDATE items SET
        real_stock=?, price=?, vendor=?, storage=?, origin=?, updated_at=?
    WHERE id=? AND store_id=? AND category=?
    """, (body.real_stock, body.price, body.vendor,
          body.storage, body.origin, now,
          item_id, store_id, category))
    conn.commit()
    return {"updated_at": now}

@app.delete("/api/stores/{store_id}/items/{category}/{item_id}")
def delete_item(store_id: str, category: str, item_id: int):
    conn = db()
    conn.execute("DELETE FROM items WHERE id=? AND store_id=?", (item_id, store_id))
    conn.commit()
    return {"ok": True}

from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"ok": True, "service": "stock-server", "version": "4.0"}

