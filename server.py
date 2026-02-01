import os
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

SERVICE = "stock-server"
VERSION = "3.0"

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "dldydtjq159")  # Railway Variables 권장
DATA_DIR = os.getenv("DATA_DIR", "/data")
DB_PATH = os.path.join(DATA_DIR, "items_db.json")

app = FastAPI(title=SERVICE)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def require_admin(x_admin_token: str | None):
    if not x_admin_token or x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)

def load_db() -> Dict[str, List[Dict[str, Any]]]:
    ensure_data_dir()
    if not os.path.exists(DB_PATH):
        return {}
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}

def save_db(db: Dict[str, List[Dict[str, Any]]]):
    ensure_data_dir()
    tmp = DB_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DB_PATH)

def get_category_list(db, category: str) -> List[Dict[str, Any]]:
    return db.setdefault(category, [])

def find_item(items: List[Dict[str, Any]], item_id: str):
    for it in items:
        if it.get("id") == item_id:
            return it
    return None

@app.get("/")
def root():
    return {"ok": True, "service": SERVICE, "version": VERSION}

@app.get("/health")
def health():
    return {"ok": True, "service": SERVICE, "version": VERSION}

@app.get("/api/items/{category}")
def list_items(category: str, x_admin_token: str | None = Header(default=None)):
    require_admin(x_admin_token)
    db = load_db()
    items = get_category_list(db, category)
    # ✅ 여기서 "상세필드"까지 전부 내려줌 (PC 프로그램이 이걸로 채움)
    return {"ok": True, "category": category, "items": items}

@app.post("/api/items/{category}")
def create_item(category: str, payload: Dict[str, Any], x_admin_token: str | None = Header(default=None)):
    require_admin(x_admin_token)
    db = load_db()
    items = get_category_list(db, category)

    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    # 같은 이름 방지
    for it in items:
        if (it.get("name") or "").strip().lower() == name.lower():
            raise HTTPException(status_code=409, detail="duplicate name")

    new_item = {
        "id": uuid.uuid4().hex,
        "name": name,
        "real_stock": (payload.get("real_stock") or ""),
        "price": (payload.get("price") or ""),
        "vendor": (payload.get("vendor") or ""),
        "storage": (payload.get("storage") or ""),
        "origin": (payload.get("origin") or ""),
        "updated_at": now_iso(),
    }

    items.append(new_item)
    save_db(db)
    return {"ok": True, "item": new_item, "updated_at": new_item["updated_at"]}

@app.put("/api/items/{category}/{item_id}")
def update_item(category: str, item_id: str, payload: Dict[str, Any], x_admin_token: str | None = Header(default=None)):
    require_admin(x_admin_token)
    db = load_db()
    items = get_category_list(db, category)
    it = find_item(items, item_id)
    if not it:
        raise HTTPException(status_code=404, detail="Not Found")

    # 업데이트 가능한 필드들
    for k in ["real_stock", "price", "vendor", "storage", "origin", "name"]:
        if k in payload:
            it[k] = payload.get(k) or ""

    it["updated_at"] = now_iso()
    save_db(db)
    return {"ok": True, "item": it, "updated_at": it["updated_at"]}

@app.delete("/api/items/{category}/{item_id}")
def delete_item(category: str, item_id: str, x_admin_token: str | None = Header(default=None)):
    require_admin(x_admin_token)
    db = load_db()
    items = get_category_list(db, category)

    before = len(items)
    items[:] = [x for x in items if x.get("id") != item_id]
    if len(items) == before:
        raise HTTPException(status_code=404, detail="Not Found")

    save_db(db)
    return {"ok": True}
