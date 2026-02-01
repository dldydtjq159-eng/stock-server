# server.py
import os
import sqlite3
import time
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


SERVICE = "stock-server"
VERSION = "4.0"

DATA_DIR = os.getenv("DATA_DIR", "/data")
DB_PATH = os.getenv("DB_PATH", os.path.join(DATA_DIR, "stock.db"))

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "dldydtjq159")  # Railway Variables에서 설정 권장

app = FastAPI(title=SERVICE)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------
# DB
# --------------------------
def _conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    return con


def init_db():
    con = _conn()
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS stores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_id INTEGER NOT NULL,
        category_set TEXT NOT NULL,  -- 'ingredients' | 'recipes'
        name TEXT NOT NULL,
        position INTEGER NOT NULL,
        UNIQUE(store_id, category_set, name),
        FOREIGN KEY(store_id) REFERENCES stores(id) ON DELETE CASCADE
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_id INTEGER NOT NULL,
        category_set TEXT NOT NULL,
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
        updated_at INTEGER NOT NULL DEFAULT 0,
        UNIQUE(store_id, category_set, category_id, name),
        FOREIGN KEY(store_id) REFERENCES stores(id) ON DELETE CASCADE,
        FOREIGN KEY(category_id) REFERENCES categories(id) ON DELETE CASCADE
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS ui_texts (
        store_id INTEGER NOT NULL,
        category_set TEXT NOT NULL,
        usage_text TEXT NOT NULL DEFAULT '',
        updated_at INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY(store_id, category_set),
        FOREIGN KEY(store_id) REFERENCES stores(id) ON DELETE CASCADE
    );
    """)

    con.commit()

    # Seed stores if empty
    r = cur.execute("SELECT COUNT(*) AS c FROM stores").fetchone()["c"]
    if r == 0:
        cur.execute("INSERT INTO stores(name) VALUES (?)", ("김경영 요리 연구소",))
        cur.execute("INSERT INTO stores(name) VALUES (?)", ("청년회관",))
        con.commit()

    # Seed default categories if none (for each store & set)
    stores = cur.execute("SELECT id FROM stores").fetchall()
    for s in stores:
        for cat_set in ("ingredients", "recipes"):
            ccount = cur.execute(
                "SELECT COUNT(*) AS c FROM categories WHERE store_id=? AND category_set=?",
                (s["id"], cat_set)
            ).fetchone()["c"]
            if ccount == 0:
                defaults = ["닭", "소스", "용기", "조미료", "식용유", "떡", "면", "야채"] if cat_set == "ingredients" else ["레시피-기본", "레시피-양념", "레시피-사이드"]
                for i, name in enumerate(defaults, 1):
                    cur.execute(
                        "INSERT INTO categories(store_id, category_set, name, position) VALUES (?,?,?,?)",
                        (s["id"], cat_set, name, i)
                    )
                # usage text seed
                cur.execute(
                    "INSERT OR REPLACE INTO ui_texts(store_id, category_set, usage_text, updated_at) VALUES (?,?,?,?)",
                    (s["id"], cat_set,
                     "사용방법:\n- 카테고리 클릭 → 품목 추가/선택 → 현재고/최소수량 입력 → 저장\n- 최소수량 미만이면 부족목록에 표시됩니다.\n",
                     int(time.time()))
                )
                con.commit()

    con.close()


@app.on_event("startup")
def _startup():
    init_db()


def require_admin(x_admin_token: Optional[str]):
    if not x_admin_token or x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")


def validate_set(category_set: str):
    if category_set not in ("ingredients", "recipes"):
        raise HTTPException(status_code=400, detail="category_set must be 'ingredients' or 'recipes'")


# --------------------------
# Models
# --------------------------
class StoreOut(BaseModel):
    id: int
    name: str


class CategoryOut(BaseModel):
    id: int
    store_id: int
    category_set: str
    name: str
    position: int


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)


class CategoryRename(BaseModel):
    name: str = Field(min_length=1, max_length=50)


class ItemOut(BaseModel):
    id: int
    store_id: int
    category_set: str
    category_id: int
    category_name: str
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
    name: str = Field(min_length=1, max_length=80)
    current_qty: float = 0
    min_qty: float = 0
    unit: str = ""
    price: str = ""
    vendor: str = ""
    storage: str = ""
    origin: str = ""
    purchase_url: str = ""
    note: str = ""


class ItemUpdate(BaseModel):
    current_qty: Optional[float] = None
    min_qty: Optional[float] = None
    unit: Optional[str] = None
    price: Optional[str] = None
    vendor: Optional[str] = None
    storage: Optional[str] = None
    origin: Optional[str] = None
    purchase_url: Optional[str] = None
    note: Optional[str] = None


class UsageOut(BaseModel):
    store_id: int
    category_set: str
    usage_text: str
    updated_at: int


class UsageUpdate(BaseModel):
    usage_text: str = ""


# --------------------------
# Health
# --------------------------
@app.get("/")
def root():
    return {"ok": True, "service": SERVICE, "version": VERSION}


@app.get("/health")
def health():
    return {"ok": True, "service": SERVICE, "version": VERSION}


# --------------------------
# Stores (public)
# --------------------------
@app.get("/api/stores", response_model=List[StoreOut])
def list_stores():
    con = _conn()
    rows = con.execute("SELECT id, name FROM stores ORDER BY id").fetchall()
    con.close()
    return [dict(r) for r in rows]


# --------------------------
# Usage text (GET public / PUT admin)
# --------------------------
@app.get("/api/ui_text", response_model=UsageOut)
def get_usage_text(
    store_id: int = Query(...),
    category_set: str = Query(...)
):
    validate_set(category_set)
    con = _conn()
    row = con.execute(
        "SELECT store_id, category_set, usage_text, updated_at FROM ui_texts WHERE store_id=? AND category_set=?",
        (store_id, category_set)
    ).fetchone()
    con.close()
    if not row:
        return {"store_id": store_id, "category_set": category_set, "usage_text": "", "updated_at": 0}
    return dict(row)


@app.put("/api/ui_text", response_model=UsageOut)
def update_usage_text(
    body: UsageUpdate,
    store_id: int = Query(...),
    category_set: str = Query(...),
    x_admin_token: Optional[str] = Header(default=None)
):
    validate_set(category_set)
    require_admin(x_admin_token)
    con = _conn()
    now = int(time.time())
    con.execute(
        "INSERT OR REPLACE INTO ui_texts(store_id, category_set, usage_text, updated_at) VALUES (?,?,?,?)",
        (store_id, category_set, body.usage_text or "", now)
    )
    con.commit()
    row = con.execute(
        "SELECT store_id, category_set, usage_text, updated_at FROM ui_texts WHERE store_id=? AND category_set=?",
        (store_id, category_set)
    ).fetchone()
    con.close()
    return dict(row)


# --------------------------
# Categories (GET public / write admin)
# --------------------------
@app.get("/api/categories", response_model=List[CategoryOut])
def list_categories(
    store_id: int = Query(...),
    category_set: str = Query(...)
):
    validate_set(category_set)
    con = _conn()
    rows = con.execute(
        "SELECT id, store_id, category_set, name, position FROM categories WHERE store_id=? AND category_set=? ORDER BY position, id",
        (store_id, category_set)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


@app.post("/api/categories", response_model=CategoryOut)
def create_category(
    body: CategoryCreate,
    store_id: int = Query(...),
    category_set: str = Query(...),
    x_admin_token: Optional[str] = Header(default=None)
):
    validate_set(category_set)
    require_admin(x_admin_token)
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(400, "name required")

    con = _conn()
    mx = con.execute(
        "SELECT COALESCE(MAX(position), 0) AS m FROM categories WHERE store_id=? AND category_set=?",
        (store_id, category_set)
    ).fetchone()["m"]
    pos = int(mx) + 1
    try:
        con.execute(
            "INSERT INTO categories(store_id, category_set, name, position) VALUES (?,?,?,?)",
            (store_id, category_set, name, pos)
        )
        con.commit()
    except sqlite3.IntegrityError:
        con.close()
        raise HTTPException(409, "Category already exists")
    row = con.execute(
        "SELECT id, store_id, category_set, name, position FROM categories WHERE store_id=? AND category_set=? AND name=?",
        (store_id, category_set, name)
    ).fetchone()
    con.close()
    return dict(row)


@app.put("/api/categories/{category_id}", response_model=CategoryOut)
def rename_category(
    category_id: int,
    body: CategoryRename,
    store_id: int = Query(...),
    category_set: str = Query(...),
    x_admin_token: Optional[str] = Header(default=None)
):
    validate_set(category_set)
    require_admin(x_admin_token)
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(400, "name required")
    con = _conn()
    row = con.execute(
        "SELECT id FROM categories WHERE id=? AND store_id=? AND category_set=?",
        (category_id, store_id, category_set)
    ).fetchone()
    if not row:
        con.close()
        raise HTTPException(404, "Category not found")
    try:
        con.execute(
            "UPDATE categories SET name=? WHERE id=?",
            (name, category_id)
        )
        con.commit()
    except sqlite3.IntegrityError:
        con.close()
        raise HTTPException(409, "Category name conflict")
    out = con.execute(
        "SELECT id, store_id, category_set, name, position FROM categories WHERE id=?",
        (category_id,)
    ).fetchone()
    con.close()
    return dict(out)


@app.delete("/api/categories/{category_id}")
def delete_category(
    category_id: int,
    store_id: int = Query(...),
    category_set: str = Query(...),
    x_admin_token: Optional[str] = Header(default=None)
):
    validate_set(category_set)
    require_admin(x_admin_token)
    con = _conn()
    row = con.execute(
        "SELECT id FROM categories WHERE id=? AND store_id=? AND category_set=?",
        (category_id, store_id, category_set)
    ).fetchone()
    if not row:
        con.close()
        raise HTTPException(404, "Category not found")

    con.execute("DELETE FROM categories WHERE id=?", (category_id,))
    # re-pack positions
    rows = con.execute(
        "SELECT id FROM categories WHERE store_id=? AND category_set=? ORDER BY position, id",
        (store_id, category_set)
    ).fetchall()
    for i, r in enumerate(rows, 1):
        con.execute("UPDATE categories SET position=? WHERE id=?", (i, r["id"]))
    con.commit()
    con.close()
    return {"ok": True}


@app.post("/api/categories/{category_id}/move")
def move_category(
    category_id: int,
    direction: str = Query(..., description="up|down"),
    store_id: int = Query(...),
    category_set: str = Query(...),
    x_admin_token: Optional[str] = Header(default=None)
):
    validate_set(category_set)
    require_admin(x_admin_token)
    if direction not in ("up", "down"):
        raise HTTPException(400, "direction must be up|down")

    con = _conn()
    rows = con.execute(
        "SELECT id, position FROM categories WHERE store_id=? AND category_set=? ORDER BY position, id",
        (store_id, category_set)
    ).fetchall()
    ids = [r["id"] for r in rows]
    if category_id not in ids:
        con.close()
        raise HTTPException(404, "Category not found")

    idx = ids.index(category_id)
    if direction == "up" and idx > 0:
        ids[idx], ids[idx - 1] = ids[idx - 1], ids[idx]
    if direction == "down" and idx < len(ids) - 1:
        ids[idx], ids[idx + 1] = ids[idx + 1], ids[idx]

    for i, cid in enumerate(ids, 1):
        con.execute("UPDATE categories SET position=? WHERE id=?", (i, cid))
    con.commit()
    con.close()
    return {"ok": True}


# --------------------------
# Items (public read/write)
# --------------------------
@app.get("/api/items", response_model=List[ItemOut])
def list_items(
    store_id: int = Query(...),
    category_set: str = Query(...),
    category_id: int = Query(...),
    q: str = Query(default="")
):
    validate_set(category_set)
    con = _conn()
    cat = con.execute(
        "SELECT name FROM categories WHERE id=? AND store_id=? AND category_set=?",
        (category_id, store_id, category_set)
    ).fetchone()
    if not cat:
        con.close()
        raise HTTPException(404, "Category not found")

    q2 = f"%{q.strip()}%" if q.strip() else "%"
    rows = con.execute(
        """
        SELECT i.*, c.name AS category_name
        FROM items i
        JOIN categories c ON c.id=i.category_id
        WHERE i.store_id=? AND i.category_set=? AND i.category_id=? AND i.name LIKE ?
        ORDER BY i.name COLLATE NOCASE
        """,
        (store_id, category_set, category_id, q2)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


@app.post("/api/items", response_model=ItemOut)
def create_item(
    body: ItemCreate,
    store_id: int = Query(...),
    category_set: str = Query(...),
    category_id: int = Query(...)
):
    validate_set(category_set)
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(400, "name required")

    con = _conn()
    cat = con.execute(
        "SELECT name FROM categories WHERE id=? AND store_id=? AND category_set=?",
        (category_id, store_id, category_set)
    ).fetchone()
    if not cat:
        con.close()
        raise HTTPException(404, "Category not found")

    now = int(time.time())
    try:
        con.execute(
            """
            INSERT INTO items(
              store_id, category_set, category_id, name,
              current_qty, min_qty, unit, price, vendor, storage, origin, purchase_url, note, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                store_id, category_set, category_id, name,
                float(body.current_qty or 0), float(body.min_qty or 0),
                body.unit or "", body.price or "", body.vendor or "",
                body.storage or "", body.origin or "", body.purchase_url or "",
                body.note or "", now
            )
        )
        con.commit()
    except sqlite3.IntegrityError:
        con.close()
        raise HTTPException(409, "Item already exists")

    row = con.execute(
        """
        SELECT i.*, c.name AS category_name
        FROM items i JOIN categories c ON c.id=i.category_id
        WHERE i.store_id=? AND i.category_set=? AND i.category_id=? AND i.name=?
        """,
        (store_id, category_set, category_id, name)
    ).fetchone()
    con.close()
    return dict(row)


@app.put("/api/items/{item_id}", response_model=ItemOut)
def update_item(
    item_id: int,
    body: ItemUpdate,
    store_id: int = Query(...),
    category_set: str = Query(...)
):
    validate_set(category_set)
    con = _conn()
    row = con.execute(
        "SELECT * FROM items WHERE id=? AND store_id=? AND category_set=?",
        (item_id, store_id, category_set)
    ).fetchone()
    if not row:
        con.close()
        raise HTTPException(404, "Item not found")

    fields = {}
    for k, v in body.dict().items():
        if v is not None:
            fields[k] = v

    if not fields:
        con.close()
        raise HTTPException(400, "No fields to update")

    fields["updated_at"] = int(time.time())

    sets = ", ".join([f"{k}=?" for k in fields.keys()])
    vals = list(fields.values()) + [item_id]

    con.execute(f"UPDATE items SET {sets} WHERE id=?", vals)
    con.commit()

    out = con.execute(
        """
        SELECT i.*, c.name AS category_name
        FROM items i JOIN categories c ON c.id=i.category_id
        WHERE i.id=? AND i.store_id=? AND i.category_set=?
        """,
        (item_id, store_id, category_set)
    ).fetchone()
    con.close()
    return dict(out)


@app.delete("/api/items/{item_id}")
def delete_item(
    item_id: int,
    store_id: int = Query(...),
    category_set: str = Query(...)
):
    validate_set(category_set)
    con = _conn()
    row = con.execute(
        "SELECT id FROM items WHERE id=? AND store_id=? AND category_set=?",
        (item_id, store_id, category_set)
    ).fetchone()
    if not row:
        con.close()
        raise HTTPException(404, "Item not found")
    con.execute("DELETE FROM items WHERE id=?", (item_id,))
    con.commit()
    con.close()
    return {"ok": True}


# --------------------------
# Shortages (public)
# --------------------------
@app.get("/api/shortages")
def list_shortages(
    store_id: int = Query(...),
    category_set: str = Query(...)
):
    validate_set(category_set)
    con = _conn()
    rows = con.execute(
        """
        SELECT i.id, i.category_id, c.name AS category_name,
               i.name, i.current_qty, i.min_qty, i.unit, i.price, i.purchase_url
        FROM items i
        JOIN categories c ON c.id=i.category_id
        WHERE i.store_id=? AND i.category_set=? AND i.current_qty < i.min_qty
        ORDER BY c.position, i.name COLLATE NOCASE
        """,
        (store_id, category_set)
    ).fetchall()
    con.close()

    out = []
    for r in rows:
        need = float(r["min_qty"]) - float(r["current_qty"])
        out.append({
            "id": r["id"],
            "category_id": r["category_id"],
            "category_name": r["category_name"],
            "name": r["name"],
            "current_qty": r["current_qty"],
            "min_qty": r["min_qty"],
            "need_qty": need,
            "unit": r["unit"],
            "price": r["price"],
            "purchase_url": r["purchase_url"],
        })
    return {"ok": True, "items": out}
