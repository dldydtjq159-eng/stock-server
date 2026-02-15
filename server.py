from fastapi import FastAPI
from datetime import datetime, timedelta

app = FastAPI()

# ====== 임시 DB ======
users = {}
keys = {}

# =====================
# 서버 확인
# =====================
@app.get("/")
def home():
    return {"status": "MCR License Server Running"}

# =====================
# 회원가입
# =====================
@app.post("/signup")
def signup(id: str, pw: str):
    if id in users:
        return {"success": False, "msg": "이미 가입됨"}

    users[id] = {"pw": pw, "expire": None}
    return {"success": True}

# =====================
# 로그인
# =====================
@app.post("/login")
def login(id: str, pw: str):
    user = users.get(id)
    if not user or user["pw"] != pw:
        return {"success": False}

    if user["expire"] and user["expire"] > datetime.now():
        remain = (user["expire"] - datetime.now()).days
        return {"success": True, "remain_days": remain}

    return {"success": True, "remain_days": 0}

# =====================
# 코드 등록
# =====================
@app.post("/use_key")
def use_key(id: str, key: str):

    if key not in keys:
        return {"success": False, "msg": "잘못된 코드"}

    days = keys[key]
    expire = datetime.now() + timedelta(days=days)

    users[id]["expire"] = expire
    del keys[key]

    return {"success": True, "expire": expire}

# =====================
# 관리자 키 생성
# =====================
@app.post("/generate_key")
def generate_key(days: int):

    import random
    key = "KEY-" + str(random.randint(100000,999999))
    keys[key] = days

    return {"key": key, "days": days}
