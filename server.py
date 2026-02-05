from fastapi import FastAPI
from pydantic import BaseModel
import os, json, datetime
from fastapi.middleware.cors import CORSMiddleware

APP_VERSION = "6.0"
SERVICE = "stock-server"

BASE_DIR = "/data"
os.makedirs(BASE_DIR, exist_ok=True)

app = FastAPI(title=SERVICE, version=APP_VERSION)

# ✅ CORS (PC 앱에서 호출 가능하게)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # 필요하면 특정 도메인만 허용 가능
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===========================
# 기본 엔드포인트 (핵심)
# ===========================

@app.get("/")
def root():
    return {
        "ok": True,
        "service": SERVICE,
        "hint": "use /ok, /version, /api/shortages/{store}, /storeapp/v1/data"
    }

@app.get("/ok")
def ok():
    return {"status": "running", "service": SERVICE}

@app.get("/version")
def version():
    return {"service": SERVICE, "version": APP_VERSION}

# ===========================
# (기존) 재고/부족목록 데이터 구조
# ===========================

def store_file(store: str):
    return os.path.join(BASE_DIR, f"{store}_stock.json")

def load_store(store: str):
    path = store_file(store)
    if not os.path.exists(path):
        return {"재료": [], "발주": []}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_store(store: str, data: dict):
    with open(store_file(store), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ===========================
# (기존) 부족목록 API (중요!)
# ===========================

@app.get("/api/shortages/{store}")
def get_shortages(store: str):
    data = load_store(store)
    shortages = []

    for cat in ["재료", "발주"]:
        for item in data.get(cat, []):
            try:
                cur = float(item.get("현재고", 0) or 0)
                minq = float(item.get("최소보유량", 0) or 0)
                if cur < minq:
                    shortages.append({
                        "category": cat,
                        "name": item.get("name", ""),
                        "current": cur,
                        "lack": max(0, minq - cur),
                        "vendor": item.get("구매처", ""),
                        "origin": item.get("원산지", "")
                    })
            except:
                pass

    return {"store": store, "shortages": shortages}

# ===========================
# (기존) 테스트용 초기 데이터
# ===========================

@app.post("/init/{store}")
def init_store(store: str):
    sample = {
        "재료": [
            {"name":"닭", "현재고":"8", "최소보유량":"10", "원산지":"국내산", "구매처":"정육점", "메모":""},
            {"name":"불닭소스", "현재고":"2", "최소보유량":"5", "원산지":"한국", "구매처":"도매", "메모":""}
        ],
        "발주": []
    }
    save_store(store, sample)
    return {"ok": True, "store": store, "message": "초기 데이터 생성됨"}

# =========================================================
# ✅ (추가) StoreApp 동기화 API: /storeapp/v1/data, /save
#    - 기존 데이터와 분리 저장: /data/storeapp_db.json
# =========================================================

STOREAPP_DB = os.path.join(BASE_DIR, "storeapp_db.json")

def now_iso():
    return datetime.datetime.utcnow().isoformat() + "Z"

def default_storeapp_data():
    return {
        "stores": ["김경영 요리 연구소", "청년회관"],
        "byStore": {
            "김경영 요리 연구소": {
                "inventory": {"닭": [], "떡": [], "소스": [], "포장재": []},
                "recipes": {"치킨": {}, "떡볶이": {}, "파스타": {}, "사이드": {}},
                "costing": {},
                "notes": {}
            },
            "청년회관": {
                "inventory": {"닭": [], "떡": [], "소스": [], "포장재": []},
                "recipes": {"치킨": {}, "떡볶이": {}, "파스타": {}, "사이드": {}},
                "costing": {},
                "notes": {}
            }
        },
        "lastSync": now_iso()
    }

def read_storeapp_db():
    if not os.path.exists(STOREAPP_DB):
        data = default_storeapp_data()
        write_storeapp_db(data)
        return data
    with open(STOREAPP_DB, "r", encoding="utf-8") as f:
        return json.load(f)

def write_storeapp_db(data: dict):
    data["lastSync"] = now_iso()
    with open(STOREAPP_DB, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

class StoreAppSaveBody(BaseModel):
    data: dict

@app.get("/storeapp/v1/data")
def storeapp_get_data():
    return read_storeapp_db()

@app.post("/storeapp/v1/save")
def storeapp_save_data(body: StoreAppSaveBody):
    # PC에서 전체 데이터를 body.data로 보내는 방식
    new_data = body.data
    if not isinstance(new_data, dict):
        return {"status": "error", "message": "invalid body"}
    write_storeapp_db(new_data)
    return {"status": "ok", "syncedAt": new_data.get("lastSync")}
