import os, json, time, uuid
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

SERVICE = "stock-server"
VERSION = "2.1"

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "dldydtjq159")

# Railway Volume을 /data 로 마운트해두면 영구저장 됨
DATA_FILE = os.getenv("DATA_FILE", "/data/items.json")

app = FastAPI(title=SERVICE)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def require_admin(x_admin_token: str | None):
    if not x_admin_token or x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

def _ensure_dir():
    d = os.path.dirname(DATA_FILE)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)

def load_data() -> Dict[str, List[Dict[str, Any]]]:
    _ensure_dir()
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data: Dict[str, List[Dict[str, Any]]]):
    _ensure_dir()
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DATA_FILE)

@app.get("/")
def root():
    return {"ok": True, "service": SERVICE, "version": VERSION}

@app.get("/health")
def health():
    return {"ok": True, "service": SERVICE, "version": VERSION}

@app.get("/api/items/{category}")
def list_items(category: str, x_admin_token: str | None = Header(default=None)):
    require_admin(x_admin_token)
    data = load_data()
    return {"ok": True, "category": category, "items": data.get(category, [])}

@app.post("/api/items/{category}")
def add_item(category: str, payload: Dict[str, Any], x_admin_token: str | None = Header(default=None)):
    require_admin(x_admin_token)
    data = load_data()
    items = data.get(category, [])

    item = {
        "id": payload.get("id") or uuid.uuid4().hex[:8],
        "name": (payload.get("name") or "").strip(),
        "unit": (payload.get("unit") or "").strip(),
        "qty": payload.get("qty", 0),
        "note": (payload.get("note") or "").strip(),
        "updated_at": int(time.time()),
    }
    if not item["name"]:
        raise HTTPException(status_code=400, detail="name is required")

    items.append(item)
    data[category] = items
    save_data(data)
    return {"ok": True, "item": item}

@app.put("/api/items/{category}/{item_id}")
def update_item(category: str, item_id: str, payload: Dict[str, Any], x_admin_token: str | None = Header(default=None)):
    require_admin(x_admin_token)
    data = load_data()
    items = data.get(category, [])
    for it in items:
        if it.get("id") == item_id:
            for k in ["name", "unit", "qty", "note"]:
                if k in payload:
                    it[k] = payload[k]
            it["updated_at"] = int(time.time())
            save_data(data)
            return {"ok": True, "item": it}
    raise HTTPException(status_code=404, detail="item not found")

@app.delete("/api/items/{category}/{item_id}")
def delete_item(category: str, item_id: str, x_admin_token: str | None = Header(default=None)):
    require_admin(x_admin_token)
    data = load_data()
    items = data.get(category, [])
    new_items = [it for it in items if it.get("id") != item_id]
    data[category] = new_items
    save_data(data)
    return {"ok": True, "deleted": item_id}
