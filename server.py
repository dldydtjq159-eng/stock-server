import os
import json
import time
from typing import Any, Dict, Optional, List

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from passlib.context import CryptContext
import jwt

# ============================================================
# ENV (Railway Variables에서 설정)
# ============================================================
TOKEN_SECRET = os.environ.get("TOKEN_SECRET", "change-me-please")  # 꼭 바꾸기
SUPERADMIN_ID = os.environ.get("SUPERADMIN_ID", "admin")           # Railway에서 세팅
SUPERADMIN_PW = os.environ.get("SUPERADMIN_PW", "adminpw")         # Railway에서 세팅

JWT_ALG = "HS256"
JWT_TTL_SEC = 60 * 60 * 12  # 12 hours

# ✅ bcrypt 이슈(파이썬3.12/버전 꼬임) 피하려고 pbkdf2_sha256로 고정
pwd_ctx = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# ============================================================
# Simple JSON storage
# ⚠ Railway 무료/기본 환경은 파일 저장이 "배포/재시작" 시 날아갈 수 있음(임시 저장소)
# ============================================================
DATA_FILE = os.environ.get("DATA_FILE", "data.json")
ADMINS_FILE = os.environ.get("ADMINS_FILE", "admins.json")


def _read_json(path: str, default: Any):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except:
        pass
    return default


def _write_json(path: str, obj: Any):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _ensure_files():
    if not os.path.exists(DATA_FILE):
        _write_json(DATA_FILE, {
            "stores": ["김경영 요리 연구소", "청년회관"],
            "byStore": {},
            "lastSync": ""
        })

    if not os.path.exists(ADMINS_FILE):
        _write_json(ADMINS_FILE, {
            "superadmin": {
                "id": SUPERADMIN_ID,
                "pw_hash": pwd_ctx.hash(SUPERADMIN_PW)
            },
            "admins": []
        })


_ensure_files()


def _load_data() -> Dict[str, Any]:
    return _read_json(DATA_FILE, {"stores": [], "byStore": {}, "lastSync": ""})


def _save_data(d: Dict[str, Any]):
    d["lastSync"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _write_json(DATA_FILE, d)


def _load_admins() -> Dict[str, Any]:
    return _read_json(ADMINS_FILE, {"superadmin": {"id": SUPERADMIN_ID, "pw_hash": pwd_ctx.hash(SUPERADMIN_PW)}, "admins": []})


def _save_admins(a: Dict[str, Any]):
    _write_json(ADMINS_FILE, a)


def _create_token(sub: str, role: str) -> str:
    now = int(time.time())
    payload = {
        "sub": sub,
        "role": role,
        "iat": now,
        "exp": now + JWT_TTL_SEC
    }
    return jwt.encode(payload, TOKEN_SECRET, algorithm=JWT_ALG)


def _decode_token(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(token, TOKEN_SECRET, algorithms=[JWT_ALG])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


def require_auth(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    token = authorization.split(" ", 1)[1].strip()
    return _decode_token(token)


def require_superadmin(user=Depends(require_auth)) -> Dict[str, Any]:
    if user.get("role") != "superadmin":
        raise HTTPException(status_code=403, detail="Superadmin only")
    return user


# ============================================================
# FastAPI
# ============================================================
app = FastAPI(
    title="stock-server + storeapp",
    version="6.1"
)

# CORS (PC앱/웹에서 호출 가능)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# Schemas
# ============================================================
class LoginReq(BaseModel):
    id: str
    pw: str


class LoginRes(BaseModel):
    token: str
    role: str
    id: str


class AdminCreateReq(BaseModel):
    id: str
    pw: str


class SaveAllReq(BaseModel):
    stores: List[str]
    byStore: Dict[str, Any]


class SaveStoreReq(BaseModel):
    data: Any


# ============================================================
# Basic health
# ============================================================
@app.get("/")
def root():
    return {"service": "stock-server", "status": "running"}


@app.get("/ok")
def ok():
    return {"ok": True}


@app.get("/version")
def version():
    return {"version": app.version}


# ============================================================
# storeapp API
# ============================================================
@app.get("/storeapp/v1/version")
def storeapp_version():
    return {"storeapp_version": app.version}


@app.post("/storeapp/v1/auth/login", response_model=LoginRes)
def login(body: LoginReq):
    admins = _load_admins()

    # superadmin
    sa = admins.get("superadmin", {})
    if body.id == sa.get("id") and pwd_ctx.verify(body.pw, sa.get("pw_hash", "")):
        token = _create_token(sub=body.id, role="superadmin")
        return {"token": token, "role": "superadmin", "id": body.id}

    # normal admins
    for a in admins.get("admins", []):
        if body.id == a.get("id") and pwd_ctx.verify(body.pw, a.get("pw_hash", "")):
            token = _create_token(sub=body.id, role="admin")
            return {"token": token, "role": "admin", "id": body.id}

    raise HTTPException(status_code=401, detail="Invalid id or password")


@app.get("/storeapp/v1/auth/me")
def me(user=Depends(require_auth)):
    return {"id": user.get("sub"), "role": user.get("role")}


@app.post("/storeapp/v1/auth/admins")
def create_admin(body: AdminCreateReq, _=Depends(require_superadmin)):
    admins = _load_admins()
    if body.id == admins.get("superadmin", {}).get("id"):
        raise HTTPException(status_code=400, detail="Cannot use superadmin id")

    for a in admins.get("admins", []):
        if a.get("id") == body.id:
            raise HTTPException(status_code=400, detail="Admin already exists")

    admins["admins"].append({
        "id": body.id,
        "pw_hash": pwd_ctx.hash(body.pw)
    })
    _save_admins(admins)
    return {"ok": True}


@app.get("/storeapp/v1/auth/admins")
def list_admins(_=Depends(require_superadmin)):
    admins = _load_admins()
    return {
        "superadmin": admins.get("superadmin", {}).get("id"),
        "admins": [a.get("id") for a in admins.get("admins", [])]
    }


@app.get("/storeapp/v1/data")
def get_all_data(user=Depends(require_auth)):
    # 로그인만 하면 데이터 조회 가능
    return _load_data()


@app.post("/storeapp/v1/save")
def save_all(body: SaveAllReq, user=Depends(require_auth)):
    d = _load_data()
    d["stores"] = body.stores
    d["byStore"] = body.byStore
    _save_data(d)
    return {"ok": True, "lastSync": d.get("lastSync", "")}


@app.get("/storeapp/v1/store/{store_name}")
def get_store(store_name: str, user=Depends(require_auth)):
    d = _load_data()
    return {
        "store": store_name,
        "data": d.get("byStore", {}).get(store_name, {})
    }


@app.post("/storeapp/v1/store/{store_name}")
def save_store(store_name: str, body: SaveStoreReq, user=Depends(require_auth)):
    d = _load_data()
    if "byStore" not in d:
        d["byStore"] = {}
    d["byStore"][store_name] = body.data
    if store_name not in d.get("stores", []):
        d.setdefault("stores", []).append(store_name)
    _save_data(d)
    return {"ok": True, "lastSync": d.get("lastSync", "")}
from fastapi import FastAPI

app = FastAPI()

# ===========================
# ✅ PC앱 업데이트 체크용 API
# ===========================

SERVER_VERSION = "1.0.1"   # ← 여기 바꾸면 업데이트 감지됨

@app.get("/storeapp/v1/version")
def get_version():
    return {
        "version": SERVER_VERSION,
        "message": "OK"
    }


