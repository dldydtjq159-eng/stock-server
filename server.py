import os
import sqlite3
from datetime import datetime
from typing import Optional, Dict

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

SERVICE = "stock-server"
VERSION = "4.1"

# Railway Variables 에서 ADMIN_TOKEN 설정 권장
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "dldydtjq159")

# Railway Volume Mount path를 /data 로 설정해야 영구 저장
DATA_DIR = os.getenv("DATA_DIR", "/data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "stock.db")

DEFAULT_STORES = [
    {"id": "lab", "name": "김경영 요리 연구소"},
    {"id": "hall", "name": "청년회관"},
]

DEFAULT_CATEGORIES = [
    {"label": "닭", "key": "chicken"},
    {"label": "소스", "key": "sauce"},
    {"label": "용기", "key": "container"},
    {"label": "조미료", "key": "seasoning"},
    {"label": "식용유", "key": "oil"},
    {"label": "떡", "key": "ricecake"},
    {"label": "면", "key": "noodle"},
    {"label": "야채", "key": "veggie"},
]

DEFAULT_HELP_TEXT = (
    "▶ 사용방법\n"
    "1) 매장 선택\n"
    "2) 카테고리 선택\n"
    "3) 품목 추가/선택\n"
    "4) 실재고/가격/구매처/보관방법/원산지 입력 후 저장\n"
)

app = FastAPI(title=SERVICE)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def now_iso():
    return datetime.utcnow().isoformat() + "Z"

def require_admin(x_admin_token: Optional[str]):
    if not x_admin_token or x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

def get_db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = get_db()
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS stores(
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS categories(
        store_id TEXT NOT NULL,
        key TEXT NOT NULL,
        label TEXT NOT NULL,
        sort INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY(store_id, key)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS helptext(
        store_id TEXT PRIMARY KEY,
        text TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS items(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_id TEXT NOT NULL,
        category_key TEXT NOT NULL,
        name TEXT NOT NULL,
        real_stock TEXT DEFAULT "",
        price TEXT DEFAULT "",
        vendor TEXT DEFAULT "",
        storage TEXT DEFAULT "",
        origin TEXT DEFAULT "",
        updated_at TEXT DEFAULT ""
    )
    """)

    # seed stores
    cur.execute("SELECT COUNT(*) AS c FROM stores")
    if cur.fetchone()["c"] == 0:
        for s in DEFAULT_STORES:
            cur.execute("INSERT INTO stores(id,name) VALUES(?,?)", (s["id"], s["name"]))

    # seed categories/help per store
    cur.execute("SELECT id FROM stores")
    store_ids = [r["id"] for r in cur.fetchall()]
    for sid in store_ids:
        cur.execute("SELECT COUNT(*) AS c FROM categories WHERE store_id=?", (sid,))
        if cur.fetchone()["c"] == 0:
            for i, cat in enumerate(DEFAULT_CATEGORIES):
                cur.execute(
                    "INSERT INTO categories(store_id,key,label,sort) VALUES(?,?,?,?)",
                    (sid, cat["key"], cat["label"], i)
                )
        cur.execute("SELECT COUNT(*) AS c FROM helptext WHERE store_id=?", (sid,))
        if cur.fetchone()["c"] == 0:
            cur.execute("INSERT INTO helptext(store_id,text) VALUES(?,?)", (sid, DEFAULT_HELP_TEXT))

    con.commit()
    con.close()

init_db()

@app.get("/")
def root():
    return {"ok": True, "service": SERVICE, "version": VERSION}

@app.get("/health")
def health():
    return {"ok": True, "service": SERVICE, "version": VERSION}

# -------------------------
# stores / meta
# -------------------------
@app.get("/api/stores")
def list_stores():
    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT id,name FROM stores ORDER BY id")
    rows = [dict(r) for r in cur.fetchall()]
    con.close()
    return {"ok": True, "stores": rows}

@app.get("/api/stores/{store_id}/meta")
def store_meta(store_id: str):
    con = get_db()
    cur = con.cursor()

    cur.execute("SELECT id,name FROM stores WHERE id=?", (store_id,))
    s = cur.fetchone()
    if not s:
        con.close()
        raise HTTPException(status_code=404, detail="Store not found")

    cur.execute("SELECT key,label,sort FROM categories WHERE store_id=? ORDER BY sort", (store_id,))
    cats = [{"key": r["key"], "label": r["label"]} for r in cur.fetchall()]

    cur.execute("SELECT text FROM helptext WHERE store_id=?", (store_id,))
    ht = cur.fetchone()
    help_text = ht["text"] if ht else DEFAULT_HELP_TEXT

    con.close()
    return {
        "ok": True,
        "store": {"id": s["id"], "name": s["name"]},
        "categories": cats,
        "help_text": help_text
    }

# -------------------------
# admin: categories/helptext
# -------------------------
@app.put("/api/admin/stores/{store_id}/categories")
def admin_save_categories(store_id: str, payload: Dict, x_admin_token: Optional[str] = Header(default=None)):
    require_admin(x_admin_token)

    categories = payload.get("categories")
    if not isinstance(categories, list) or len(categories) == 0:
        raise HTTPException(status_code=400, detail="categories required")

    cleaned = []
    seen = set()
    for i, c in enumerate(categories):
        key = (c.get("key") or "").strip()
        label = (c.get("label") or "").strip()
        if not key or not label:
            raise HTTPException(status_code=400, detail="category key/label required")
        if key in seen:
            raise HTTPException(status_code=400, detail=f"duplicate key: {key}")
        seen.add(key)
        cleaned.append((store_id, key, label, i))

    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT id FROM stores WHERE id=?", (store_id,))
    if not cur.fetchone():
        con.close()
        raise HTTPException(status_code=404, detail="Store not found")

    cur.execute("DELETE FROM categories WHERE store_id=?", (store_id,))
    cur.executemany("INSERT INTO categories(store_id,key,label,sort) VALUES(?,?,?,?)", cleaned)

    con.commit()
    con.close()
    return {"ok": True, "updated_at": now_iso()}

@app.put("/api/admin/stores/{store_id}/helptext")
def admin_save_helptext(store_id: str, payload: Dict, x_admin_token: Optional[str] = Header(default=None)):
    require_admin(x_admin_token)
    text = payload.get("text")
    if not isinstance(text, str):
        raise HTTPException(status_code=400, detail="text required")

    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT id FROM stores WHERE id=?", (store_id,))
    if not cur.fetchone():
        con.close()
        raise HTTPException(status_code=404, detail="Store not found")

    cur.execute("""
        INSERT INTO helptext(store_id,text) VALUES(?,?)
        ON CONFLICT(store_id) DO UPDATE SET text=excluded.text
    """, (store_id, text))

    con.commit()
    con.close()
    return {"ok": True, "updated_at": now_iso()}

# -------------------------
# items (public)
# -------------------------
@app.get("/api/items/{store_id}/{category_key}")
def list_items(store_id: str, category_key: str):
    con = get_db()
    cur = con.cursor()
    cur.execute("""
        SELECT id, name, real_stock, price, vendor, storage, origin, updated_at
        FROM items
        WHERE store_id=? AND category_key=?
        ORDER BY name COLLATE NOCASE
    """, (store_id, category_key))
    items = [dict(r) for r in cur.fetchall()]
    con.close()
    return {"ok": True, "store_id": store_id, "category": category_key, "items": items}

@app.post("/api/items/{store_id}/{category_key}")
def add_item(store_id: str, category_key: str, payload: Dict):
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name required")

    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT id FROM items WHERE store_id=? AND category_key=? AND name=?", (store_id, category_key, name))
    if cur.fetchone():
        con.close()
        raise HTTPException(status_code=409, detail="duplicate")

    cur.execute("""
        INSERT INTO items(store_id, category_key, name, real_stock, price, vendor, storage, origin, updated_at)
        VALUES(?,?,?,?,?,?,?,?,?)
    """, (
        store_id, category_key, name,
        payload.get("real_stock", "") or "",
        payload.get("price", "") or "",
        payload.get("vendor", "") or "",
        payload.get("storage", "") or "",
        payload.get("origin", "") or "",
        now_iso()
    ))
    con.commit()
    item_id = cur.lastrowid
    con.close()
    return {"ok": True, "id": item_id, "updated_at": now_iso()}

@app.put("/api/items/{store_id}/{category_key}/{item_id}")
def update_item(store_id: str, category_key: str, item_id: int, payload: Dict):
    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT id FROM items WHERE id=? AND store_id=? AND category_key=?", (item_id, store_id, category_key))
    if not cur.fetchone():
        con.close()
        raise HTTPException(status_code=404, detail="Not found")

    cur.execute("""
        UPDATE items
        SET real_stock=?, price=?, vendor=?, storage=?, origin=?, updated_at=?
        WHERE id=? AND store_id=? AND category_key=?
    """, (
        (payload.get("real_stock") or ""),
        (payload.get("price") or ""),
        (payload.get("vendor") or ""),
        (payload.get("storage") or ""),
        (payload.get("origin") or ""),
        now_iso(),
        item_id, store_id, category_key
    ))
    con.commit()
    con.close()
    return {"ok": True, "updated_at": now_iso()}

@app.delete("/api/items/{store_id}/{category_key}/{item_id}")
def delete_item(store_id: str, category_key: str, item_id: int):
    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT id FROM items WHERE id=? AND store_id=? AND category_key=?", (item_id, store_id, category_key))
    if not cur.fetchone():
        con.close()
        raise HTTPException(status_code=404, detail="Not found")

    cur.execute("DELETE FROM items WHERE id=? AND store_id=? AND category_key=?", (item_id, store_id, category_key))
    con.commit()
    con.close()
    return {"ok": True}
