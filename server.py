# server.py
import os, sqlite3, uuid, time
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

SERVICE = "stock-server"
VERSION = "A-1.0"

DATA_DIR = os.getenv("DATA_DIR", "/data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "stock.db")

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "dldydtjq159")

app = FastAPI(title=SERVICE, version=VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_headers=["*"],
    allow_methods=["*"],
)

def db():
    return sqlite3.connect(DB_PATH)

def require_admin(x_admin_token: str | None):
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(401, "Unauthorized")

def init_db():
    con = db()
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS stores(
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS categories(
        id TEXT PRIMARY KEY,
        store_id TEXT,
        name TEXT,
        ord INTEGER
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS items(
        id TEXT PRIMARY KEY,
        category_id TEXT,
        name TEXT,
        stock INTEGER,
        min_stock INTEGER,
        unit TEXT,
        price INTEGER,
        link TEXT
    )""")

    # stores (중복 방지)
    cur.execute("DELETE FROM stores")
    cur.executemany(
        "INSERT INTO stores VALUES (?,?)",
        [
            ("store1", "김경영 요리 연구소"),
            ("store2", "청년회관"),
        ]
    )
    con.commit()
    con.close()

init_db()

@app.get("/")
def root():
    return {"ok": True, "service": SERVICE, "version": VERSION}

# ---------- STORES ----------
@app.get("/api/stores")
def stores():
    con = db()
    rows = con.execute("SELECT id,name FROM stores").fetchall()
    con.close()
    return [{"id": r[0], "name": r[1]} for r in rows]

# ---------- CATEGORIES ----------
@app.get("/api/categories/{store_id}")
def categories(store_id: str):
    con = db()
    rows = con.execute(
        "SELECT id,name,ord FROM categories WHERE store_id=? ORDER BY ord",
        (store_id,)
    ).fetchall()
    con.close()
    return [{"id": r[0], "name": r[1], "ord": r[2]} for r in rows]

@app.post("/api/categories/{store_id}")
def add_category(store_id: str, data: dict, x_admin_token: str | None = Header(None)):
    require_admin(x_admin_token)
    cid = str(uuid.uuid4())
    con = db()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO categories VALUES (?,?,?,?)",
        (cid, store_id, data["name"], int(time.time()))
    )
    con.commit()
    con.close()
    return {"id": cid}

# ---------- ITEMS ----------
@app.get("/api/items/{category_id}")
def items(category_id: str):
    con = db()
    rows = con.execute("""
        SELECT id,name,stock,min_stock,unit,price,link
        FROM items WHERE category_id=?
    """, (category_id,)).fetchall()
    con.close()
    return [
        {
            "id": r[0], "name": r[1],
            "stock": r[2], "min_stock": r[3],
            "unit": r[4], "price": r[5],
            "link": r[6]
        } for r in rows
    ]

@app.post("/api/items/{category_id}")
def add_item(category_id: str, data: dict):
    iid = str(uuid.uuid4())
    con = db()
    con.execute("""
        INSERT INTO items VALUES (?,?,?,?,?,?,?)
    """, (
        iid, category_id, data["name"],
        data.get("stock", 0),
        data.get("min_stock", 0),
        data.get("unit", ""),
        data.get("price", 0),
        data.get("link", "")
    ))
    con.commit()
    con.close()
    return {"id": iid}

@app.put("/api/items/{item_id}")
def update_item(item_id: str, data: dict):
    con = db()
    con.execute("""
        UPDATE items SET
        stock=?, min_stock=?, unit=?, price=?, link=?
        WHERE id=?
    """, (
        data["stock"], data["min_stock"],
        data["unit"], data["price"],
        data["link"], item_id
    ))
    con.commit()
    con.close()
    return {"ok": True}

# ---------- SHORTAGE ----------
@app.get("/api/shortage/{store_id}")
def shortage(store_id: str):
    con = db()
    rows = con.execute("""
    SELECT c.name, i.name, i.stock, i.min_stock, i.unit
    FROM items i
    JOIN categories c ON i.category_id=c.id
    WHERE c.store_id=? AND i.stock < i.min_stock
    """, (store_id,)).fetchall()
    con.close()

    return [
        {
            "category": r[0],
            "item": r[1],
            "stock": r[2],
            "need": r[3] - r[2],
            "unit": r[4],
        } for r in rows
    ]
