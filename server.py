import os, json, uuid, time
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

SERVICE = "stock-server"
VERSION = "4.1"

DATA_DIR = os.getenv("DATA_DIR", "/data")
os.makedirs(DATA_DIR, exist_ok=True)

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "dldydtjq159")

def p(name: str) -> str:
    return os.path.join(DATA_DIR, name)

def load(name: str, default):
    fp = p(name)
    if not os.path.exists(fp):
        save(name, default)
        return default
    with open(fp, "r", encoding="utf-8") as f:
        return json.load(f)

def save(name: str, data):
    with open(p(name), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def now():
    return time.strftime("%Y-%m-%d %H:%M:%S")

def require_admin(x_admin_token: str | None):
    if not x_admin_token or x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

app = FastAPI(title=SERVICE, version=VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_headers=["*"],
    allow_methods=["*"],
)

# -------------------------
# 기본/헬스
# -------------------------
@app.get("/")
def root():
    return {"ok": True, "service": SERVICE, "version": VERSION}

@app.get("/health")
def health():
    return {"ok": True, "service": SERVICE, "version": VERSION}

# -------------------------
# Stores (고정 2개)
# -------------------------
DEFAULT_STORES = [
    {"id": "store1", "name": "김경영 요리 연구소"},
    {"id": "store2", "name": "청년회관"},
]

@app.get("/api/stores")
def get_stores():
    # stores.json이 없으면 자동 생성
    return load("stores.json", DEFAULT_STORES)

# -------------------------
# Categories (매장별)
# -------------------------
# 구조: categories.json = { store_id: [ {id,name,order}, ... ] }
@app.get("/api/categories/{store_id}")
def get_categories(store_id: str):
    data = load("categories.json", {})
    cats = data.get(store_id, [])
    cats.sort(key=lambda x: x.get("order", 0))
    return {"ok": True, "store_id": store_id, "categories": cats}

@app.post("/api/categories/{store_id}")
def add_category(store_id: str, body: dict, x_admin_token: str | None = Header(default=None)):
    require_admin(x_admin_token)
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(400, detail="name required")

    data = load("categories.json", {})
    data.setdefault(store_id, [])
    # 중복 방지
    if any(c["name"] == name for c in data[store_id]):
        raise HTTPException(409, detail="category already exists")

    new_cat = {
        "id": str(uuid.uuid4()),
        "name": name,
        "order": (max([c.get("order", 0) for c in data[store_id]] + [-1]) + 1),
        "updated_at": now(),
    }
    data[store_id].append(new_cat)
    save("categories.json", data)
    return {"ok": True, "category": new_cat}

@app.put("/api/categories/{store_id}/{cat_id}")
def rename_category(store_id: str, cat_id: str, body: dict, x_admin_token: str | None = Header(default=None)):
    require_admin(x_admin_token)
    new_name = (body.get("name") or "").strip()
    if not new_name:
        raise HTTPException(400, detail="name required")

    data = load("categories.json", {})
    cats = data.get(store_id, [])
    # 이름 중복 방지
    if any(c["name"] == new_name and c["id"] != cat_id for c in cats):
        raise HTTPException(409, detail="category name duplicated")

    for c in cats:
        if c["id"] == cat_id:
            old_name = c["name"]
            c["name"] = new_name
            c["updated_at"] = now()
            save("categories.json", data)

            # 카테고리 이름을 키로 쓰고 있어서 items.json에서도 같이 이름 바꿔줌
            items = load("items.json", {})
            old_key_prefix = f"{store_id}:{old_name}"
            new_key_prefix = f"{store_id}:{new_name}"
            if old_key_prefix in items:
                items[new_key_prefix] = items.pop(old_key_prefix)
                save("items.json", items)

            return {"ok": True, "category": c}

    raise HTTPException(404, detail="category not found")

@app.post("/api/categories/{store_id}/{cat_id}/move")
def move_category(store_id: str, cat_id: str, body: dict, x_admin_token: str | None = Header(default=None)):
    require_admin(x_admin_token)
    direction = body.get("direction")  # "up" or "down"

    data = load("categories.json", {})
    cats = data.get(store_id, [])
    cats.sort(key=lambda x: x.get("order", 0))

    idx = next((i for i,c in enumerate(cats) if c["id"] == cat_id), None)
    if idx is None:
        raise HTTPException(404, detail="category not found")

    if direction == "up" and idx > 0:
        cats[idx]["order"], cats[idx-1]["order"] = cats[idx-1]["order"], cats[idx]["order"]
    elif direction == "down" and idx < len(cats)-1:
        cats[idx]["order"], cats[idx+1]["order"] = cats[idx+1]["order"], cats[idx]["order"]
    else:
        return {"ok": True, "categories": cats}

    # 저장
    data[store_id] = cats
    save("categories.json", data)
    return {"ok": True, "categories": cats}

@app.delete("/api/categories/{store_id}/{cat_id}")
def delete_category(store_id: str, cat_id: str, x_admin_token: str | None = Header(default=None)):
    require_admin(x_admin_token)

    data = load("categories.json", {})
    cats = data.get(store_id, [])
    target = next((c for c in cats if c["id"] == cat_id), None)
    if not target:
        raise HTTPException(404, detail="category not found")

    # items도 같이 삭제(서버에서 실제 삭제)
    items = load("items.json", {})
    key = f"{store_id}:{target['name']}"
    if key in items:
        items.pop(key, None)
        save("items.json", items)

    data[store_id] = [c for c in cats if c["id"] != cat_id]
    save("categories.json", data)
    return {"ok": True}

# -------------------------
# Items (식재료)
# -------------------------
# items.json 구조: { "store_id:category_name": [ {id,name,current,min_qty,unit,price,vendor,storage,origin,buy_url,memo,updated_at}, ... ] }
@app.get("/api/items/{store_id}/{category_name}")
def list_items(store_id: str, category_name: str):
    items = load("items.json", {})
    key = f"{store_id}:{category_name}"
    return {"ok": True, "store_id": store_id, "category": category_name, "items": items.get(key, [])}

@app.post("/api/items/{store_id}/{category_name}")
def add_item(store_id: str, category_name: str, body: dict):
    items = load("items.json", {})
    key = f"{store_id}:{category_name}"
    items.setdefault(key, [])

    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(400, detail="name required")
    if any(x["name"] == name for x in items[key]):
        raise HTTPException(409, detail="item exists")

    it = {
        "id": str(uuid.uuid4()),
        "name": name,
        "current": body.get("current", ""),
        "min_qty": body.get("min_qty", ""),
        "unit": body.get("unit", ""),
        "price": body.get("price", ""),
        "vendor": body.get("vendor", ""),
        "storage": body.get("storage", ""),
        "origin": body.get("origin", ""),
        "buy_url": body.get("buy_url", ""),
        "memo": body.get("memo", ""),
        "updated_at": now(),
    }
    items[key].append(it)
    save("items.json", items)
    return {"ok": True, "item": it}

@app.put("/api/items/{store_id}/{category_name}/{item_id}")
def update_item(store_id: str, category_name: str, item_id: str, body: dict):
    items = load("items.json", {})
    key = f"{store_id}:{category_name}"
    arr = items.get(key, [])
    for it in arr:
        if it["id"] == item_id:
            for k in ["current","min_qty","unit","price","vendor","storage","origin","buy_url","memo","name"]:
                if k in body:
                    it[k] = body[k]
            it["updated_at"] = now()
            save("items.json", items)
            return {"ok": True, "item": it}
    raise HTTPException(404, detail="item not found")

@app.delete("/api/items/{store_id}/{category_name}/{item_id}")
def delete_item(store_id: str, category_name: str, item_id: str):
    items = load("items.json", {})
    key = f"{store_id}:{category_name}"
    arr = items.get(key, [])
    new_arr = [x for x in arr if x["id"] != item_id]
    if len(new_arr) == len(arr):
        raise HTTPException(404, detail="item not found")
    items[key] = new_arr
    save("items.json", items)
    return {"ok": True}

# -------------------------
# Shortages (부족목록)
# -------------------------
@app.get("/api/shortages/{store_id}")
def shortages(store_id: str):
    cats = load("categories.json", {}).get(store_id, [])
    cats.sort(key=lambda x: x.get("order", 0))
    items_data = load("items.json", {})

    result = []
    for c in cats:
        key = f"{store_id}:{c['name']}"
        for it in items_data.get(key, []):
            try:
                cur = float(str(it.get("current","")).strip() or 0)
                mn = float(str(it.get("min_qty","")).strip() or 0)
            except:
                continue
            if cur < mn:
                result.append({
                    "category": c["name"],
                    "name": it["name"],
                    "current": it.get("current",""),
                    "min_qty": it.get("min_qty",""),
                    "need": (mn - cur),
                    "unit": it.get("unit",""),
                    "price": it.get("price",""),
                    "buy_url": it.get("buy_url",""),
                })
    return {"ok": True, "store_id": store_id, "shortages": result}
