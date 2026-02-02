import os
import re
import sqlite3
import hashlib
from datetime import datetime
from typing import Optional, Dict, Any

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# =========================
# 기본 설정
# =========================
APP_VERSION = "5.0"
SERVICE_NAME = "stock-server"

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "dldydtjq159").strip()
DATA_DIR = os.getenv("DATA_DIR", "/data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "stock.db")

# =========================
# FastAPI
# =========================
app = FastAPI(title=SERVICE_NAME, version=APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# 유틸
# =========================
def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def require_admin(token: Optional[str]):
    if not token or token.strip() != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def fnum(v):
    try:
        return float(v)
    except Exception:
        return 0.0

# =========================
# DB 초기화
# =========================
def init_db():
    con = db()
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS stores (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS store_meta (
        store_id TEXT PRIMARY KEY,
        usage_text TEXT DEFAULT '',
        updated_at TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_id TEXT,
        key TEXT,
        label TEXT,
        sort INTEGER,
        UNIQUE(store_id, key)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_id TEXT,
        category_key TEXT,
        name TEXT,

        current_stock REAL DEFAULT 0,
        min_stock REAL DEFAULT 0,
        unit TEXT DEFAULT '',

        price TEXT DEFAULT '',
        vendor TEXT DEFAULT '',
        storage TEXT DEFAULT '',
        origin TEXT DEFAULT '',
        buy_link TEXT DEFAULT '',
        memo TEXT DEFAULT '',

        updated_at TEXT,
        UNIQUE(store_id, category_key, name)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS admin (
        id INTEGER PRIMARY KEY CHECK(id=1),
        password_hash TEXT,
        updated_at TEXT
    )
    """)

    # 기본 매장
    stores = [
        ("lab", "김경영 요리 연구소"),
        ("youth", "청년회관")
    ]
    for sid, name in stores:
        cur.execute("INSERT OR IGNORE INTO stores VALUES (?,?)", (sid, name))
        cur.execute(
            "INSERT OR IGNORE INTO store_meta VALUES (?,?,?)",
            (sid, "카테고리 → 품목 선택 → 저장", now())
        )

    # 기본 관리자 비밀번호
    r = cur.execute("SELECT 1 FROM admin WHERE id=1").fetchone()
    if not r:
        h = hashlib.sha256("tkfkd4026".encode()).hexdigest()
        cur.execute("INSERT INTO admin VALUES (1, ?, ?)", (h, now()))

    con.commit()
    con.close()

init_db()

# =========================
# API
# =========================
@app.get("/")
def root():
    return {"ok": True, "service": SERVICE_NAME, "version": APP_VERSION}

@app.get("/api/stores")
def stores():
    con = db()
    rows = con.execute("SELECT id,name FROM stores").fetchall()
    con.close()
    return {"stores": [dict(r) for r in rows]}

@app.get("/api/stores/{sid}/meta")
def store_meta(sid: str):
    con = db()
    meta = con.execute("SELECT * FROM store_meta WHERE store_id=?", (sid,)).fetchone()
    cats = con.execute(
        "SELECT key,label,sort FROM categories WHERE store_id=? ORDER BY sort",
        (sid,)
    ).fetchall()
    con.close()
    return {
        "meta": {
            "usage_text": meta["usage_text"],
            "categories": [dict(c) for c in cats]
        }
    }

@app.put("/api/stores/{sid}/meta")
def update_meta(
    sid: str,
    payload: Dict[str, Any],
    x_admin_token: Optional[str] = Header(default=None)
):
    require_admin(x_admin_token)
    con = db()
    con.execute(
        "UPDATE store_meta SET usage_text=?, updated_at=? WHERE store_id=?",
        (payload.get("usage_text",""), now(), sid)
    )
    con.execute("DELETE FROM categories WHERE store_id=?", (sid,))
    for c in payload.get("categories", []):
        con.execute(
            "INSERT INTO categories(store_id,key,label,sort) VALUES (?,?,?,?)",
            (sid, c["key"], c["label"], c.get("sort",0))
        )
    con.commit()
    con.close()
    return {"ok": True}

@app.get("/api/stores/{sid}/items/{ck}")
def list_items(sid: str, ck: str):
    con = db()
    rows = con.execute(
        "SELECT * FROM items WHERE store_id=? AND category_key=? ORDER BY name",
        (sid, ck)
    ).fetchall()
    con.close()
    return {"items": [dict(r) for r in rows]}

@app.post("/api/stores/{sid}/items/{ck}")
def add_item(sid: str, ck: str, payload: Dict[str, Any]):
    con = db()
    con.execute("""
        INSERT INTO items
        (store_id,category_key,name,current_stock,min_stock,unit,
         price,vendor,storage,origin,buy_link,memo,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        sid, ck, payload["name"],
        fnum(payload.get("current_stock")),
        fnum(payload.get("min_stock")),
        payload.get("unit",""),
        payload.get("price",""),
        payload.get("vendor",""),
        payload.get("storage",""),
        payload.get("origin",""),
        payload.get("buy_link",""),
        payload.get("memo",""),
        now()
    ))
    con.commit()
    con.close()
    return {"ok": True}

@app.put("/api/stores/{sid}/items/{ck}/{iid}")
def update_item(sid: str, ck: str, iid: int, payload: Dict[str, Any]):
    con = db()
    con.execute("""
        UPDATE items SET
        current_stock=?, min_stock=?, unit=?,
        price=?, vendor=?, storage=?, origin=?,
        buy_link=?, memo=?, updated_at=?
        WHERE id=? AND store_id=? AND category_key=?
    """, (
        fnum(payload.get("current_stock")),
        fnum(payload.get("min_stock")),
        payload.get("unit",""),
        payload.get("price",""),
        payload.get("vendor",""),
        payload.get("storage",""),
        payload.get("origin",""),
        payload.get("buy_link",""),
        payload.get("memo",""),
        now(), iid, sid, ck
    ))
    con.commit()
    con.close()
    return {"ok": True, "updated_at": now()}

@app.get("/api/shortages/{sid}")
def shortages(sid: str):
    con = db()
    rows = con.execute("SELECT * FROM items WHERE store_id=?", (sid,)).fetchall()
    cats = {
        c["key"]: c["label"]
        for c in con.execute("SELECT key,label FROM categories WHERE store_id=?", (sid,))
    }
    con.close()

    out = []
    for r in rows:
        need = r["min_stock"] - r["current_stock"]
        if need > 0:
            out.append({
                "category_key": r["category_key"],
                "category_label": cats.get(r["category_key"], r["category_key"]),
                "name": r["name"],
                "current_stock": r["current_stock"],
                "min_stock": r["min_stock"],
                "need": need,
                "unit": r["unit"],
                "price": r["price"],
                "buy_link": r["buy_link"]
            })
    return {"shortages": out}

@app.post("/api/admin/change-password")
def change_pw(
    payload: Dict[str, Any],
    x_admin_token: Optional[str] = Header(default=None)
):
    require_admin(x_admin_token)
    old = payload.get("old_password","")
    new = payload.get("new_password","")
    con = db()
    row = con.execute("SELECT password_hash FROM admin WHERE id=1").fetchone()
    if hashlib.sha256(old.encode()).hexdigest() != row["password_hash"]:
        con.close()
        raise HTTPException(status_code=401, detail="wrong password")
    con.execute(
        "UPDATE admin SET password_hash=?, updated_at=? WHERE id=1",
        (hashlib.sha256(new.encode()).hexdigest(), now())
    )
    con.commit()
    con.close()
    return {"ok": True}
