# server.py  (stock-server v4.0)
import os
import sqlite3
from datetime import datetime
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

SERVICE = "stock-server"
VERSION = "4.0"

DB_PATH = os.getenv("DB_PATH", "/data/stock.db")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "dldydtjq159")

app = FastAPI(title=SERVICE)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# DB helpers
# -------------------------
def now_iso():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def con():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON;")
    return c

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    with con() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS stores (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS store_usage (
            store_id TEXT PRIMARY KEY,
            usage_text TEXT NOT NULL DEFAULT '',
            FOREIGN KEY(store_id) REFERENCES stores(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            store_id TEXT NOT NULL,
            key TEXT NOT NULL,
            label TEXT NOT NULL,
            sort INTEGER NOT NULL DEFAULT 0,
            UNIQUE(store_id, key),
            FOREIGN KEY(store_id) REFERENCES stores(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            store_id TEXT NOT NULL,
            category_key TEXT NOT NULL,
            name TEXT NOT NULL,

            current_qty REAL NOT NULL DEFAULT 0,
            min_qty REAL NOT NULL DEFAULT 0,
            unit TEXT NOT NULL DEFAULT '',

            price TEXT NOT NULL DEFAULT '',
            vendor TEXT NOT NULL DEFAULT '',
            storage TEXT NOT NULL DEFAULT '',
            origin TEXT NOT NULL DEFAULT '',
            buy_link TEXT NOT NULL DEFAULT '',
            memo TEXT NOT NULL DEFAULT '',

            updated_at TEXT NOT NULL DEFAULT '',
            UNIQUE(store_id, category_key, name),
            FOREIGN KEY(store_id) REFERENCES stores(id) ON DELETE CASCADE
        );
        """)

        # 기본 매장 2개 자동 생성
        db.execute("INSERT OR IGNORE INTO stores(id,name) VALUES(?,?)", ("lab", "김경영 요리 연구소"))
        db.execute("INSERT OR IGNORE INTO stores(id,name) VALUES(?,?)", ("youth", "청년회관"))
        db.execute("INSERT OR IGNORE INTO store_usage(store_id, usage_text) VALUES(?,?)", ("lab", "카테고리 클릭 → 품목 추가/선택 → 저장"))
        db.execute("INSERT OR IGNORE INTO store_usage(store_id, usage_text) VALUES(?,?)", ("youth", "카테고리 클릭 → 품목 추가/선택 → 저장"))

        # 기본 카테고리 자동 생성(없을 때만)
        for sid in ("lab", "youth"):
            existing = db.execute("SELECT COUNT(*) AS c FROM categories WHERE store_id=?", (sid,)).fetchone()["c"]
            if existing == 0:
                base = [
                    ("chicken", "닭", 0),
                    ("sauce", "소스", 1),
                    ("container", "용기", 2),
                    ("seasoning", "조미료", 3),
                    ("oil", "식용유", 4),
                    ("ricecake", "떡", 5),
                    ("noodle", "면", 6),
                    ("veggie", "야채", 7),
                ]
                for k, lbl, s in base:
                    db.execute(
                        "INSERT INTO categories(store_id,key,label,sort) VALUES(?,?,?,?)",
                        (sid, k, lbl, s)
                    )

def require_admin(x_admin_token: Optional[str]):
    if not x_admin_token or x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

@app.on_event("startup")
def _startup():
    init_db()

# -------------------------
# Models
# -------------------------
class CategoryIn(BaseModel):
    key: str = Field(..., min_length=1, max_length=40)
    label: str = Field(..., min_length=1, max_length=40)
    sort: int = 0

class CategoryUpdate(BaseModel):
    label: Optional[str] = None
    sort: Optional[int] = None

class ItemIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)

    current_qty: float = 0
    min_qty: float = 0
    unit: str = ""

    price: str = ""
    vendor: str = ""
    storage: str = ""
    origin: str = ""
    buy_link: str = ""
    memo: str = ""

class ItemUpdate(BaseModel):
    current_qty: Optional[float] = None
    min_qty: Optional[float] = None
    unit: Optional[str] = None

    price: Optional[str] = None
    vendor: Optional[str] = None
    storage: Optional[str] = None
    origin: Optional[str] = None
    buy_link: Optional[str] = None
    memo: Optional[str] = None

class UsageUpdate(BaseModel):
    usage_text: str

# -------------------------
# Health
# -------------------------
@app.get("/")
def root():
    return {"ok": True, "service": SERVICE, "version": VERSION}

@app.get("/health")
def health():
    return {"ok": True}

# -------------------------
# Stores
# -------------------------
@app.get("/api/stores")
def list_stores():
    with con() as db:
        rows = db.execute("SELECT id,name FROM stores ORDER BY name").fetchall()
    return [{"id": r["id"], "name": r["name"]} for r in rows]

# -------------------------
# Store usage text
# -------------------------
@app.get("/api/store_usage/{store_id}")
def get_usage(store_id: str):
    with con() as db:
        row = db.execute("SELECT usage_text FROM store_usage WHERE store_id=?", (store_id,)).fetchone()
        if not row:
            raise HTTPException(404, "store not found")
    return {"store_id": store_id, "usage_text": row["usage_text"]}

@app.put("/api/store_usage/{store_id}")
def put_usage(store_id: str, body: UsageUpdate, x_admin_token: Optional[str] = Header(default=None)):
    require_admin(x_admin_token)
    with con() as db:
        ok = db.execute("SELECT 1 FROM stores WHERE id=?", (store_id,)).fetchone()
        if not ok:
            raise HTTPException(404, "store not found")
        db.execute("INSERT OR REPLACE INTO store_usage(store_id, usage_text) VALUES(?,?)", (store_id, body.usage_text))
    return {"ok": True, "updated_at": now_iso()}

# -------------------------
# Categories
# -------------------------
@app.get("/api/categories/{store_id}")
def list_categories(store_id: str):
    with con() as db:
        rows = db.execute(
            "SELECT key,label,sort FROM categories WHERE store_id=? ORDER BY sort,label",
            (store_id,)
        ).fetchall()
    return {"store_id": store_id, "categories": [{"key": r["key"], "label": r["label"], "sort": r["sort"]} for r in rows]}

@app.post("/api/categories/{store_id}")
def add_category(store_id: str, body: CategoryIn, x_admin_token: Optional[str] = Header(default=None)):
    require_admin(x_admin_token)
    with con() as db:
        try:
            db.execute(
                "INSERT INTO categories(store_id,key,label,sort) VALUES(?,?,?,?)",
                (store_id, body.key, body.label, body.sort)
            )
        except sqlite3.IntegrityError:
            raise HTTPException(409, "category key already exists")
    return {"ok": True}

@app.put("/api/categories/{store_id}/{key}")
def update_category(store_id: str, key: str, body: CategoryUpdate, x_admin_token: Optional[str] = Header(default=None)):
    require_admin(x_admin_token)
    with con() as db:
        row = db.execute("SELECT 1 FROM categories WHERE store_id=? AND key=?", (store_id, key)).fetchone()
        if not row:
            raise HTTPException(404, "category not found")

        if body.label is not None:
            db.execute("UPDATE categories SET label=? WHERE store_id=? AND key=?", (body.label, store_id, key))
        if body.sort is not None:
            db.execute("UPDATE categories SET sort=? WHERE store_id=? AND key=?", (int(body.sort), store_id, key))
    return {"ok": True}

@app.delete("/api/categories/{store_id}/{key}")
def delete_category(store_id: str, key: str, x_admin_token: Optional[str] = Header(default=None)):
    require_admin(x_admin_token)
    with con() as db:
        # 카테고리 삭제 시, 해당 카테고리 품목도 실제 삭제
        db.execute("DELETE FROM items WHERE store_id=? AND category_key=?", (store_id, key))
        cur = db.execute("DELETE FROM categories WHERE store_id=? AND key=?", (store_id, key))
        if cur.rowcount == 0:
            raise HTTPException(404, "category not found")
    return {"ok": True}

# -------------------------
# Items
# -------------------------
@app.get("/api/items/{store_id}/{category_key}")
def list_items(store_id: str, category_key: str):
    with con() as db:
        rows = db.execute(
            """
            SELECT * FROM items
            WHERE store_id=? AND category_key=?
            ORDER BY name
            """,
            (store_id, category_key)
        ).fetchall()

    items = []
    for r in rows:
        items.append({k: r[k] for k in r.keys()})
    return {"store_id": store_id, "category_key": category_key, "items": items}

@app.post("/api/items/{store_id}/{category_key}")
def add_item(store_id: str, category_key: str, body: ItemIn):
    with con() as db:
        try:
            db.execute(
                """
                INSERT INTO items(
                    store_id, category_key, name,
                    current_qty, min_qty, unit,
                    price, vendor, storage, origin, buy_link, memo,
                    updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    store_id, category_key, body.name,
                    float(body.current_qty), float(body.min_qty), body.unit or "",
                    body.price or "", body.vendor or "", body.storage or "", body.origin or "",
                    body.buy_link or "", body.memo or "",
                    now_iso()
                )
            )
        except sqlite3.IntegrityError:
            raise HTTPException(409, "item already exists")
    return {"ok": True, "updated_at": now_iso()}

@app.put("/api/items/{store_id}/{category_key}/{item_id}")
def update_item(store_id: str, category_key: str, item_id: int, body: ItemUpdate):
    with con() as db:
        row = db.execute(
            "SELECT * FROM items WHERE id=? AND store_id=? AND category_key=?",
            (item_id, store_id, category_key)
        ).fetchone()
        if not row:
            raise HTTPException(404, "item not found")

        data = dict(row)
        for k, v in body.model_dump().items():
            if v is not None:
                data[k] = v

        db.execute(
            """
            UPDATE items SET
                current_qty=?,
                min_qty=?,
                unit=?,
                price=?,
                vendor=?,
                storage=?,
                origin=?,
                buy_link=?,
                memo=?,
                updated_at=?
            WHERE id=? AND store_id=? AND category_key=?
            """,
            (
                float(data["current_qty"]),
                float(data["min_qty"]),
                data["unit"] or "",
                data["price"] or "",
                data["vendor"] or "",
                data["storage"] or "",
                data["origin"] or "",
                data["buy_link"] or "",
                data["memo"] or "",
                now_iso(),
                item_id, store_id, category_key
            )
        )
    return {"ok": True, "updated_at": now_iso()}

@app.delete("/api/items/{store_id}/{category_key}/{item_id}")
def delete_item(store_id: str, category_key: str, item_id: int):
    with con() as db:
        cur = db.execute(
            "DELETE FROM items WHERE id=? AND store_id=? AND category_key=?",
            (item_id, store_id, category_key)
        )
        if cur.rowcount == 0:
            raise HTTPException(404, "item not found")
    return {"ok": True}

# -------------------------
# Shortages
# -------------------------
@app.get("/api/shortages/{store_id}")
def shortages(store_id: str):
    with con() as db:
        rows = db.execute(
            """
            SELECT
                i.id, i.category_key, i.name,
                i.current_qty, i.min_qty, i.unit, i.price, i.buy_link,
                c.label AS category_label
            FROM items i
            LEFT JOIN categories c
                ON c.store_id=i.store_id AND c.key=i.category_key
            WHERE i.store_id=? AND i.min_qty > i.current_qty
            ORDER BY c.sort, c.label, i.name
            """,
            (store_id,)
        ).fetchall()

    out = []
    for r in rows:
        need = float(r["min_qty"]) - float(r["current_qty"])
        out.append({
            "item_id": r["id"],
            "category_key": r["category_key"],
            "category": r["category_label"] or r["category_key"],
            "name": r["name"],
            "current_qty": r["current_qty"],
            "min_qty": r["min_qty"],
            "need": need,
            "unit": r["unit"],
            "price": r["price"],
            "buy_link": r["buy_link"],
        })
    return {"store_id": store_id, "count": len(out), "shortages": out}
