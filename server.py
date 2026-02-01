# server.py  (FINAL)

import os
import json
import uuid
from datetime import datetime
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "dldydtjq159")
DATA_DIR = "/data"
os.makedirs(DATA_DIR, exist_ok=True)

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def path(name):
    return os.path.join(DATA_DIR, name)

def load(name, default):
    p = path(name)
    if not os.path.exists(p):
        save(name, default)
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def save(name, data):
    with open(path(name), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

app = FastAPI(title="stock-server", version="4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_headers=["*"],
    allow_methods=["*"],
)

def auth(token):
    if token != ADMIN_TOKEN:
        raise HTTPException(401, "Unauthorized")

@app.get("/")
def root():
    return {"ok": True, "service": "stock-server", "version": "4.0"}

# -------------------------
# 매장
# -------------------------
@app.get("/api/stores")
def stores():
    return load("stores.json", [
        {"id": "store1", "name": "김경영 요리 연구소"},
        {"id": "store2", "name": "청년회관"}
    ])

# -------------------------
# 카테고리
# -------------------------
@app.get("/api/categories/{store}")
def categories(store: str):
    return load(f"{store}_categories.json", [
        {"id": "ing", "name": "식재료"},
        {"id": "recipe", "name": "레시피"}
    ])

@app.post("/api/categories/{store}")
def add_category(store: str, data: dict, x_admin_token: str | None = Header(None)):
    auth(x_admin_token)
    cats = load(f"{store}_categories.json", [])
    cats.append({"id": str(uuid.uuid4()), "name": data["name"]})
    save(f"{store}_categories.json", cats)
    return {"ok": True}

@app.delete("/api/categories/{store}/{cid}")
def del_category(store, cid, x_admin_token: str | None = Header(None)):
    auth(x_admin_token)
    cats = load(f"{store}_categories.json", [])
    cats = [c for c in cats if c["id"] != cid]
    save(f"{store}_categories.json", cats)

    items = load(f"{store}_items.json", [])
    items = [i for i in items if i["category"] != cid]
    save(f"{store}_items.json", items)
    return {"ok": True}

# -------------------------
# 품목
# -------------------------
@app.get("/api/items/{store}/{category}")
def items(store, category):
    data = load(f"{store}_items.json", [])
    return [i for i in data if i["category"] == category]

@app.post("/api/items/{store}")
def add_item(store, data: dict, x_admin_token: str | None = Header(None)):
    auth(x_admin_token)
    items = load(f"{store}_items.json", [])
    data["id"] = str(uuid.uuid4())
    data["updated"] = now()
    items.append(data)
    save(f"{store}_items.json", items)
    return data

@app.put("/api/items/{store}/{iid}")
def update_item(store, iid, data: dict):
    items = load(f"{store}_items.json", [])
    for i in items:
        if i["id"] == iid:
            i.update(data)
            i["updated"] = now()
    save(f"{store}_items.json", items)
    return {"ok": True}

# -------------------------
# 부족 목록
# -------------------------
@app.get("/api/shortage/{store}")
def shortage(store):
    items = load(f"{store}_items.json", [])
    out = []
    for i in items:
        cur = float(i.get("current", 0))
        minq = float(i.get("min", 0))
        if cur < minq:
            out.append({
                "category": i.get("category_name", ""),
                "name": i["name"],
                "current": cur,
                "need": minq - cur,
                "price": i.get("price", ""),
                "link": i.get("link", "")
            })
    return out
