# server.py
import os, json, uuid, time, sqlite3
from typing import Optional, List
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# ===============================
# 기본 설정
# ===============================
SERVICE = "stock-server"
VERSION = "FINAL-1.0"

DATA_DIR = os.getenv("DATA_DIR", "/data")
DB_PATH = os.path.join(DATA_DIR, "stock.db")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "dldydtjq159")

os.makedirs(DATA_DIR, exist_ok=True)

# ===============================
# DB 초기화
# ===============================
def db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

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
    cur.execute("INSERT OR IGNORE INTO stores VALUES (?,?)",
                ("store1", "김경영 요리연구소"))
    cur.execute("INSERT OR IGNORE INTO stores VALUES (?,?)",
                ("store2", "청년회관"))

    con.commit()
    con.close()

init_db()

# ===============================
# 앱
# ===============================
app = FastAPI(title=SERVICE, version=VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_headers=["*"],
    allow_methods=["*"],
)

def require_admin(token: Optional[str]):
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

def now():
    return time.strftime("%Y-%m-%d %H:%M:%S")

# ===============================
# 기본
# ===============================
@app.get("/")
def root():
    return {"ok": True, "service": SERVICE, "version": VERSION}

@app.get("/health")
def health():
    return {"ok": True}

# ===============================
# 매장
# ===============================
@app.get("/api/stores")
def list_stores():
    con = db()
    rows = con.execute("SELECT * FROM stores").fetchall()
    con.close()
    return {"stores": [dict(r) for r in rows]}

# ===============================
# 카테고리
# ===============================
@app.get("/api/categories/{store_id}")
def list_categories(store_id: str):
    con = db()
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
    name = data.get("name")
    if not name:
        raise HTTPException(400, "name required")

    con = db()
    cur = con.cursor()
    cur.execute("""
        INSERT INTO categories VALUES (?,?,?,?)
    """, (str(uuid.uuid4()), store_id, name, int(time.time())))
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

# ===============================
# 품목
# ===============================
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
    con = db()
    con.execute("""
        INSERT INTO items VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (
        str(uuid.uuid4()), store_id, category_id,
        data.get("name"),
        int(data.get("stock", 0)),
        int(data.get("min_stock", 0)),
        data.get("unit"),
        data.get("price"),
        data.get("vendor"),
        data.get("buy_link"),
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
        data.get("unit"),
        data.get("price"),
        data.get("vendor"),
        data.get("buy_link"),
        data.get("memo"),
        now(),
        item_id
    ))
    con.commit()
    con.close()
    return {"ok": True}

# ===============================
# 부족 목록
# ===============================
@app.get("/api/shortage/{store_id}")
def shortage(store_id: str):
    con = db()
    rows = con.execute("""
        SELECT * FROM items
        WHERE store_id=? AND stock < min_stock
    """, (store_id,)).fetchall()
    con.close()

    result = []
    for r in rows:
        d = dict(r)
        d["need"] = d["min_stock"] - d["stock"]
        result.append(d)

    return {"shortage": result}
