import os, sqlite3
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

APP_VERSION = "FINAL-1.0"

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "dldydtjq159")
DATA_DIR = os.getenv("DATA_DIR", "/data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "stock.db")

app = FastAPI(title="stock-server", version=APP_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- utils ----------------
def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def admin_check(token: Optional[str]):
    if token != ADMIN_TOKEN:
        raise HTTPException(401, "ADMIN ONLY")

# ---------------- init DB ----------------
def init_db():
    con = db()
    c = con.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS stores(
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS categories(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      store_id TEXT,
      name TEXT,
      type TEXT
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS items(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      store_id TEXT,
      category TEXT,
      name TEXT,
      current_stock REAL,
      min_stock REAL,
      unit TEXT,
      price TEXT,
      vendor TEXT,
      memo TEXT,
      updated_at TEXT
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS recipes(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      store_id TEXT,
      name TEXT
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS recipe_items(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      recipe_id INTEGER,
      item_name TEXT,
      amount REAL,
      unit TEXT
    )""")

    # 기본 매장
    c.execute("INSERT OR IGNORE INTO stores VALUES('lab','김경영 요리 연구소')")
    c.execute("INSERT OR IGNORE INTO stores VALUES('youth','청년회관')")

    con.commit()
    con.close()

init_db()

# ---------------- API ----------------
@app.get("/")
def root():
    return {"ok": True, "service": "stock-server", "version": APP_VERSION}

@app.get("/api/stores")
def stores():
    con = db()
    rows = con.execute("SELECT * FROM stores").fetchall()
    con.close()
    return {"stores": [dict(r) for r in rows]}

@app.get("/api/items/{store_id}")
def items(store_id: str):
    con = db()
    rows = con.execute(
        "SELECT * FROM items WHERE store_id=?", (store_id,)
    ).fetchall()
    con.close()
    return {"items": [dict(r) for r in rows]}

@app.post("/api/items/{store_id}")
def add_item(store_id: str, data: Dict[str, Any]):
    con = db()
    con.execute("""
      INSERT INTO items VALUES(NULL,?,?,?,?,?,?,?,?,?)
    """, (
        store_id,
        data["category"],
        data["name"],
        data["current_stock"],
        data["min_stock"],
        data["unit"],
        data.get("price",""),
        data.get("vendor",""),
        data.get("memo",""),
        now()
    ))
    con.commit()
    con.close()
    return {"ok": True}

@app.get("/api/recipes/{store_id}")
def recipes(store_id: str):
    con = db()
    r = con.execute("SELECT * FROM recipes WHERE store_id=?", (store_id,)).fetchall()
    con.close()
    return {"recipes": [dict(x) for x in r]}

@app.post("/api/recipes/{store_id}")
def add_recipe(store_id: str, data: Dict[str, Any]):
    con = db()
    cur = con.cursor()
    cur.execute("INSERT INTO recipes VALUES(NULL,?,?)", (store_id, data["name"]))
    rid = cur.lastrowid
    for it in data["items"]:
        cur.execute("""
          INSERT INTO recipe_items VALUES(NULL,?,?,?,?)
        """, (rid, it["name"], it["amount"], it["unit"]))
    con.commit()
    con.close()
    return {"ok": True}

@app.get("/api/shortages/{store_id}")
def shortages(store_id: str):
    con = db()
    items = con.execute("SELECT * FROM items WHERE store_id=?", (store_id,)).fetchall()
    out = []
    for i in items:
        if i["current_stock"] < i["min_stock"]:
            out.append({
                "name": i["name"],
                "need": i["min_stock"] - i["current_stock"],
                "unit": i["unit"],
                "category": i["category"]
            })
    con.close()
    return {"shortages": out}
