# server.py
import os, sqlite3, re
from datetime import datetime
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

APP_VERSION = "FINAL-1.0"
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "dldydtjq159")
DATA_DIR = os.getenv("DATA_DIR", "/data")
os.makedirs(DATA_DIR, exist_ok=True)
DB = os.path.join(DATA_DIR, "stock.db")

app = FastAPI(title="stock-server", version=APP_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

# ---------------- DB ----------------
def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def init_db():
    c = db()
    cur = c.cursor()

    cur.execute("""CREATE TABLE IF NOT EXISTS stores(
        id TEXT PRIMARY KEY,
        name TEXT
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS categories(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_id TEXT,
        key TEXT,
        label TEXT,
        sort INTEGER
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS items(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_id TEXT,
        category_key TEXT,
        name TEXT,
        current_stock REAL,
        min_stock REAL,
        unit TEXT,
        price TEXT,
        buy_link TEXT,
        updated_at TEXT
    )""")

    cur.execute("INSERT OR IGNORE INTO stores VALUES('lab','김경영 요리 연구소')")
    cur.execute("INSERT OR IGNORE INTO stores VALUES('youth','청년회관')")

    if cur.execute("SELECT COUNT(*) c FROM categories").fetchone()["c"] == 0:
        base = [
            ("chicken","닭",0),
            ("sauce","소스",10),
            ("container","용기",20),
            ("seasoning","조미료",30)
        ]
        for sid in ("lab","youth"):
            for k,l,s in base:
                cur.execute(
                    "INSERT INTO categories(store_id,key,label,sort) VALUES(?,?,?,?)",
                    (sid,k,l,s)
                )

    c.commit()
    c.close()

init_db()

def admin(token):
    if token != ADMIN_TOKEN:
        raise HTTPException(401,"Unauthorized")

# ---------------- API ----------------
@app.get("/")
def root():
    return {"ok":True,"service":"stock-server","version":APP_VERSION}

@app.get("/api/stores")
def stores():
    c=db()
    rows=c.execute("SELECT * FROM stores").fetchall()
    c.close()
    return {"stores":[dict(r) for r in rows]}

@app.get("/api/stores/{sid}/meta")
def meta(sid:str):
    c=db()
    cats=c.execute(
        "SELECT key,label FROM categories WHERE store_id=? ORDER BY sort",
        (sid,)
    ).fetchall()
    c.close()
    return {"meta":{"categories":[dict(x) for x in cats]}}

@app.get("/api/stores/{sid}/items/{cat}")
def items(sid:str,cat:str):
    c=db()
    rows=c.execute(
        "SELECT * FROM items WHERE store_id=? AND category_key=? ORDER BY name",
        (sid,cat)
    ).fetchall()
    c.close()
    return {"items":[dict(r) for r in rows]}

@app.post("/api/stores/{sid}/items/{cat}")
def add_item(sid:str,cat:str,payload:dict):
    c=db()
    c.execute("""INSERT INTO items
        (store_id,category_key,name,current_stock,min_stock,unit,price,buy_link,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?)""",
        (sid,cat,payload["name"],0,0,"","","",now())
    )
    c.commit()
    c.close()
    return {"ok":True}

@app.put("/api/stores/{sid}/items/{cat}/{iid}")
def upd_item(sid:str,cat:str,iid:int,payload:dict):
    c=db()
    c.execute("""UPDATE items SET
        current_stock=?,min_stock=?,unit=?,price=?,buy_link=?,updated_at=?
        WHERE id=?""",
        (
            payload.get("current_stock",0),
            payload.get("min_stock",0),
            payload.get("unit",""),
            payload.get("price",""),
            payload.get("buy_link",""),
            now(), iid
        )
    )
    c.commit()
    c.close()
    return {"ok":True}

@app.get("/api/shortages/{sid}")
def shortages(sid:str):
    c=db()
    rows=c.execute("SELECT * FROM items WHERE store_id=?", (sid,)).fetchall()
    c.close()
    out=[]
    for r in rows:
        if r["current_stock"] < r["min_stock"]:
            out.append(dict(r))
    return {"shortages":out}
