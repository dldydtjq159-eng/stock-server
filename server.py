import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

APP_VERSION = "6.0"
SERVICE = "stock-server"

app = FastAPI(title=SERVICE, version=APP_VERSION)

# ✅ CORS 허용 (PC 프로그램 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ 1) 기본 접속 테스트용
@app.get("/")
def root():
    return {
        "ok": True,
        "service": SERVICE,
        "version": APP_VERSION,
        "hint": "use /ok/version or /api/stores"
    }

# ✅ 2) Railway 상태 확인용
@app.get("/ok/version")
def version():
    return {
        "service": SERVICE,
        "version": APP_VERSION,
        "status": "running"
    }

# ✅ 3) PC 프로그램이 실제로 쓰는 API (이게 핵심)
@app.get("/api/stores")
def get_stores():
    return {
        "stores": [
            {"id": 1, "name": "테스트 가게"},
            {"id": 2, "name": "치킨집"},
            {"id": 3, "name": "파스타 가게"}
        ]
    }
