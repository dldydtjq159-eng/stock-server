import os
import json
import sqlite3
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

SERVICE = "stock-server"
VERSION = "4.0"

# ✅ Railway Variables에서 설정 추천
# ADMIN_TOKEN=dldydtjq159  (PC프로그램 config.json의 admin_token과 동일해야 함)
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "dldydtjq159")

# ✅ Railway Volume Mount path: /data 로 잡으면 DB가 영구저장됨
DATA_DIR = os.getenv("DATA_DIR", "/data")
DB_PATH = os.path.join(DATA_DIR, "stock.db")

os.makedirs(DATA_DIR, exist_ok=True)

app = FastAPI(title=SERVICE)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def require_admin(x_admin_token: Optional[str]):
    if not x_admin_token or x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS stores (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS store_meta (
        store_id TEXT PRIMARY KEY,
        usage_text TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(store_id) REFERENCES stores(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        store_id TEXT NOT NULL,
        key TEXT NOT NULL,
        label TEXT NOT NULL,
        sort INTEGER NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY(store_id, key),
        FOREIGN KEY(store_id) REFERENCES stores(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id TEXT PRIMARY KEY,
        store_id TEXT NOT NULL,
        category TEXT NOT NULL,
        name TEXT NOT NULL,
        real_stock TEXT NOT NULL,
        price TEXT NOT NULL,
        vendor TEXT NOT NULL,
        storage TEXT NOT NULL,
        origin TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(store_id, category, name),
        FOREIGN KEY(store_id) REFERENCES stores(id)
    )
    """)

    conn.commit()

    # seed stores
    cur.execute("SELECT COUNT(*) AS c FROM stores")
    c = cur.fetchone()["c"]
    if c == 0:
        stores = [
            ("lab", "김경영 요리 연구소"),
            ("hall", "청년회관"),
        ]
        cur.executemany("INSERT INTO stores(id, name) VALUES(?, ?)", stores)

        default_categories = [
            ("chicken", "닭"),
            ("sauce", "소스"),
            ("container", "용기"),
            ("seasoning", "조미료"),
            ("oil", "식용유"),
            ("ricecake", "떡"),
            ("noodle", "면"),
            ("veggie", "야채"),
        ]

        for store_id, _name in stores:
            # meta
            cur.execute(
                "INSERT INTO store_meta(store_id, usage_text, updated_at) VALUES(?, ?, ?)",
                (store_id, "▶ 카테고리 클릭 → 품목 추가/선택 → 저장\n\n예) 소스 → [추가] → 불닭소스 / 매운소스", now_iso())
            )
            # categories
            for idx, (k, label) in enumerate(default_categories):
                cur.execute(
                    "INSERT INTO categories(store_id, key, label, sort, updated_at) VALUES(?, ?, ?, ?, ?)",
                    (store_id, k, label, idx, now_iso())
                )
        conn.commit()

    conn.close()

init_db()

def fetch_stores() -> List[Dict[str, Any]]:
    conn = db()
    rows = conn.execute("SELECT id, name FROM stores ORDER BY name").fetchall()
    conn.close()
    return [{"id": r["id"], "name": r["name"]} for r in rows]

def fetch_meta(store_id: str) -> Dict[str, Any]:
    conn = db()
    meta = conn.execute(
        "SELECT usage_text, updated_at FROM store_meta WHERE store_id=?",
        (store_id,)
    ).fetchone()

    cats = conn.execute(
        "SELECT key, label, sort FROM categories WHERE store_id=? ORDER BY sort ASC, label ASC",
        (store_id,)
    ).fetchall()

    conn.close()
    if not meta:
        raise HTTPException(status_code=404, detail="Store not found")
    return {
        "store_id": store_id,
        "usage_text": meta["usage_text"],
        "updated_at": meta["updated_at"],
        "categories": [{"key": c["key"], "label": c["label"], "sort": c["sort"]} for c in cats]
    }

def upsert_meta(store_id: str, usage_text: str, categories: List[Dict[str, Any]]):
    conn = db()
    cur = conn.cursor()

    # store exists?
    s = cur.execute("SELECT id FROM stores WHERE id=?", (store_id,)).fetchone()
    if not s:
        conn.close()
        raise HTTPException(status_code=404, detail="Store not found")

    ts = now_iso()
    cur.execute("""
        INSERT INTO store_meta(store_id, usage_text, updated_at)
        VALUES(?, ?, ?)
        ON CONFLICT(store_id) DO UPDATE SET usage_text=excluded.usage_text, updated_at=excluded.updated_at
    """, (store_id, usage_text, ts))

    # replace categories
    cur.execute("DELETE FROM categories WHERE store_id=?", (store_id,))
    for c in categories:
        key = (c.get("key") or "").strip()
        label = (c.get("label") or "").strip()
        sort = int(c.get("sort") or 0)
        if not key or not label:
            continue
        cur.execute(
            "INSERT INTO categories(store_id, key, label, sort, updated_at) VALUES(?, ?, ?, ?, ?)",
            (store_id, key, label, sort, ts)
        )

    conn.commit()
    conn.close()

def ensure_store(store_id: str):
    conn = db()
    r = conn.execute("SELECT id FROM stores WHERE id=?", (store_id,)).fetchone()
    conn.close()
    if not r:
        raise HTTPException(status_code=404, detail="Store not found")

@app.get("/")
def root():
    return {"ok": True, "service": SERVICE, "version": VERSION}

@app.get("/health")
def health():
    return {"ok": True, "service": SERVICE, "version": VERSION}

@app.get("/api/stores")
def api_stores():
    return {"ok": True, "stores": fetch_stores()}

@app.get("/api/stores/{store_id}/meta")
def api_store_meta(store_id: str):
    return {"ok": True, "meta": fetch_meta(store_id)}

@app.put("/api/stores/{store_id}/meta")
def api_store_meta_update(
    store_id: str,
    payload: Dict[str, Any],
    x_admin_token: Optional[str] = Header(default=None)
):
    # ✅ 관리자만 가능
    require_admin(x_admin_token)
    usage_text = payload.get("usage_text") or ""
    categories = payload.get("categories") or []
    if not isinstance(categories, list):
        raise HTTPException(status_code=400, detail="categories must be list")
    upsert_meta(store_id, usage_text, categories)
    return {"ok": True, "updated_at": now_iso()}

# -------------------------
# Items (비로그인도 사용 가능)
# -------------------------
@app.get("/api/stores/{store_id}/items/{category}")
def list_items(store_id: str, category: str):
    ensure_store(store_id)
    conn = db()
    rows = conn.execute("""
        SELECT id, name, real_stock, price, vendor, storage, origin, updated_at
        FROM items
        WHERE store_id=? AND category=?
        ORDER BY name ASC
    """, (store_id, category)).fetchall()
    conn.close()

    return {
        "ok": True,
        "store_id": store_id,
        "category": category,
        "items": [dict(r) for r in rows]
    }

@app.post("/api/stores/{store_id}/items/{category}")
def create_item(store_id: str, category: str, payload: Dict[str, Any]):
    ensure_store(store_id)
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name required")

    item_id = f"{store_id}_{category}_{abs(hash(name))}"
    ts = now_iso()

    def g(k): return (payload.get(k) or "").strip()

    conn = db()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO items(id, store_id, category, name, real_stock, price, vendor, storage, origin, updated_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            item_id, store_id, category, name,
            g("real_stock"), g("price"), g("vendor"), g("storage"), g("origin"),
            ts
        ))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=409, detail="Item already exists")
    conn.close()
    return {"ok": True, "id": item_id, "updated_at": ts}

@app.put("/api/stores/{store_id}/items/{category}/{item_id}")
def update_item(store_id: str, category: str, item_id: str, payload: Dict[str, Any]):
    ensure_store(store_id)

    def g(k): return (payload.get(k) or "").strip()
    ts = now_iso()

    conn = db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE items
        SET real_stock=?, price=?, vendor=?, storage=?, origin=?, updated_at=?
        WHERE id=? AND store_id=? AND category=?
    """, (
        g("real_stock"), g("price"), g("vendor"), g("storage"), g("origin"),
        ts,
        item_id, store_id, category
    ))
    if cur.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Not Found")
    conn.commit()
    conn.close()
    return {"ok": True, "updated_at": ts}

@app.delete("/api/stores/{store_id}/items/{category}/{item_id}")
def delete_item(store_id: str, category: str, item_id: str):
    ensure_store(store_id)
    conn = db()
    cur = conn.cursor()
    cur.execute("DELETE FROM items WHERE id=? AND store_id=? AND category=?", (item_id, store_id, category))
    if cur.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Not Found")
    conn.commit()
    conn.close()
    return {"ok": True}
