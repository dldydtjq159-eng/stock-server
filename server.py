import os
import sqlite3
from fastapi import FastAPI, Header, HTTPException

# =========================
# 기본 설정
# =========================
SERVICE_NAME = "stock-server"
VERSION = "4.0"

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "dldydtjq159")
DATA_DIR = os.getenv("DATA_DIR", "/data")
DB_PATH = os.path.join(DATA_DIR, "stock.db")

app = FastAPI(title=SERVICE_NAME)

# =========================
# DB 초기화
# =========================
def get_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()

    # 매장
    cur.execute("""
    CREATE TABLE IF NOT EXISTS stores (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL
    )
    """)

    # 카테고리/사용문구 메타
    cur.execute("""
    CREATE TABLE IF NOT EXISTS store_meta (
        store_id TEXT PRIMARY KEY,
        usage_text TEXT,
        categories TEXT
    )
    """)

    # 품목
    cur.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_id TEXT,
        category TEXT,
        name TEXT,
        real_stock TEXT,
        price TEXT,
        vendor TEXT,
        storage TEXT,
        origin TEXT,
        updated_at TEXT
    )
    """)

    # 기본 매장 2개 (중복 방지)
    cur.execute("INSERT OR IGNORE INTO stores VALUES ('lab','김경영 요리 연구소')")
    cur.execute("INSERT OR IGNORE INTO stores VALUES ('youth','청년회관')")

    # 기본 메타
    cur.execute("""
    INSERT OR IGNORE INTO store_meta VALUES (
        'lab',
        '카테고리 클릭 → 품목 추가/선택 → 저장',
        '[{"key":"seasoning","label":"조미료","sort":1},
          {"key":"oil","label":"식용유","sort":2},
          {"key":"rice","label":"떡","sort":3},
          {"key":"noodle","label":"면","sort":4},
          {"key":"veggie","label":"야채","sort":5}]'
    )
    """)
    cur.execute("""
    INSERT OR IGNORE INTO store_meta VALUES (
        'youth',
        '카테고리 클릭 → 품목 추가/선택 → 저장',
        '[{"key":"seasoning","label":"조미료","sort":1},
          {"key":"oil","label":"식용유","sort":2},
          {"key":"rice","label":"떡","sort":3},
          {"key":"noodle","label":"면","sort":4},
          {"key":"veggie","label":"야채","sort":5}]'
    )
    """)

    conn.commit()
    conn.close()

init_db()

# =========================
# 공통
# =========================
def admin_check(x_admin_token: str | None):
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

# =========================
# 기본 체크
# =========================
@app.get("/")
def root():
    return {"ok": True, "service": SERVICE_NAME, "version": VERSION}

# =========================
# 매장
# =========================
@app.get("/api/stores")
def stores():
    conn = get_db()
    rows = conn.execute("SELECT * FROM stores").fetchall()
    conn.close()
    return {"stores": [dict(r) for r in rows]}

# =========================
# 매장 메타
# =========================
@app.get("/api/stores/{store_id}/meta")
def store_meta(store_id: str):
    conn = get_db()
    row = conn.execute(
        "SELECT usage_text, categories FROM store_meta WHERE store_id=?",
        (store_id,)
    ).fetchone()
    conn.close()

    if not row:
        return {"meta": {"usage_text": "", "categories": []}}

    import json
    return {
        "meta": {
            "usage_text": row["usage_text"],
            "categories": json.loads(row["categories"])
        }
    }

@app.put("/api/stores/{store_id}/meta")
def update_meta(store_id: str, payload: dict, x_admin_token: str = Header(None)):
    admin_check(x_admin_token)

    import json
    conn = get_db()
    conn.execute("""
        UPDATE store_meta
        SET usage_text=?, categories=?
        WHERE store_id=?
    """, (
        payload.get("usage_text", ""),
        json.dumps(payload.get("categories", []), ensure_ascii=False),
        store_id
    ))
    conn.commit()
    conn.close()
    return {"ok": True}

# =========================
# 품목
# =========================
@app.get("/api/stores/{store_id}/items/{category}")
def items(store_id: str, category: str):
    conn = get_db()
    rows = conn.execute("""
        SELECT * FROM items
        WHERE store_id=? AND category=?
        ORDER BY name
    """, (store_id, category)).fetchall()
    conn.close()
    return {"items": [dict(r) for r in rows]}

@app.post("/api/stores/{store_id}/items/{category}")
def add_item(store_id: str, category: str, payload: dict):
    conn = get_db()
    conn.execute("""
        INSERT INTO items
        (store_id, category, name, real_stock, price, vendor, storage, origin, updated_at)
        VALUES (?,?,?,?,?,?,?,?,datetime('now'))
    """, (
        store_id,
        category,
        payload.get("name"),
        payload.get("real_stock",""),
        payload.get("price",""),
        payload.get("vendor",""),
        payload.get("storage",""),
        payload.get("origin","")
    ))
    conn.commit()
    conn.close()
    return {"ok": True}

@app.put("/api/stores/{store_id}/items/{category}/{item_id}")
def update_item(store_id: str, category: str, item_id: int, payload: dict):
    conn = get_db()
    conn.execute("""
        UPDATE items SET
        real_stock=?,
        price=?,
        vendor=?,
        storage=?,
        origin=?,
        updated_at=datetime('now')
        WHERE id=? AND store_id=? AND category=?
    """, (
        payload.get("real_stock",""),
        payload.get("price",""),
        payload.get("vendor",""),
        payload.get("storage",""),
        payload.get("origin",""),
        item_id,
        store_id,
        category
    ))
    conn.commit()
    conn.close()
    return {"ok": True}

@app.delete("/api/stores/{store_id}/items/{category}/{item_id}")
def delete_item(store_id: str, category: str, item_id: int):
    conn = get_db()
    conn.execute(
        "DELETE FROM items WHERE id=? AND store_id=? AND category=?",
        (item_id, store_id, category)
    )
    conn.commit()
    conn.close()
    return {"ok": True}
