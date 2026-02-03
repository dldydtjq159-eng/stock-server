import os
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

APP_VERSION = "6.0"
SERVICE = "stock-server"

# Railway 환경변수(없어도 서버는 뜨게 기본값 세팅)
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "dldydtj159")
DATA_DIR = os.getenv("DATA_DIR", "/data")
APP_EMAIL = os.getenv("APP_EMAIL", "dldydtj159@naver.com")
APP_PASSWORD = os.getenv("APP_PASSWORD", "")

app = FastAPI(title=SERVICE, version=APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# 🔥 필수 엔드포인트 세트 (이거 없으면 너 PC앱 다 터짐)
# =========================

@app.get("/")
def root():
    return {
        "ok": True,
        "service": SERVICE,
        "hint": "use /ok/version or /version"
    }

@app.get("/ok/version")
def ok_version():
    return {"version": APP_VERSION}

@app.get("/version")
def version():
    return {
        "service": SERVICE,
        "version": APP_VERSION,
        "status": "running",
        "time": datetime.utcnow().isoformat()
    }

# =========================
# 예시용 기본 API (테스트용)
# =========================

@app.get("/api/ping")
def ping():
    return {"pong": True}

@app.get("/api/health")
def health():
    return {"status": "healthy"}

# =========================
# PC 프로그램에서 요청하는 기본 엔드포인트 더미
# (404 방지용 최소 세트)
# =========================

@app.get("/api/stores")
def stores():
    return {"stores": []}

@app.get("/api/items")
def items():
    return {"items": []}
