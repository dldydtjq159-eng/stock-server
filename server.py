# server.py
import os
import sqlite3
import time
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

SERVICE = "stock-server"
VERSION = "4.0"

# Railway Variables에서 ADMIN_TOKEN 설정 권장
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "dldydtjq159")

DATA_DIR = os.getenv("DATA_DIR", "/data")
DB_PATH = os.path.join(DATA_DIR, "stock.db")


def now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def db() -> sqlite3.Connection:
    ensure_dir()
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def require_token(x_admin_token: Optional[str]):
    if not x_admin_token or x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")


def init_db():
    c = db()
    cur = c.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS stores (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL UNIQUE,
      created_at TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS category_groups (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      store_id TEXT NOT NULL,
      group_no INTEGER NOT NULL,
      name TEXT NOT NULL,
      sort INTEGER NOT NULL,
      created_at TEXT NOT NULL,
      UNIQUE(store_id, group_no),
      FOREIGN KEY(store_id) REFERENCES stores(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS categories (
      id TEXT PRIMARY KEY,
      store_id TEXT NOT NULL,
      group_no INTEGER NOT NULL,
      name TEXT NOT NULL,
      sort INTEGER NOT NULL,
      created_at TEXT NOT NULL,
      UNIQUE(store_id, group_no, sort),
      FOREIGN KEY(store_id) REFERENCES stores(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS items (
      id TEXT PRIMARY KEY,
      store_id TEXT NOT NULL,
      category_id TEXT NOT NULL,
      name TEXT NOT NULL,
      current_qty INTEGER NOT NULL DEFAULT 0,
      min_qty INTEGER NOT NULL DEFAULT 0,
      unit TEXT NOT NULL DEFAULT '개',
      price TEXT NOT NULL DEFAULT '',
      vendor TEXT NOT NULL DEFAULT '',
      storage TEXT NOT NULL DEFAULT '',
      origin TEXT NOT NULL DEFAULT '',
      buy_url TEXT NOT NULL DEFAULT '',
      notes TEXT NOT NULL DEFAULT '',
      updated_at TEXT NOT NULL,
      created_at TEXT NOT NULL,
      FOREIGN KEY(store_id) REFERENCES stores(id),
      FOREIGN KEY(category_id) REFERENCES categories(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS usage_text (
      store_id TEXT PRIMARY KEY,
      text1 TEXT NOT NULL DEFAULT '',
      text2 TEXT NOT NULL DEFAULT '',
      updated_at TEXT NOT NULL,
      FOREIGN KEY(store_id) REFERENCES stores(id)
    )
    """)

    c.commit()

    # 기본 매장 2개 (중복 생성 방지)
    seed_default(c)

    c.close()


def seed_default(c: sqlite3.Connection):
    cur = c.cursor()
    now = now_iso()

    # stores
    stores = [
        ("store_k", "김경영 요리 연구소"),
        ("store_y", "청년회관"),
    ]
    for sid, name in stores:
        cur.execute("INSERT OR IGNORE INTO stores(id, name, created_at) VALUES(?,?,?)", (sid, name, now))

    # group names
    for sid, _ in stores:
        # group 1/2 이름
        cur.execute("""
          INSERT OR IGNORE INTO category_groups(store_id, group_no, name, sort, created_at)
          VALUES(?,?,?,?,?)
        """, (sid, 1, "카테고리 1", 1, now))
        cur.execute("""
          INSERT OR IGNORE INTO category_groups(store_id, group_no, name, sort, created_at)
          VALUES(?,?,?,?,?)
        """, (sid, 2, "카테고리 2", 2, now))

        # usage default
        cur.execute("""
          INSERT OR IGNORE INTO usage_text(store_id, text1, text2, updated_at)
          VALUES(?,?,?,?)
        """, (sid, "▶ 사용방법\n카테고리 선택 → 품목 추가 → 수량/최소수량 입력 → 저장", "", now))

        # 기본 카테고리(그룹1)
        defaults = ["닭", "소스", "용기", "조미료", "식용유", "떡", "면", "야채"]
        existing = cur.execute("""
          SELECT COUNT(*) AS cnt FROM categories WHERE store_id=? AND group_no=1
        """, (sid,)).fetchone()["cnt"]
        if existing == 0:
            for i, nm in enumerate(defaults, start=1):
                cid = f"{sid}_g1_{i:02d}"
                cur.execute("""
                  INSERT OR IGNORE INTO categories(id, store_id, group_no, name, sort, created_at)
                  VALUES(?,?,?,?,?,?)
                """, (cid, sid, 1, nm, i, now))

        # 그룹2는 비워둬도 됨(원하면 기본 추가 가능)


def make_id(prefix: str) -> str:
    return f"{prefix}_{int(time.time()*1000)}"


app = FastAPI(title=SERVICE)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()


# -------------------------
# Models
# -------------------------
class StoreOut(BaseModel):
    id: str
    name: str


class UsageOut(BaseModel):
    store_id: str
    text1: str
    text2: str
    updated_at: str


class UsageUpdate(BaseModel):
    text1: str = ""
    text2: str = ""


class CategoryOut(BaseModel):
    id: str
    store_id: str
    group_no: int
    name: str
    sort: int


class CategoryCreate(BaseModel):
    name: str


class CategoryRename(BaseModel):
    name: str


class CategoryReorder(BaseModel):
    category_ids: List[str]


class ItemOut(BaseModel):
    id: str
    store_id: str
    category_id: str
    name: str
    current_qty: int
    min_qty: int
    unit: str
    price: str
    vendor: str
    storage: str
    origin: str
    buy_url: str
    notes: str
    updated_at: str


class ItemCreate(BaseModel):
    name: str
    unit: str = "개"


class ItemUpdate(BaseModel):
    name: Optional[str] = None
    current_qty: Optional[int] = None
    min_qty: Optional[int] = None
    unit: Optional[str] = None
    price: Optional[str] = None
    vendor: Optional[str] = None
    storage: Optional[str] = None
    origin: Optional[str] = None
    buy_url: Optional[str] = None
    notes: Optional[str] = None


class ShortageRow(BaseModel):
    item_id: str
    store_id: str
    category_id: str
    category_name: str
    item_name: str
    current_qty: int
    min_qty: int
    need_qty: int
    unit: str
    buy_url: str


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
    c = db()
    rows = c.execute("SELECT id, name FROM stores ORDER BY created_at ASC").fetchall()
    c.close()
    return {"ok": True, "stores": [dict(r) for r in rows]}


@app.get("/api/usage/{store_id}")
def get_usage(store_id: str):
    c = db()
    row = c.execute("SELECT store_id, text1, text2, updated_at FROM usage_text WHERE store_id=?", (store_id,)).fetchone()
    c.close()
    if not row:
        return {"ok": True, "usage": {"store_id": store_id, "text1": "", "text2": "", "updated_at": now_iso()}}
    return {"ok": True, "usage": dict(row)}


@app.put("/api/usage/{store_id}")
def update_usage(store_id: str, body: UsageUpdate, x_admin_token: Optional[str] = Header(default=None)):
    require_token(x_admin_token)
    c = db()
    c.execute("""
      INSERT INTO usage_text(store_id, text1, text2, updated_at)
      VALUES(?,?,?,?)
      ON CONFLICT(store_id) DO UPDATE SET
        text1=excluded.text1,
        text2=excluded.text2,
        updated_at=excluded.updated_at
    """, (store_id, body.text1, body.text2, now_iso()))
    c.commit()
    c.close()
    return {"ok": True, "updated_at": now_iso()}


@app.get("/api/categories/{store_id}/{group_no}")
def list_categories(store_id: str, group_no: int):
    c = db()
    rows = c.execute("""
      SELECT id, store_id, group_no, name, sort
      FROM categories
      WHERE store_id=? AND group_no=?
      ORDER BY sort ASC
    """, (store_id, group_no)).fetchall()
    c.close()
    return {"ok": True, "categories": [dict(r) for r in rows]}


@app.post("/api/categories/{store_id}/{group_no}")
def create_category(store_id: str, group_no: int, body: CategoryCreate, x_admin_token: Optional[str] = Header(default=None)):
    require_token(x_admin_token)
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(400, "name required")

    c = db()
    # sort = max+1
    mx = c.execute("SELECT COALESCE(MAX(sort),0) AS mx FROM categories WHERE store_id=? AND group_no=?", (store_id, group_no)).fetchone()["mx"]
    cid = make_id(f"{store_id}_g{group_no}_cat")
    c.execute("""
      INSERT INTO categories(id, store_id, group_no, name, sort, created_at)
      VALUES(?,?,?,?,?,?)
    """, (cid, store_id, group_no, name, mx + 1, now_iso()))
    c.commit()
    c.close()
    return {"ok": True, "id": cid}


@app.put("/api/categories/{category_id}")
def rename_category(category_id: str, body: CategoryRename, x_admin_token: Optional[str] = Header(default=None)):
    require_token(x_admin_token)
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(400, "name required")
    c = db()
    cur = c.execute("UPDATE categories SET name=? WHERE id=?", (name, category_id))
    c.commit()
    c.close()
    if cur.rowcount == 0:
        raise HTTPException(404, "category not found")
    return {"ok": True}


@app.delete("/api/categories/{category_id}")
def delete_category(category_id: str, x_admin_token: Optional[str] = Header(default=None)):
    require_token(x_admin_token)
    c = db()

    # 카테고리 정보
    row = c.execute("SELECT store_id, group_no FROM categories WHERE id=?", (category_id,)).fetchone()
    if not row:
        c.close()
        raise HTTPException(404, "category not found")

    # 해당 카테고리의 품목도 함께 삭제
    c.execute("DELETE FROM items WHERE category_id=?", (category_id,))
    c.execute("DELETE FROM categories WHERE id=?", (category_id,))
    c.commit()

    # sort 재정렬
    store_id = row["store_id"]
    group_no = row["group_no"]
    rows = c.execute("""
      SELECT id FROM categories WHERE store_id=? AND group_no=? ORDER BY sort ASC
    """, (store_id, group_no)).fetchall()
    for i, r in enumerate(rows, start=1):
        c.execute("UPDATE categories SET sort=? WHERE id=?", (i, r["id"]))
    c.commit()

    c.close()
    return {"ok": True}


@app.post("/api/categories/{store_id}/{group_no}/reorder")
def reorder_categories(store_id: str, group_no: int, body: CategoryReorder, x_admin_token: Optional[str] = Header(default=None)):
    require_token(x_admin_token)
    ids = body.category_ids or []
    c = db()

    # 검증: 동일 store/group 범위인지
    existing = c.execute("""
      SELECT id FROM categories WHERE store_id=? AND group_no=? ORDER BY sort ASC
    """, (store_id, group_no)).fetchall()
    existing_ids = [r["id"] for r in existing]

    if set(ids) != set(existing_ids):
        raise HTTPException(400, "category_ids mismatch")

    for i, cid in enumerate(ids, start=1):
        c.execute("UPDATE categories SET sort=? WHERE id=?", (i, cid))
    c.commit()
    c.close()
    return {"ok": True}


@app.get("/api/items/{store_id}/{category_id}")
def list_items(store_id: str, category_id: str, q: str = ""):
    q = (q or "").strip()
    c = db()
    if q:
        rows = c.execute("""
          SELECT * FROM items
          WHERE store_id=? AND category_id=? AND name LIKE ?
          ORDER BY name COLLATE NOCASE ASC
        """, (store_id, category_id, f"%{q}%")).fetchall()
    else:
        rows = c.execute("""
          SELECT * FROM items
          WHERE store_id=? AND category_id=?
          ORDER BY name COLLATE NOCASE ASC
        """, (store_id, category_id)).fetchall()
    c.close()
    return {"ok": True, "items": [dict(r) for r in rows]}


@app.post("/api/items/{store_id}/{category_id}")
def create_item(store_id: str, category_id: str, body: ItemCreate):
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(400, "name required")
    unit = (body.unit or "개").strip() or "개"

    c = db()
    iid = make_id(f"{store_id}_item")
    now = now_iso()
    c.execute("""
      INSERT INTO items(id, store_id, category_id, name, current_qty, min_qty, unit,
                        price, vendor, storage, origin, buy_url, notes, updated_at, created_at)
      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (iid, store_id, category_id, name, 0, 0, unit, "", "", "", "", "", "", now, now))
    c.commit()
    c.close()
    return {"ok": True, "id": iid}


@app.put("/api/items/{item_id}")
def update_item(item_id: str, body: ItemUpdate):
    c = db()
    row = c.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
    if not row:
        c.close()
        raise HTTPException(404, "item not found")

    updates = {}
    for k, v in body.model_dump().items():
        if v is not None:
            updates[k] = v

    if not updates:
        c.close()
        return {"ok": True, "updated_at": row["updated_at"]}

    # 안전 캐스팅
    if "current_qty" in updates:
        updates["current_qty"] = int(updates["current_qty"])
    if "min_qty" in updates:
        updates["min_qty"] = int(updates["min_qty"])
    if "name" in updates and not str(updates["name"]).strip():
        raise HTTPException(400, "name empty")

    updates["updated_at"] = now_iso()

    sets = ", ".join([f"{k}=?" for k in updates.keys()])
    vals = list(updates.values()) + [item_id]
    c.execute(f"UPDATE items SET {sets} WHERE id=?", vals)
    c.commit()
    c.close()
    return {"ok": True, "updated_at": updates["updated_at"]}


@app.delete("/api/items/{item_id}")
def delete_item(item_id: str):
    c = db()
    cur = c.execute("DELETE FROM items WHERE id=?", (item_id,))
    c.commit()
    c.close()
    if cur.rowcount == 0:
        raise HTTPException(404, "item not found")
    return {"ok": True}


@app.get("/api/shortages/{store_id}")
def shortages(store_id: str):
    c = db()
    rows = c.execute("""
      SELECT i.id AS item_id, i.store_id, i.category_id, c.name AS category_name,
             i.name AS item_name, i.current_qty, i.min_qty, i.unit, i.buy_url
      FROM items i
      JOIN categories c ON c.id = i.category_id
      WHERE i.store_id = ?
        AND i.min_qty > 0
        AND i.current_qty < i.min_qty
      ORDER BY (i.min_qty - i.current_qty) DESC, c.sort ASC, i.name COLLATE NOCASE ASC
    """, (store_id,)).fetchall()
    out = []
    for r in rows:
        need = int(r["min_qty"]) - int(r["current_qty"])
        if need > 0:
            out.append({
                "item_id": r["item_id"],
                "store_id": r["store_id"],
                "category_id": r["category_id"],
                "category_name": r["category_name"],
                "item_name": r["item_name"],
                "current_qty": int(r["current_qty"]),
                "min_qty": int(r["min_qty"]),
                "need_qty": int(need),
                "unit": r["unit"],
                "buy_url": r["buy_url"],
            })
    c.close()
    return {"ok": True, "shortages": out}
