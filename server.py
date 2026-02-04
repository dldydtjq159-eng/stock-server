from fastapi import FastAPI
from pydantic import BaseModel
import os, json, datetime

APP_VERSION = "6.0"
SERVICE = "stock-server"

BASE_DIR = "/data"
os.makedirs(BASE_DIR, exist_ok=True)

app = FastAPI(title=SERVICE, version=APP_VERSION)

# ===========================
# 기본 엔드포인트 (핵심)
# ===========================

@app.get("/")
def root():
    return {
        "ok": True,
        "service": SERVICE,
        "hint": "use /ok, /version, or /api/shortages/{store}"
    }

@app.get("/ok")
def ok():
    return {"status": "running", "service": SERVICE}

@app.get("/version")
def version():
    return {"service": SERVICE, "version": APP_VERSION}

# ===========================
# 데이터 구조
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
# 부족목록 API (중요!)
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
# (선택) 테스트용 초기 데이터
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
