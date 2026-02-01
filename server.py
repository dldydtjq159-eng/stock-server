# server.py
import os, uuid, time, sqlite3
from typing import Optional
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

SERVICE = "stock-server"
VERSION = "FINAL-1.1"

DATA_DIR = os.getenv("DATA_DIR", "/data")
DB_PATH = os.path.join(DATA_DIR, "stock.db")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "dldydtjq159")

os.makedirs(DATA_DIR, exist_ok=True)

def db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def require_admin(token: Optional[str]):
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

def now():
    return time.strftime("%Y-%m-%d %H:%M:%S")

DEFAULT_CATEGORIES = ["닭", "소스", "용기", "조미료", "식용유", "떡", "면", "야채"]

def seed_default_categories(con, store_id: str):
    cur = con.cursor()
    cnt = cur.execute("SELECT COUNT(*) AS c FROM categories WHERE store_id=?", (store_id,)).fetchone()["c"]
    if cnt and int(cnt) > 0:
        return
    base = int(time.time())
    for i, name in enumerate(DEFAULT_CATEGORIES):
        cur.execute(
            "INSERT OR IGNORE INTO categories VALUES (?,?,?,?)",
            (str(uuid.uuid4()), store_id, name, base + i)
        )

def init_db():
    con = db()
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS stores (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL UNIQUE
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id TEXT PRIMARY KEY,
        store_id TEXT NOT NULL,
        name TEXT NOT NULL,
        ord INTEGER DEFAULT 0,
        UNIQUE(store_id, name)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id TEXT PRIMARY KEY,
        store_id TEXT NOT NULL,
        category_id TEXT NOT NULL,
        name TEXT NOT NULL,
        stock INTEGER DEFAULT 0,
        min_stock INTEGER DEFAULT 0,
        unit TEXT,
        price TEXT,
        vendor TEXT,
        buy_link TEXT,
        memo TEXT,
        updated_at TEXT
    )
    """)

    # 기본 매장 (중복 방지)
    cur.execute("INSERT OR IGNORE INTO stores VALUES (?,?)", ("store1", "김경영 요리연구소"))
    cur.execute("INSERT OR IGNORE INTO stores VALUES (?,?)", ("store2", "청년회관"))

    # ✅ 매장별 기본 카테고리 자동 생성
    seed_default_categories(con, "store1")
    seed_default_categories(con, "store2")

    con.commit()
    con.close()

init_db()

app = FastAPI(title=SERVICE, version=VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_headers=["*"],
    allow_methods=["*"],
)

@app.get("/")
def root():
    return {"ok": True, "service": SERVICE, "version": VERSION}

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/api/stores")
def list_stores():
    con = db()
    rows = con.execute("SELECT * FROM stores").fetchall()
    con.close()
    return {"stores": [dict(r) for r in rows]}

@app.get("/api/categories/{store_id}")
def list_categories(store_id: str):
    con = db()
    # 혹시 DB에 카테고리 0개면 여기서도 한번 더 시드
    seed_default_categories(con, store_id)
    con.commit()
    rows = con.execute(
        "SELECT * FROM categories WHERE store_id=? ORDER BY ord",
        (store_id,)
    ).fetchall()
    con.close()
    return {"categories": [dict(r) for r in rows]}

@app.post("/api/categories/{store_id}")
def add_category(store_id: str, data: dict,
                 x_admin_token: Optional[str] = Header(None)):
    require_admin(x_admin_token)
    name = (data.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "name required")
    con = db()
    con.execute(
        "INSERT INTO categories VALUES (?,?,?,?)",
        (str(uuid.uuid4()), store_id, name, int(time.time()))
    )
    con.commit()
    con.close()
    return {"ok": True}

@app.delete("/api/categories/{category_id}")
def delete_category(category_id: str,
                    x_admin_token: Optional[str] = Header(None)):
    require_admin(x_admin_token)
    con = db()
    con.execute("DELETE FROM items WHERE category_id=?", (category_id,))
    con.execute("DELETE FROM categories WHERE id=?", (category_id,))
    con.commit()
    con.close()
    return {"ok": True}

@app.get("/api/items/{store_id}/{category_id}")
def list_items(store_id: str, category_id: str):
    con = db()
    rows = con.execute("""
        SELECT * FROM items
        WHERE store_id=? AND category_id=?
        ORDER BY name
    """, (store_id, category_id)).fetchall()
    con.close()
    return {"items": [dict(r) for r in rows]}

@app.post("/api/items/{store_id}/{category_id}")
def add_item(store_id: str, category_id: str, data: dict):
    name = (data.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "name required")

    con = db()
    con.execute("""
        INSERT INTO items VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (
        str(uuid.uuid4()), store_id, category_id,
        name,
        int(data.get("stock", 0)),
        int(data.get("min_stock", 0)),
        data.get("unit", "") or "",
        data.get("price", "") or "",
        data.get("vendor", "") or "",
        data.get("buy_link", "") or "",
        now()
    ))
    con.commit()
    con.close()
    return {"ok": True}

@app.put("/api/item/{item_id}")
def update_item(item_id: str, data: dict):
    con = db()
    con.execute("""
        UPDATE items SET
        stock=?, min_stock=?, unit=?, price=?, vendor=?,
        buy_link=?, memo=?, updated_at=?
        WHERE id=?
    """, (
        int(data.get("stock", 0)),
        int(data.get("min_stock", 0)),
        data.get("unit", "") or "",
        data.get("price", "") or "",
        data.get("vendor", "") or "",
        data.get("buy_link", "") or "",
        data.get("memo", "") or "",
        now(),
        item_id
    ))
    con.commit()
    con.close()
    return {"ok": True}

@app.get("/api/shortage/{store_id}")
def shortage(store_id: str):
    con = db()
    rows = con.execute("""
        SELECT i.*, c.name AS category_name
        FROM items i
        JOIN categories c ON i.category_id=c.id
        WHERE i.store_id=? AND i.stock < i.min_stock
        ORDER BY category_name, i.name
    """, (store_id,)).fetchall()
    con.close()

    result = []
    for r in rows:
        d = dict(r)
        d["need"] = int(d["min_stock"]) - int(d["stock"])
        result.append(d)

    return {"shortage": result}
