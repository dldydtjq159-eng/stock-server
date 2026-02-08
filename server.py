import os, json, time
from fastapi import FastAPI, HTTPException, Header, Body
from pydantic import BaseModel
from passlib.context import CryptContext
import jwt

app = FastAPI()
pwd = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

SUPER_ID = os.environ.get("SUPERADMIN_ID", "dldydtjq159")
SUPER_PW = os.environ.get("SUPERADMIN_PW", "tkfkd4026")
SECRET = os.environ.get("TOKEN_SECRET", "change-me")

ADMINS_FILE = "admins.json"
DATA_FILE = "data.json"

def _load(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def _save(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

# ======= 초기 데이터 보장 =======
admins = _load(
    ADMINS_FILE,
    {"superadmin": {"id": SUPER_ID, "pw_hash": pwd.hash(SUPER_PW)}, "admins": []}
)

data = _load(
    DATA_FILE,
    {
        "stores": ["김경영 요리 연구소", "청년회관"],
        "byStore": {},
        "lastSync": ""
    }
)

_save(ADMINS_FILE, admins)
_save(DATA_FILE, data)

# ======= DTO =======
class LoginReq(BaseModel):
    id: str
    pw: str

class AdminAddReq(BaseModel):
    id: str
    pw: str
    name: str | None = None

# =========================
# 1️⃣ 버전 API (업데이트 체크용)
# =========================
@app.get("/storeapp/v1/version")
def version():
    return {"version": "6.0"}

# =========================
# 2️⃣ 로그인 API (POST만 허용)
# =========================
@app.post("/storeapp/v1/auth/login")
def login(req: LoginReq):
    if req.id == SUPER_ID and pwd.verify(req.pw, admins["superadmin"]["pw_hash"]):
        token = jwt.encode(
            {"sub": req.id, "super": True, "exp": int(time.time()) + 1800},
            SECRET,
            algorithm="HS256",
        )
        return {"token": token, "is_super": True}

    for a in admins["admins"]:
        if a["id"] == req.id and pwd.verify(req.pw, a["pw_hash"]):
            token = jwt.encode(
                {"sub": req.id, "super": False, "exp": int(time.time()) + 1800},
                SECRET,
                algorithm="HS256",
            )
            return {"token": token, "is_super": False}

    raise HTTPException(status_code=401, detail="Invalid id or password")

# =========================
# 3️⃣ 슈퍼관리자 인증 함수
# =========================
def _auth_super(auth: str = Header(None)):
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(401, detail="No token")

    tok = auth.split(" ", 1)[1]
    try:
        dec = jwt.decode(tok, SECRET, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, detail="Bad token")

    if not dec.get("super"):
        raise HTTPException(403, detail="Not superadmin")

    return dec

# =========================
# 4️⃣ 관리자 목록 조회
# =========================
@app.get("/storeapp/v1/auth/admins")
def list_admins():
    return {
        "admins": [
            {"id": SUPER_ID, "name": "슈퍼", "is_super": True}
        ]
        + [
            {"id": a["id"], "name": a.get("name", ""), "is_super": False}
            for a in admins["admins"]
        ]
    }

# =========================
# 5️⃣ 부관리자 추가 (슈퍼만)
# =========================
@app.post("/storeapp/v1/auth/admins")
def add_admin(
    req: AdminAddReq = Body(...),
    dec: dict = _auth_super(),
):
    if any(a["id"] == req.id for a in admins["admins"]):
        raise HTTPException(400, detail="exists")

    admins["admins"].append(
        {
            "id": req.id,
            "pw_hash": pwd.hash(req.pw),
            "name": req.name,
        }
    )
    _save(ADMINS_FILE, admins)
    return {"ok": True}

# =========================
# 6️⃣ 전체 데이터 조회
# =========================
@app.get("/storeapp/v1/data")
def get_all():
    return data

# =========================
# 7️⃣ 전체 데이터 저장
# =========================
@app.post("/storeapp/v1/save")
def save_all(body: dict):
    global data
    data = body.get("data", data)
    _save(DATA_FILE, data)
    return {"ok": True}

# =========================
# 8️⃣ 매장별 데이터 조회
# =========================
@app.get("/storeapp/v1/store/{store}")
def get_store(store: str):
    return {"store_data": data.get("byStore", {}).get(store, {})}

# =========================
# 9️⃣ 매장별 데이터 저장
# =========================
@app.post("/storeapp/v1/store/{store}")
def save_store(store: str, body: dict):
    data.setdefault("byStore", {})[store] = body.get("store_data", {})
    _save(DATA_FILE, data)
    return {"ok": True}
