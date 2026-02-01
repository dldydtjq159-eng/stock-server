


import os
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

SERVICE = "stock-server"
VERSION = "2.0"

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "dldydtjq159")  # Railway Variables로 덮어쓰기 추천

app = FastAPI(title=SERVICE)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 필요하면 나중에 도메인만 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def require_admin(x_admin_token: str | None):
    if not x_admin_token or x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

@app.get("/")
def root():
    return {"ok": True, "service": SERVICE, "version": VERSION}

@app.get("/health")
def health():
    return {"ok": True, "service": SERVICE, "version": VERSION}

# 예시: 보호된 API (여기부터는 토큰 필요)
@app.get("/api/items/{category}")
def list_items(category: str, x_admin_token: str | None = Header(default=None)):
    require_admin(x_admin_token)
    # TODO: 여기에 DB/파일에서 category 목록 읽어오기
    return {"ok": True, "category": category, "items": []}

@app.post("/api/items/{category}")
def add_item(category: str, payload: dict, x_admin_token: str | None = Header(default=None)):
    require_admin(x_admin_token)
    # TODO: payload로 item 추가 로직
    return {"ok": True, "category": category, "added": payload}
