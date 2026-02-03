import os
import re
import sqlite3
from datetime import datetime
from typing import Optional, Dict, Any

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

APP_VERSION = "5.0"
SERVICE = "stock-server"

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "dldydtjq159").strip()
DATA_DIR = os.getenv("DATA_DIR", "/data").strip()
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "stock.db")

app = FastAPI(title=SERVICE, version=APP_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def slugify(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"[^a-z0-9\-_]", "", s)
    return (s or "cat")[:32]

def parse_float(v) -> float:
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    m = re.search(r"([0-9]+(\.[0-9]+)?)", s)
    if not m:
        return 0.0
    try:
        return float(m.group(1))
    except Exception:
        return 0.0

def require_admin(x_admin_token: Optional[str]):
    if not x_admin_token or x_admin_token.strip() != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized: invalid x-admin-token")

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
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
    CREATE TABLE IF NOT EXISTS store_meta (
      store_id TEXT PRIMARY KEY,
      usage_text TEXT NOT NULL DEFAULT '',
      updated_at TEXT NOT NULL,
      FOREIGN KEY(store_id) REFERENCES stores(id) ON DELETE CASCADE
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS categories (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      store_id TEXT NOT NULL,
      key TEXT NOT NULL,
      label TEXT NOT NULL,
      sort INTEGER NOT NULL DEFAULT 0,
      UNIQUE(store_id, key),
      FOREIGN KEY(store_id) REFERENCES stores(id) ON DELETE CASCADE
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS items (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      store_id TEXT NOT NULL,
      category_key TEXT NOT NULL,
      name TEXT NOT NULL,

      current_stock REAL NOT NULL DEFAULT 0,
      min_stock REAL NOT NULL DEFAULT 0,
      unit TEXT NOT NULL DEFAULT '',

      price TEXT NOT NULL DEFAULT '',
      vendor TEXT NOT NULL DEFAULT '',
      storage TEXT NOT NULL DEFAULT '',
      origin TEXT NOT NULL DEFAULT '',

      buy_link TEXT NOT NULL DEFAULT '',
      memo TEXT NOT NULL DEFAULT '',

      updated_at TEXT NOT NULL,

      UNIQUE(store_id, category_key, name),
      FOREIGN KEY(store_id) REFERENCES stores(id) ON DELETE CASCADE
    );
    """)

    default_stores = [
        ("lab", "김경영 요리 연구소"),
        ("youth", "청년회관"),
    ]
    for sid, sname in default_stores:
        cur.execute("INSERT OR IGNORE INTO stores(id, name) VALUES(?, ?)", (sid, sname))

    for sid, _ in default_stores:
        cur.execute("SELECT 1 FROM store_meta WHERE store_id=?", (sid,))
        if cur.fetchone() is None:
            cur.execute(
                "INSERT INTO store_meta(store_id, usage_text, updated_at) VALUES(?,?,?)",
                (sid, "카테고리 클릭 → 품목 추가/선택 → 저장", now_str())
            )

    default_categories = [
        ("seasoning", "조미료", 0),
        ("oil", "식용유", 10),
        ("ricecake", "떡", 20),
        ("noodle", "면", 30),
        ("veggie", "야채", 40),
    ]
    for sid, _ in default_stores:
        c = con.execute("SELECT COUNT(*) AS c FROM categories WHERE store_id=?", (sid,)).fetchone()["c"]
        if c == 0:
            for k, label, sort in default_categories:
                cur.execute(
                    "INSERT OR IGNORE INTO categories(store_id, key, label, sort) VALUES(?,?,?,?)",
                    (sid, k, label, sort)
                )

    con.commit()
    con.close()

init_db()

def row_to_item(r):
    return {
        "id": r["id"],
        "name": r["name"],
        "current_stock": r["current_stock"],
        "min_stock": r["min_stock"],
        "unit": r["unit"],
        "price": r["price"],
        "vendor": r["vendor"],
        "storage": r["storage"],
        "origin": r["origin"],
        "buy_link": r["buy_link"],
        "memo": r["memo"],
        "updated_at": r["updated_at"],
    }

@app.get("/")
def root():
    return {"ok": True, "service": SERVICE, "version": APP_VERSION}

@app.get("/api/stores")
def get_stores():
    con = db()
    rows = con.execute("SELECT id, name FROM stores ORDER BY name ASC").fetchall()
    con.close()
    seen = set()
    stores = []
    for r in rows:
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        stores.append({"id": r["id"], "name": r["name"]})
    return {"stores": stores}

@app.get("/api/stores/{store_id}/meta")
def get_store_meta(store_id: str):
    con = db()
    st = con.execute("SELECT id, name FROM stores WHERE id=?", (store_id,)).fetchone()
    if not st:
        con.close()
        raise HTTPException(status_code=404, detail="Store not found")

    meta = con.execute("SELECT usage_text, updated_at FROM store_meta WHERE store_id=?", (store_id,)).fetchone()
    if not meta:
        con.execute("INSERT INTO store_meta(store_id, usage_text, updated_at) VALUES(?,?,?)", (store_id, "", now_str()))
        con.commit()
        meta = con.execute("SELECT usage_text, updated_at FROM store_meta WHERE store_id=?", (store_id,)).fetchone()

    cats = con.execute(
        "SELECT key, label, sort FROM categories WHERE store_id=? ORDER BY sort ASC, label ASC",
        (store_id,)
    ).fetchall()
    con.close()

    return {
        "meta": {
            "store": {"id": st["id"], "name": st["name"]},
            "usage_text": meta["usage_text"],
            "categories": [{"key": c["key"], "label": c["label"], "sort": c["sort"]} for c in cats],
            "updated_at": meta["updated_at"],
        }
    }

@app.put("/api/stores/{store_id}/meta")
def update_store_meta(store_id: str, payload: Dict[str, Any], x_admin_token: Optional[str] = Header(default=None)):
    require_admin(x_admin_token)
    usage_text = (payload.get("usage_text") or "").strip()
    categories = payload.get("categories") or []

    con = db()
    st = con.execute("SELECT 1 FROM stores WHERE id=?", (store_id,)).fetchone()
    if not st:
        con.close()
        raise HTTPException(status_code=404, detail="Store not found")

    con.execute("UPDATE store_meta SET usage_text=?, updated_at=? WHERE store_id=?", (usage_text, now_str(), store_id))

    con.execute("DELETE FROM categories WHERE store_id=?", (store_id,))
    for i, c in enumerate(categories):
        key = slugify(c.get("key") or f"cat{i}")
        label = (c.get("label") or key).strip()
        sort = int(c.get("sort") or i * 10)
        con.execute("INSERT INTO categories(store_id, key, label, sort) VALUES(?,?,?,?)", (store_id, key, label, sort))

    con.commit()
    con.close()
    return {"ok": True, "updated_at": now_str()}

@app.get("/api/stores/{store_id}/items/{category_key}")
def list_items(store_id: str, category_key: str):
    con = db()
    st = con.execute("SELECT 1 FROM stores WHERE id=?", (store_id,)).fetchone()
    if not st:
        con.close()
        raise HTTPException(status_code=404, detail="Store not found")
    rows = con.execute(
        "SELECT * FROM items WHERE store_id=? AND category_key=? ORDER BY name ASC",
        (store_id, category_key)
    ).fetchall()
    con.close()
    return {"items": [row_to_item(r) for r in rows]}

@app.post("/api/stores/{store_id}/items/{category_key}")
def add_item(store_id: str, category_key: str, payload: Dict[str, Any]):
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    con = db()
    st = con.execute("SELECT 1 FROM stores WHERE id=?", (store_id,)).fetchone()
    if not st:
        con.close()
        raise HTTPException(status_code=404, detail="Store not found")

    try:
        con.execute("""
            INSERT INTO items(
              store_id, category_key, name,
              current_stock, min_stock, unit,
              price, vendor, storage, origin,
              buy_link, memo, updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            store_id, category_key, name,
            parse_float(payload.get("current_stock")),
            parse_float(payload.get("min_stock")),
            (payload.get("unit") or "").strip(),
            (payload.get("price") or "").strip(),
            (payload.get("vendor") or "").strip(),
            (payload.get("storage") or "").strip(),
            (payload.get("origin") or "").strip(),
            (payload.get("buy_link") or "").strip(),
            (payload.get("memo") or "").strip(),
            now_str()
        ))
        con.commit()
    except sqlite3.IntegrityError:
        con.close()
        raise HTTPException(status_code=409, detail="Item already exists")

    con.close()
    return {"ok": True}

@app.put("/api/stores/{store_id}/items/{category_key}/{item_id}")
def update_item(store_id: str, category_key: str, item_id: int, payload: Dict[str, Any]):
    con = db()
    row = con.execute("SELECT * FROM items WHERE id=? AND store_id=? AND category_key=?", (item_id, store_id, category_key)).fetchone()
    if not row:
        con.close()
        raise HTTPException(status_code=404, detail="Item not found")

    def pick(key, default):
        return payload.get(key, default)

    con.execute("""
        UPDATE items SET
          current_stock=?,
          min_stock=?,
          unit=?,
          price=?,
          vendor=?,
          storage=?,
          origin=?,
          buy_link=?,
          memo=?,
          updated_at=?
        WHERE id=? AND store_id=? AND category_key=?
    """, (
        parse_float(pick("current_stock", row["current_stock"])),
        parse_float(pick("min_stock", row["min_stock"])),
        (pick("unit", row["unit"]) or "").strip(),
        (pick("price", row["price"]) or "").strip(),
        (pick("vendor", row["vendor"]) or "").strip(),
        (pick("storage", row["storage"]) or "").strip(),
        (pick("origin", row["origin"]) or "").strip(),
        (pick("buy_link", row["buy_link"]) or "").strip(),
        (pick("memo", row["memo"]) or "").strip(),
        now_str(),
        item_id, store_id, category_key
    ))
    con.commit()
    updated = con.execute("SELECT updated_at FROM items WHERE id=?", (item_id,)).fetchone()["updated_at"]
    con.close()
    return {"ok": True, "updated_at": updated}

@app.delete("/api/stores/{store_id}/items/{category_key}/{item_id}")
def delete_item(store_id: str, category_key: str, item_id: int):
    con = db()
    row = con.execute("SELECT 1 FROM items WHERE id=? AND store_id=? AND category_key=?", (item_id, store_id, category_key)).fetchone()
    if not row:
        con.close()
        raise HTTPException(status_code=404, detail="Item not found")
    con.execute("DELETE FROM items WHERE id=? AND store_id=? AND category_key=?", (item_id, store_id, category_key))
    con.commit()
    con.close()
    return {"ok": True}

@app.get("/api/shortages/{store_id}")
def shortages(store_id: str):
    con = db()
    st = con.execute("SELECT 1 FROM stores WHERE id=?", (store_id,)).fetchone()
    if not st:
        con.close()
        raise HTTPException(status_code=404, detail="Store not found")

    cats = con.execute("SELECT key, label FROM categories WHERE store_id=?", (store_id,)).fetchall()
    cat_label = {c["key"]: c["label"] for c in cats}

    rows = con.execute("SELECT * FROM items WHERE store_id=?", (store_id,)).fetchall()
    con.close()

    out = []
    for r in rows:
        cur = float(r["current_stock"] or 0)
        mn = float(r["min_stock"] or 0)
        need = mn - cur
        if need > 0:
            out.append({
                "category_key": r["category_key"],
                "category_label": cat_label.get(r["category_key"], r["category_key"]),
                "item_id": r["id"],
                "name": r["name"],
                "current_stock": cur,
                "min_stock": mn,
                "need": need,
                "unit": r["unit"],
                "price": r["price"],
                "buy_link": r["buy_link"],
                "updated_at": r["updated_at"],
            })

    out.sort(key=lambda x: (x["category_label"], x["name"]))
    return {"shortages": out}
