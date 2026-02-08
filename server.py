
# ===== server.py (추가 API 포함) =====
import os, json, time
from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel
from passlib.context import CryptContext
import jwt

app = FastAPI()
pwd_ctx = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

TOKEN_SECRET = os.environ.get("TOKEN_SECRET","change-me")
SUPERADMIN_ID = os.environ.get("SUPERADMIN_ID","dldydtjq159")
SUPERADMIN_PW = os.environ.get("SUPERADMIN_PW","tkfkd4026")

ADMINS_FILE = "admins.json"

def load_admins():
    if os.path.exists(ADMINS_FILE):
        with open(ADMINS_FILE,"r",encoding="utf-8") as f:
            return json.load(f)
    data = {"superadmin":{"id":SUPERADMIN_ID,"pw_hash":pwd_ctx.hash(SUPERADMIN_PW)},"admins":[]}
    with open(ADMINS_FILE,"w",encoding="utf-8") as f: json.dump(data,f,indent=2)
    return data

def save_admins(obj):
    with open(ADMINS_FILE,"w",encoding="utf-8") as f:
        json.dump(obj,f,indent=2)

@app.get("/storeapp/v1/version")
def version():
    return {"version":"1.1.0","notes":"부관리자 관리 추가","download_url":""}

class LoginIn(BaseModel):
    id:str; pw:str

@app.post("/storeapp/v1/auth/login")
def login(inp:LoginIn):
    data = load_admins()
    # 슈퍼
    if inp.id==data["superadmin"]["id"] and pwd_ctx.verify(inp.pw, data["superadmin"]["pw_hash"]):
        token = jwt.encode({"id":inp.id,"super":True,"ts":time.time()},TOKEN_SECRET,algorithm="HS256")
        return {"token":token,"is_super":True}
    # 부관리자
    for a in data["admins"]:
        if a["id"]==inp.id and pwd_ctx.verify(inp.pw, a["pw_hash"]):
            token = jwt.encode({"id":inp.id,"super":False,"ts":time.time()},TOKEN_SECRET,algorithm="HS256")
            return {"token":token,"is_super":False}
    raise HTTPException(401,"Invalid id or password")

def get_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401,"No token")
    token = authorization.split(" ",1)[1]
    try:
        payload = jwt.decode(token,TOKEN_SECRET,algorithms=["HS256"])
        return payload
    except:
        raise HTTPException(401,"Bad token")

class AdminIn(BaseModel):
    id:str; pw:str

@app.get("/storeapp/v1/auth/admins")
def list_admins(user=Depends(get_user)):
    data = load_admins()
    if not user.get("super"):
        raise HTTPException(403,"Only superadmin")
    return {"admins":[{"id":a["id"]} for a in data["admins"]]}

@app.post("/storeapp/v1/auth/admins")
def add_admin(inp:AdminIn, user=Depends(get_user)):
    data = load_admins()
    if not user.get("super"):
        raise HTTPException(403,"Only superadmin")
    for a in data["admins"]:
        if a["id"]==inp.id:
            raise HTTPException(400,"Already exists")
    data["admins"].append({"id":inp.id,"pw_hash":pwd_ctx.hash(inp.pw)})
    save_admins(data)
    return {"ok":True}
