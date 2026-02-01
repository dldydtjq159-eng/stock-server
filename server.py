# server.py FINAL

import os, sqlite3, time
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="stock-server-final")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = "/data"
DB_PATH = f"{DATA_DIR}/stock.db"
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "dldydtjq159")


def get_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def admin_check(token):
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.on_event("startup")
def startup():
    db = get_db()
    c = db.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS stores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_id INTEGER,
        name TEXT,
        position INTEGER
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER,
        name TEXT,
        current INTEGER,
        minimum INTEGER,
        unit TEXT,
        price TEXT,
        vendor TEXT,
        link TEXT,
        updated INTEGER
    )
    """)

    c.execute("INSERT OR IGNORE INTO stores(name) VALUES (?)", ("김경영 요리 연구소",))
    c.execute("INSERT OR IGNORE INTO stores(name) VALUES (?)", ("청년회관",))

    db.commit()
    db.close()


@app.get("/")
def root():
    return {"ok": True, "service": "stock-server", "version": "FINAL"}


@app.get("/stores")
def stores():
    db = get_db()
    rows = db.execute("SELECT * FROM stores ORDER BY id").fetchall()
    db.close()
    return [dict(r) for r in rows]


@app.get("/categories/{store_id}")
def categories(store_id: int):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM categories WHERE store_id=? ORDER BY position",
        (store_id,)
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


@app.post("/categories/{store_id}")
def add_category(store_id: int, data: dict, x_admin_token: str = Header(None)):
    admin_check(x_admin_token)
    db = get_db()
    pos = db.execute(
        "SELECT COALESCE(MAX(position),0)+1 FROM categories WHERE store_id=?",
        (store_id,)
    ).fetchone()[0]
    db.execute(
        "INSERT INTO categories(store_id,name,position) VALUES (?,?,?)",
        (store_id, data["name"], pos)
    )
    db.commit()
    db.close()
    return {"ok": True}


@app.delete("/categories/{cat_id}")
def delete_category(cat_id: int, x_admin_token: str = Header(None)):
    admin_check(x_admin_token)
    db = get_db()
    db.execute("DELETE FROM items WHERE category_id=?", (cat_id,))
    db.execute("DELETE FROM categories WHERE id=?", (cat_id,))
    db.commit()
    db.close()
    return {"ok": True}


@app.get("/items/{category_id}")
def items(category_id: int):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM items WHERE category_id=? ORDER BY name",
        (category_id,)
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


@app.post("/items/{category_id}")
def add_item(category_id: int, data: dict):
    db = get_db()
    db.execute("""
    INSERT INTO items(category_id,name,current,minimum,unit,price,vendor,link,updated)
    VALUES (?,?,?,?,?,?,?,?,?)
    """, (
        category_id,
        data["name"],
        data.get("current", 0),
        data.get("minimum", 0),
        data.get("unit", ""),
        data.get("price", ""),
        data.get("vendor", ""),
        data.get("link", ""),
        int(time.time())
    ))
    db.commit()
    db.close()
    return {"ok": True}


@app.put("/items/{item_id}")
def update_item(item_id: int, data: dict):
    db = get_db()
    db.execute("""
    UPDATE items SET
        current=?, minimum=?, unit=?, price=?, vendor=?, link=?, updated=?
    WHERE id=?
    """, (
        data["current"],
        data["minimum"],
        data["unit"],
        data["price"],
        data["vendor"],
        data["link"],
        int(time.time()),
        item_id
    ))
    db.commit()
    db.close()
    return {"ok": True}


@app.get("/shortage/{store_id}")
def shortage(store_id: int):
    db = get_db()
    rows = db.execute("""
    SELECT c.name category, i.name, i.current, i.minimum, (i.minimum-i.current) need
    FROM items i
    JOIN categories c ON i.category_id=c.id
    WHERE c.store_id=? AND i.current < i.minimum
    """, (store_id,)).fetchall()
    db.close()
    return [dict(r) for r in rows]
