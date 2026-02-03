import os
import re
import sqlite3
from datetime import datetime
from typing import Optional, Dict, Any

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

APP_VERSION = "6.0"

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "dldydtjq159").strip()
DATA_DIR = os.getenv("DATA_DIR", "/data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "stock.db")

app = FastAPI(title="stock-server", version=APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = db()
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS stores (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS categories (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      store_id TEXT NOT NULL,
      key TEXT NOT NULL,
      label TEXT NOT NULL,
      sort INTEGER NOT NULL DEFAULT 0
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS items (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      store_id TEXT NOT NULL,
      category_key TEXT NOT NULL,
      name TEXT NOT NULL,
      current_stock REAL DEFAULT 0,
      min_stock REAL DEFAULT 0,
      unit TEXT DEFAULT '',
      price TEXT DEFAULT '',
      vendor TEXT DEFAULT '',
      origin TEXT DEFAULT '',
      memo TEXT DEFAULT '',
      updated_at TEXT
    );
    """)

    # 기본 매장
    stores = [
        ("lab", "김경영 요리 연구소"),
        ("youth", "청년회관"),
    ]
    for sid, sname in stores:
        cur.execute("INSERT OR IGNORE INTO stores(id, name) VALUES(?, ?)", (sid, sname))

    con.commit()
    con.close()

init_db()

@app.get("/")
def root():
    return {
        "ok": True,
        "service": "stock-server",
        "version": APP_VERSION,
        "status": "running",
        "time": now_str()
    }

@app.get("/version")
def version():
    return {"version": APP_VERSION}

@app.get("/api/stores")
def get_stores():
    con = db()
    rows = con.execute("SELECT id, name FROM stores").fetchall()
    con.close()
    return {"stores": [{"id": r["id"], "name": r["name"]} for r in rows]}

@app.post("/api/stores/{store_id}/categories")
def add_category(store_id: str, payload: Dict[str, Any], x_admin_token: Optional[str] = Header(None)):
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

    con = db()
    cur = con.cursor()
    key = payload.get("key")
    label = payload.get("label")
    sort = payload.get("sort", 0)

    cur.execute(
        "INSERT INTO categories(store_id, key, label, sort) VALUES(?,?,?,?)",
        (store_id, key, label, sort)
    )
    con.commit()
    con.close()
    return {"ok": True}

@app.get("/api/shortages/{store_id}")
def shortages(store_id: str):
    con = db()
    rows = con.execute(
        "SELECT * FROM items WHERE store_id=?",
        (store_id,)
    ).fetchall()
    con.close()

    out = []
    for r in rows:
        need = r["min_stock"] - r["current_stock"]
        if need > 0:
            out.append({
                "name": r["name"],
                "current": r["current_stock"],
                "min": r["min_stock"],
                "need": need,
                "vendor": r["vendor"],
                "origin": r["origin"]
            })
    return {"shortages": out}
