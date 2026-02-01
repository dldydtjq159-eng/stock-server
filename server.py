# server.py  (FastAPI + SQLite /data/app.db)
import os
import sqlite3
import time
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

SERVICE = "stock-server"
VERSION = "4.0"

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "dldydtjq159")  # Railway Variables에 ADMIN_TOKEN으로 넣는걸 추천

DATA_DIR = os.getenv("DATA_DIR", "/data")
DB_PATH = os.path.join(DATA_DIR, "app.db")

os.makedirs(DATA_DIR, exist_ok=True)

app = FastAPI(title=SERVICE)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# DB
# -------------------------
def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def now_ts() -> int:
    return int(time.time())

def require_admin(x_admin_token: Optional[str]):
    if not x_admin_token or x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

def init_db():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS stores (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL UNIQUE,
      created_at INTEGER NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS help_text (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      store_id INTEGER NOT NULL,
      category_set INTEGER NOT NULL,
      text TEXT NOT NULL,
      updated_at INTEGER NOT NULL,
      UNIQUE(store_id, category_set),
      FOREIGN KEY(store_id) REFERENCES stores(id) ON DELETE CASCADE
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS categories (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      store_id INTEGER NOT NULL,
      category_set INTEGER NOT NULL,
      name TEXT NOT NULL,
      sort_order INTEGER NOT NULL DEFAULT 0,
      created_at INTEGER NOT NULL,
      updated_at INTEGER NOT NULL,
      UNIQUE(store_id, category_set, name),
      FOREIGN KEY(store_id) REFERENCES stores(id) ON DELETE CASCADE
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS items (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      store_id INTEGER NOT NULL,
      category_set INTEGER NOT NULL,
      category_id INTEGER NOT NULL,
      name TEXT NOT NULL,
      current_qty REAL NOT NULL DEFAULT 0,
      min_qty REAL NOT NULL DEFAULT 0,
      unit TEXT NOT NULL DEFAULT '',
      price TEXT NOT NULL DEFAULT '',
      vendor TEXT NOT NULL DEFAULT '',
      storage TEXT NOT NULL DEFAULT '',
      origin TEXT NOT NULL DEFAULT '',
      purchase_url TEXT NOT NULL DEFAULT '',
      note TEXT NOT NULL DEFAULT '',
      created_at INTEGER NOT NULL,
      updated_at INTEGER NOT NULL,
      UNIQUE(store_id, category_set, category_id, name),
      FOREIGN KEY(store_id) REFERENCES stores(id) ON DELETE CASCADE,
      FOREIGN KEY(category_id) REFERENCES categories(id) ON DELETE CASCADE
    )
    """)

    conn.commit()

    # seed stores
    cur.execute("SELECT COUNT(*) AS c FROM stores")
    if cur.fetchone()["c"] == 0:
        cur.execute("INSERT INTO stores(name, created_at) VALUES(?,?)", ("김경영 요리 연구소", now_ts()))
        cur.execute("INSERT INTO stores(name, created_at) VALUES(?,?)", ("청년회관", now_ts()))
        conn.commit()

    # seed categories for each store and set
    cur.execute("SELECT id FROM stores ORDER BY id")
    store_ids = [r["id"] for r in cur.fetchall()]
    default_cats = ["닭", "소스", "용기", "조미료", "식용유", "떡", "면", "야채"]

    for sid in store_ids:
        for cset in (1, 2):
            cur.execute("SELECT COUNT(*) AS c FROM categories WHERE store_id=? AND category_set=?", (sid, cset))
            if cur.fetchone()["c"] == 0:
                ts = now_ts()
                for i, name in enumerate(default_cats):
                    cur.execute("""
                    INSERT INTO categories(store_id, category_set, name, sort_order, created_at, updated_at)
                    VALUES(?,?,?,?,?,?)
                    """, (sid, cset, name, i, ts, ts))
                conn.commit()

            # seed help text
            cur.execute("SELECT COUNT(*) AS c FROM help_text WHERE store_id=? AND category_set=?", (sid, cset))
            if cur.fetchone()["c"] == 0:
                cur.execute("""
                INSERT INTO help_text(store_id, category_set, text, updated_at)
                VALUES(?,?,?,?)
                """, (
                    sid, cset,
                    "▶ 사용방법\n- 왼쪽 카테고리를 선택하세요.\n- 품목을 추가하고 현재고/최소수량을 입력 후 저장하면 자동 동기화됩니다.\n- 부족목록에서 발주서를 만들 수 있어요.",
                    now_ts()
                ))
                conn.commit()

    conn.close()

init_db()

# -------------------------
# Models
# -------------------------
class StoreOut(BaseModel):
    id: int
    name: str

class CategoryOut(BaseModel):
    id: int
    name: str
    sort_order: int

class CategoryCreate(BaseModel):
    name: str

class CategoryUpdate(BaseModel):
    name: str

class CategoryReorder(BaseModel):
    ordered_ids: List[int]

class HelpUpdate(BaseModel):
    text: str

class ItemOut(BaseModel):
    id: int
    name: str
    current_qty: float
    min_qty: float
    unit: str
    price: str
    vendor: str
    storage: str
    origin: str
    purchase_url: str
    note: str
    updated_at: int

class ItemCreate(BaseModel):
    name: str

class ItemUpdate(BaseModel):
    current_qty: float
    min_qty: float
    unit: str = ""
    price: str = ""
    vendor: str = ""
    storage: str = ""
    origin: str = ""
    purchase_url: str = ""
    note: str = ""

# -------------------------
# Routes
# -------------------------
@app.get("/")
def root():
    return {"ok": True, "service": SERVICE, "version": VERSION}

@app.get("/health")
def health():
    return {"ok": True, "service": SERVICE, "version": VERSION}

@app.get("/api/stores")
def list_stores():
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM stores ORDER BY id")
    rows = cur.fetchall()
    conn.close()
    return {"ok": True, "stores": [dict(r) for r in rows]}

def _get_store(conn, store_id: int):
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM stores WHERE id=?", (store_id,))
    r = cur.fetchone()
    if not r:
        raise HTTPException(status_code=404, detail="Store not found")
    return r

def _category_set_ok(category_set: int):
    if category_set not in (1, 2):
        raise HTTPException(status_code=400, detail="category_set must be 1 or 2")

@app.get("/api/help")
def get_help(store_id: int, category_set: int = 1):
    _category_set_ok(category_set)
    conn = db()
    _get_store(conn, store_id)
    cur = conn.cursor()
    cur.execute("SELECT text, updated_at FROM help_text WHERE store_id=? AND category_set=?", (store_id, category_set))
    r = cur.fetchone()
    conn.close()
    if not r:
        return {"ok": True, "text": "", "updated_at": 0}
    return {"ok": True, "text": r["text"], "updated_at": r["updated_at"]}

@app.put("/api/help")
def update_help(store_id: int, category_set: int, payload: HelpUpdate, x_admin_token: Optional[str] = Header(default=None)):
    require_admin(x_admin_token)
    _category_set_ok(category_set)
    conn = db()
    _get_store(conn, store_id)
    cur = conn.cursor()
    ts = now_ts()
    cur.execute("""
    INSERT INTO help_text(store_id, category_set, text, updated_at)
    VALUES(?,?,?,?)
    ON CONFLICT(store_id, category_set) DO UPDATE SET text=excluded.text, updated_at=excluded.updated_at
    """, (store_id, category_set, payload.text, ts))
    conn.commit()
    conn.close()
    return {"ok": True, "updated_at": ts}

@app.get("/api/categories")
def list_categories(store_id: int, category_set: int = 1):
    _category_set_ok(category_set)
    conn = db()
    _get_store(conn, store_id)
    cur = conn.cursor()
    cur.execute("""
    SELECT id, name, sort_order
    FROM categories
    WHERE store_id=? AND category_set=?
    ORDER BY sort_order ASC, id ASC
    """, (store_id, category_set))
    rows = cur.fetchall()
    conn.close()
    return {"ok": True, "categories": [dict(r) for r in rows]}

@app.post("/api/categories")
def create_category(store_id: int, category_set: int, payload: CategoryCreate, x_admin_token: Optional[str] = Header(default=None)):
    require_admin(x_admin_token)
    _category_set_ok(category_set)
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name required")

    conn = db()
    _get_store(conn, store_id)
    cur = conn.cursor()
    cur.execute("SELECT COALESCE(MAX(sort_order), -1) AS m FROM categories WHERE store_id=? AND category_set=?", (store_id, category_set))
    m = cur.fetchone()["m"]
    ts = now_ts()
    try:
        cur.execute("""
        INSERT INTO categories(store_id, category_set, name, sort_order, created_at, updated_at)
        VALUES(?,?,?,?,?,?)
        """, (store_id, category_set, name, int(m) + 1, ts, ts))
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=409, detail="Category name already exists")

    conn.commit()
    cid = cur.lastrowid
    conn.close()
    return {"ok": True, "id": cid, "updated_at": ts}

@app.put("/api/categories/{category_id}")
def rename_category(store_id: int, category_set: int, category_id: int, payload: CategoryUpdate, x_admin_token: Optional[str] = Header(default=None)):
    require_admin(x_admin_token)
    _category_set_ok(category_set)
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name required")

    conn = db()
    _get_store(conn, store_id)
    cur = conn.cursor()
    ts = now_ts()
    try:
        cur.execute("""
        UPDATE categories SET name=?, updated_at=?
        WHERE id=? AND store_id=? AND category_set=?
        """, (name, ts, category_id, store_id, category_set))
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=409, detail="Category name already exists")

    if cur.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Category not found")

    conn.commit()
    conn.close()
    return {"ok": True, "updated_at": ts}

@app.post("/api/categories/reorder")
def reorder_categories(store_id: int, category_set: int, payload: CategoryReorder, x_admin_token: Optional[str] = Header(default=None)):
    require_admin(x_admin_token)
    _category_set_ok(category_set)
    ordered_ids = payload.ordered_ids or []
    if not ordered_ids:
        raise HTTPException(status_code=400, detail="ordered_ids required")

    conn = db()
    _get_store(conn, store_id)
    cur = conn.cursor()

    # validate all belong to store/set
    cur.execute("SELECT id FROM categories WHERE store_id=? AND category_set=?", (store_id, category_set))
    existing = {r["id"] for r in cur.fetchall()}
    if set(ordered_ids) != existing:
        conn.close()
        raise HTTPException(status_code=400, detail="ordered_ids must include all category ids exactly once")

    ts = now_ts()
    for i, cid in enumerate(ordered_ids):
        cur.execute("UPDATE categories SET sort_order=?, updated_at=? WHERE id=? AND store_id=? AND category_set=?",
                    (i, ts, cid, store_id, category_set))
    conn.commit()
    conn.close()
    return {"ok": True, "updated_at": ts}

@app.delete("/api/categories/{category_id}")
def delete_category(store_id: int, category_set: int, category_id: int, x_admin_token: Optional[str] = Header(default=None)):
    require_admin(x_admin_token)
    _category_set_ok(category_set)
    conn = db()
    _get_store(conn, store_id)
    cur = conn.cursor()

    # deleting category also deletes items via FK
    cur.execute("DELETE FROM categories WHERE id=? AND store_id=? AND category_set=?", (category_id, store_id, category_set))
    if cur.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Category not found")
    conn.commit()

    # normalize order
    cur.execute("""
    SELECT id FROM categories WHERE store_id=? AND category_set=? ORDER BY sort_order ASC, id ASC
    """, (store_id, category_set))
    ids = [r["id"] for r in cur.fetchall()]
    ts = now_ts()
    for i, cid in enumerate(ids):
        cur.execute("UPDATE categories SET sort_order=?, updated_at=? WHERE id=?", (i, ts, cid))
    conn.commit()
    conn.close()
    return {"ok": True}

@app.get("/api/items")
def list_items(store_id: int, category_set: int, category_id: int):
    _category_set_ok(category_set)
    conn = db()
    _get_store(conn, store_id)
    cur = conn.cursor()
    cur.execute("""
    SELECT id, name, current_qty, min_qty, unit, price, vendor, storage, origin, purchase_url, note, updated_at
    FROM items
    WHERE store_id=? AND category_set=? AND category_id=?
    ORDER BY name ASC
    """, (store_id, category_set, category_id))
    rows = cur.fetchall()
    conn.close()
    return {"ok": True, "items": [dict(r) for r in rows]}

@app.post("/api/items")
def create_item(store_id: int, category_set: int, category_id: int, payload: ItemCreate):
    _category_set_ok(category_set)
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name required")

    conn = db()
    _get_store(conn, store_id)
    cur = conn.cursor()

    # ensure category exists
    cur.execute("SELECT id FROM categories WHERE id=? AND store_id=? AND category_set=?", (category_id, store_id, category_set))
    if not cur.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Category not found")

    ts = now_ts()
    try:
        cur.execute("""
        INSERT INTO items(store_id, category_set, category_id, name, current_qty, min_qty, unit, price, vendor, storage, origin, purchase_url, note, created_at, updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (store_id, category_set, category_id, name, 0, 0, "", "", "", "", "", "", "", ts, ts))
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=409, detail="Item name already exists in this category")

    conn.commit()
    iid = cur.lastrowid
    conn.close()
    return {"ok": True, "id": iid, "updated_at": ts}

@app.put("/api/items/{item_id}")
def update_item(store_id: int, category_set: int, category_id: int, item_id: int, payload: ItemUpdate):
    _category_set_ok(category_set)
    conn = db()
    _get_store(conn, store_id)
    cur = conn.cursor()

    ts = now_ts()
    cur.execute("""
    UPDATE items
    SET current_qty=?, min_qty=?, unit=?, price=?, vendor=?, storage=?, origin=?, purchase_url=?, note=?, updated_at=?
    WHERE id=? AND store_id=? AND category_set=? AND category_id=?
    """, (
        float(payload.current_qty), float(payload.min_qty),
        payload.unit or "", payload.price or "", payload.vendor or "",
        payload.storage or "", payload.origin or "", payload.purchase_url or "",
        payload.note or "", ts,
        item_id, store_id, category_set, category_id
    ))
    if cur.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Item not found")

    conn.commit()
    conn.close()
    return {"ok": True, "updated_at": ts}

@app.delete("/api/items/{item_id}")
def delete_item(store_id: int, category_set: int, category_id: int, item_id: int):
    _category_set_ok(category_set)
    conn = db()
    _get_store(conn, store_id)
    cur = conn.cursor()
    cur.execute("""
    DELETE FROM items WHERE id=? AND store_id=? AND category_set=? AND category_id=?
    """, (item_id, store_id, category_set, category_id))
    if cur.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Item not found")
    conn.commit()
    conn.close()
    return {"ok": True}

@app.get("/api/shortages")
def shortages(store_id: int, category_set: int = 1):
    _category_set_ok(category_set)
    conn = db()
    _get_store(conn, store_id)
    cur = conn.cursor()
    cur.execute("""
    SELECT i.id, i.name, i.current_qty, i.min_qty, i.unit, i.purchase_url,
           i.category_id, c.name as category_name
    FROM items i
    JOIN categories c ON c.id=i.category_id
    WHERE i.store_id=? AND i.category_set=?
      AND i.min_qty > i.current_qty
    ORDER BY c.sort_order ASC, c.name ASC, i.name ASC
    """, (store_id, category_set))
    rows = cur.fetchall()
    conn.close()

    out = []
    for r in rows:
        need = float(r["min_qty"]) - float(r["current_qty"])
        out.append({
            "id": r["id"],
            "name": r["name"],
            "category_id": r["category_id"],
            "category_name": r["category_name"],
            "current_qty": float(r["current_qty"]),
            "min_qty": float(r["min_qty"]),
            "need_qty": need,
            "unit": r["unit"],
            "purchase_url": r["purchase_url"],
        })
    return {"ok": True, "shortages": out}
