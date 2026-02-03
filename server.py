# STOCK SERVER (FastAPI) - All-in-one minimal API for PC App
# - stores / meta / items CRUD / shortages
# - SQLite 저장: DATA_DIR(기본 /data) 아래 stock.db
# - (선택) 이메일 알림: /api/notify/{store_id} 호출 시 부족목록을 메일로 발송
#
# Railway 설정
# 1) Variables
#    ADMIN_TOKEN = dldydtjq159
#    DATA_DIR = /data
#    APP_EMAIL = dldydtjq159@naver.com
#    APP_PASSWORD = (네이버 앱비밀번호)   ← Railway Variables로만 넣기(코드에 하드코딩 X)
# 2) Volume
#    Mount path = /data
# 3) Start Command (Settings > Deploy)
#    uvicorn server:app --host 0.0.0.0 --port $PORT

import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import smtplib
from email.mime.text import MIMEText

APP_VERSION = "6.0"
SERVICE = "stock-server"

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "dldydtjq159").strip()
DATA_DIR = os.getenv("DATA_DIR", "/data").strip()
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "stock.db")

APP_EMAIL = os.getenv("APP_EMAIL", "dldydtjq159@naver.com").strip()
APP_PASSWORD = os.getenv("APP_PASSWORD", "").strip()  # 네이버 앱비밀번호

app = FastAPI(title=SERVICE, version=APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- DB ----------------
def db() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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
        categories_json TEXT DEFAULT '[]',
        updated_at TEXT,
        FOREIGN KEY(store_id) REFERENCES stores(id)
    )
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
        storage TEXT DEFAULT '',
        origin TEXT DEFAULT '',
        buy_link TEXT DEFAULT '',
        memo TEXT DEFAULT '',
        created_at TEXT,
        updated_at TEXT,
        UNIQUE(store_id, category_key, name),
        FOREIGN KEY(store_id) REFERENCES stores(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS order_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        payload_json TEXT NOT NULL
    )
    """)

    con.commit()

    # 기본 매장 2개
    cur.execute("INSERT OR IGNORE INTO stores(id, name) VALUES(?,?)", ("lab", "김경영요리 연구소"))
    cur.execute("INSERT OR IGNORE INTO stores(id, name) VALUES(?,?)", ("youth", "청년회관"))

    # 기본 메타(카테고리 2개)
    default_categories = [
        {"key": "ingredient", "label": "재료", "sort": 0},
        {"key": "order", "label": "발주", "sort": 10},
    ]
    for sid in ("lab", "youth"):
        cur.execute("""
            INSERT OR IGNORE INTO store_meta(store_id, usage_text, categories_json, updated_at)
            VALUES(?,?,?,?)
        """, (sid, "공지사항을 여기에 적어두세요.", json_dumps(default_categories), now_iso()))
    con.commit()
    con.close()

def json_loads(s: str):
    import json
    try:
        return json.loads(s)
    except Exception:
        return None

def json_dumps(obj) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False)

init_db()

# ---------------- Models ----------------
class Category(BaseModel):
    key: str
    label: str
    sort: int = 0

class StoreMeta(BaseModel):
    usage_text: str = ""
    categories: List[Category] = Field(default_factory=list)

class ItemIn(BaseModel):
    name: str
    current_stock: float = 0
    min_stock: float = 0
    unit: str = ""
    price: str = ""
    vendor: str = ""
    storage: str = ""
    origin: str = ""
    buy_link: str = ""
    memo: str = ""

# ---------------- Auth ----------------
def require_admin(x_admin_token: Optional[str]):
    if (x_admin_token or "").strip() != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

# ---------------- Health ----------------
@app.get("/ok")
def ok():
    return {"ok": True, "service": SERVICE, "version": APP_VERSION}

@app.get("/version")
def version():
    return {"version": APP_VERSION}

# ---------------- Stores ----------------
@app.get("/api/stores")
def list_stores():
    con = db()
    rows = con.execute("SELECT id, name FROM stores ORDER BY id").fetchall()
    con.close()
    return {"stores": [dict(r) for r in rows]}

@app.get("/api/stores/{store_id}/meta")
def get_meta(store_id: str):
    con = db()
    r = con.execute("SELECT usage_text, categories_json, updated_at FROM store_meta WHERE store_id=?", (store_id,)).fetchone()
    con.close()
    if not r:
        raise HTTPException(404, "store meta not found")
    cats = json_loads(r["categories_json"]) or []
    return {"meta": {"usage_text": r["usage_text"] or "", "categories": cats, "updated_at": r["updated_at"]}}

@app.put("/api/stores/{store_id}/meta")
def put_meta(store_id: str, payload: Dict[str, Any], x_admin_token: Optional[str] = Header(default=None)):
    require_admin(x_admin_token)

    usage_text = (payload.get("usage_text") or "").strip()
    categories = payload.get("categories") or []
    # 간단 검증
    norm = []
    for c in categories:
        key = (c.get("key") or "").strip()
        label = (c.get("label") or "").strip()
        sort = int(c.get("sort") or 0)
        if not key or not label:
            continue
        norm.append({"key": key, "label": label, "sort": sort})
    con = db()
    con.execute("""
        INSERT INTO store_meta(store_id, usage_text, categories_json, updated_at)
        VALUES(?,?,?,?)
        ON CONFLICT(store_id) DO UPDATE SET
            usage_text=excluded.usage_text,
            categories_json=excluded.categories_json,
            updated_at=excluded.updated_at
    """, (store_id, usage_text, json_dumps(norm), now_iso()))
    con.commit()
    con.close()
    return {"ok": True}

# ---------------- Items ----------------
@app.get("/api/stores/{store_id}/items/{category_key}")
def list_items(store_id: str, category_key: str):
    con = db()
    rows = con.execute("""
        SELECT * FROM items
        WHERE store_id=? AND category_key=?
        ORDER BY name COLLATE NOCASE
    """, (store_id, category_key)).fetchall()
    con.close()
    return {"items": [dict(r) for r in rows]}

@app.post("/api/stores/{store_id}/items/{category_key}")
def add_item(store_id: str, category_key: str, item: ItemIn):
    con = db()
    try:
        con.execute("""
            INSERT INTO items(store_id, category_key, name, current_stock, min_stock, unit, price, vendor, storage, origin, buy_link, memo, created_at, updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            store_id, category_key, item.name.strip(),
            float(item.current_stock or 0), float(item.min_stock or 0),
            item.unit or "", item.price or "", item.vendor or "", item.storage or "",
            item.origin or "", item.buy_link or "", item.memo or "",
            now_iso(), now_iso()
        ))
        con.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="duplicate item name")
    finally:
        con.close()
    return {"ok": True}

@app.put("/api/stores/{store_id}/items/{category_key}/{item_id}")
def update_item(store_id: str, category_key: str, item_id: int, payload: Dict[str, Any]):
    con = db()
    cur = con.cursor()
    r = cur.execute("SELECT id FROM items WHERE id=? AND store_id=? AND category_key=?", (item_id, store_id, category_key)).fetchone()
    if not r:
        con.close()
        raise HTTPException(404, "item not found")

    # 허용 필드만 업데이트
    allowed = {"current_stock","min_stock","unit","price","vendor","storage","origin","buy_link","memo","name"}
    sets = []
    vals = []
    for k, v in payload.items():
        if k not in allowed:
            continue
        if k in ("current_stock","min_stock"):
            try:
                v = float(v)
            except Exception:
                v = 0.0
        if v is None:
            v = ""
        sets.append(f"{k}=?")
        vals.append(v)
    if not sets:
        con.close()
        return {"ok": True, "updated_at": now_iso()}

    sets.append("updated_at=?")
    vals.append(now_iso())
    vals.extend([item_id])

    cur.execute(f"UPDATE items SET {', '.join(sets)} WHERE id=?", vals)
    con.commit()
    updated_at = cur.execute("SELECT updated_at FROM items WHERE id=?", (item_id,)).fetchone()["updated_at"]
    con.close()
    return {"ok": True, "updated_at": updated_at}

@app.delete("/api/stores/{store_id}/items/{category_key}/{item_id}")
def delete_item(store_id: str, category_key: str, item_id: int):
    con = db()
    con.execute("DELETE FROM items WHERE id=? AND store_id=? AND category_key=?", (item_id, store_id, category_key))
    con.commit()
    con.close()
    return {"ok": True}

# ---------------- Shortages ----------------
@app.get("/api/shortages/{store_id}")
def shortages(store_id: str):
    con = db()
    # 카테고리 라벨 매핑
    meta = con.execute("SELECT categories_json FROM store_meta WHERE store_id=?", (store_id,)).fetchone()
    cat_map = {}
    if meta:
        cats = json_loads(meta["categories_json"]) or []
        for c in cats:
            cat_map[c.get("key")] = c.get("label")
    rows = con.execute("""
        SELECT * FROM items
        WHERE store_id=? AND current_stock < min_stock
        ORDER BY category_key, name
    """, (store_id,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["need"] = max(0.0, float(d.get("min_stock") or 0) - float(d.get("current_stock") or 0))
        d["category_label"] = cat_map.get(d["category_key"], d["category_key"])
        out.append(d)
    con.close()
    return {"shortages": out}

# ---------------- Email notify (optional) ----------------
def send_email(subject: str, body: str, to_email: str):
    if not APP_EMAIL or not APP_PASSWORD:
        raise RuntimeError("APP_EMAIL 또는 APP_PASSWORD가 설정되지 않았습니다. Railway Variables에 설정하세요.")
    # 네이버 SMTP
    smtp_host = "smtp.naver.com"
    smtp_port = 465

    msg = MIMEText(body, _charset="utf-8")
    msg["Subject"] = subject
    msg["From"] = APP_EMAIL
    msg["To"] = to_email

    with smtplib.SMTP_SSL(smtp_host, smtp_port) as smtp:
        smtp.login(APP_EMAIL, APP_PASSWORD)
        smtp.sendmail(APP_EMAIL, [to_email], msg.as_string())

@app.post("/api/notify/{store_id}")
def notify_shortage(store_id: str, to_email: Optional[str] = None):
    to_email = (to_email or APP_EMAIL).strip()
    data = shortages(store_id)["shortages"]
    if not data:
        return {"ok": True, "sent": False, "reason": "no shortages"}

    lines = []
    lines.append(f"[부족 알림] {store_id}  ({now_iso()})")
    lines.append("")
    lines.append("카테고리 | 품목 | 현재고 | 최소 | 부족 | 구매처 | 원산지")
    lines.append("-"*80)
    for r in data:
        unit = r.get("unit") or ""
        cur = f"{r.get('current_stock',0)} {unit}".strip()
        mn = f"{r.get('min_stock',0)} {unit}".strip()
        need = f"{r.get('need',0)} {unit}".strip()
        lines.append(f"{r.get('category_label','')} | {r.get('name','')} | {cur} | {mn} | {need} | {r.get('vendor','')} | {r.get('origin','')}")
    body = "\n".join(lines)

    send_email(subject="재고 부족 알림", body=body, to_email=to_email)
    return {"ok": True, "sent": True, "count": len(data)}

# ---------------- Order history (optional) ----------------
@app.post("/api/order_history/{store_id}")
def add_order_history(store_id: str, payload: Dict[str, Any]):
    import json
    con = db()
    con.execute("INSERT INTO order_history(store_id, created_at, payload_json) VALUES(?,?,?)",
                (store_id, now_iso(), json.dumps(payload, ensure_ascii=False)))
    con.commit()
    con.close()
    return {"ok": True}

@app.get("/api/order_history/{store_id}")
def list_order_history(store_id: str, limit: int = 50):
    con = db()
    rows = con.execute("SELECT id, created_at, payload_json FROM order_history WHERE store_id=? ORDER BY id DESC LIMIT ?",
                       (store_id, int(limit))).fetchall()
    con.close()
    out = []
    for r in rows:
        out.append({"id": r["id"], "created_at": r["created_at"], "payload": json_loads(r["payload_json"])})
    return {"history": out}

@app.get("/ok/version")
def ok_version():
    return {
        "service": "stock-server",
        "version": "5.0",
        "status": "running",
        "time": datetime.now().isoformat()
    }
