# mobile_api_patch.py
# 사장님 기존 FastAPI 서버에 "모바일 웹"용 API를 추가하는 코드입니다.
# 기존 /storeapp/v1/data, /storeapp/v1/save 와 같은 구조를 유지하면서
# /storeapp/v1/m/* 로 모바일 기능을 제공합니다.
#
# ✅ 기본값:
#   staff_pin = "1234"
#   owner_pw  = "4026"
#   리뷰 링크 = 사장님이 주신 4개 링크
#
# 적용 방법은 README_KR.md 참고

import os, time, hmac, hashlib, base64
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

MOBILE_ROUTER = APIRouter(prefix="/storeapp/v1/m", tags=["mobile"])

# ===== 토큰 서명(간단) =====
MOBILE_SECRET = os.environ.get("MOBILE_SECRET", "CHANGE_ME_SECRET").encode("utf-8")
TOKEN_TTL = 60 * 30  # 30분

def _b64(x: bytes) -> str:
    return base64.urlsafe_b64encode(x).decode("utf-8").rstrip("=")

def _sign(payload: str) -> str:
    sig = hmac.new(MOBILE_SECRET, payload.encode("utf-8"), hashlib.sha256).digest()
    return _b64(sig)

def make_token(role: str) -> str:
    ts = int(time.time())
    payload = f"{role}:{ts}"
    return payload + "." + _sign(payload)

def parse_token(token: str):
    try:
        payload, sig = token.split(".", 1)
        if _sign(payload) != sig:
            return None
        role, ts = payload.split(":", 1)
        ts = int(ts)
        if int(time.time()) - ts > TOKEN_TTL:
            return None
        return {"role": role, "ts": ts}
    except:
        return None

def require_auth(authorization: str | None):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    token = authorization.split(" ", 1)[1].strip()
    info = parse_token(token)
    if not info:
        raise HTTPException(status_code=401, detail="세션이 만료됐거나 인증이 올바르지 않습니다.")
    return info

# ===== 서버의 기존 데이터 저장소를 사용 =====
# 아래 2개 함수는 사장님 서버 코드에 이미 있어야 합니다:
#   - api_get_data()  또는 load data 로직
#   - api_save_data() 또는 save data 로직
# 사장님 서버에 맞게 이름만 연결하세요.
#
# 여기서는 함수 이름을 get_data()/save_data()로 가정합니다.

def get_data():
    raise NotImplementedError("사장님 서버의 '데이터 로드 함수'를 여기에 연결하세요.")

def save_data(data: dict) -> bool:
    raise NotImplementedError("사장님 서버의 '데이터 저장 함수'를 여기에 연결하세요.")

def ensure_mobile_config(d: dict) -> dict:
    d.setdefault("mobile", {})
    m = d["mobile"]
    m.setdefault("staff_pin", "1234")
    m.setdefault("owner_pw", "4026")
    m.setdefault("review_links", {
        "baemin": "https://self.baemin.com/shops/14843749/reviews",
        "coupang": "https://store.coupangeats.com/merchant/management/reviews",
        "yogiyo": "https://ceo.yogiyo.co.kr/reviews",
        "ddangyo": "https://boss.ddangyo.com/",
    })
    return d

class LoginBody(BaseModel):
    pin: str

class OwnerLoginBody(BaseModel):
    pw: str

class UpdateItemBody(BaseModel):
    store: str
    category: str
    index: int
    patch: dict

class MemoSaveBody(BaseModel):
    store: str
    memo: str

class SetPinBody(BaseModel):
    pin: str

class LinksBody(BaseModel):
    links: dict

@MOBILE_ROUTER.get("/ping")
def ping():
    return {"ok": True}

@MOBILE_ROUTER.post("/login")
def login(body: LoginBody):
    d = ensure_mobile_config(get_data())
    if body.pin != str(d["mobile"]["staff_pin"]):
        raise HTTPException(status_code=401, detail="PIN이 올바르지 않습니다.")
    return {"token": make_token("staff"), "role": "staff"}

@MOBILE_ROUTER.post("/owner_login")
def owner_login(body: OwnerLoginBody):
    d = ensure_mobile_config(get_data())
    if body.pw != str(d["mobile"]["owner_pw"]):
        raise HTTPException(status_code=401, detail="비밀번호가 올바르지 않습니다.")
    return {"token": make_token("owner"), "role": "owner"}

@MOBILE_ROUTER.get("/stores")
def stores(authorization: str | None = Header(default=None)):
    require_auth(authorization)
    d = ensure_mobile_config(get_data())
    return {"stores": d.get("stores", [])}

@MOBILE_ROUTER.get("/inventory")
def inventory(store: str, authorization: str | None = Header(default=None)):
    require_auth(authorization)
    d = ensure_mobile_config(get_data())
    st = d.get("byStore", {}).get(store)
    if not st:
        raise HTTPException(status_code=404, detail="매장을 찾을 수 없습니다.")
    return {"inventory": st.get("inventory", {})}

@MOBILE_ROUTER.post("/update_item")
def update_item(body: UpdateItemBody, authorization: str | None = Header(default=None)):
    info = require_auth(authorization)
    d = ensure_mobile_config(get_data())
    st = d.get("byStore", {}).get(body.store)
    if not st:
        raise HTTPException(status_code=404, detail="매장을 찾을 수 없습니다.")
    items = st.get("inventory", {}).get(body.category, [])
    if body.index < 0 or body.index >= len(items):
        raise HTTPException(status_code=400, detail="index 범위 오류")
    # 직원은 current만 수정 허용
    if info["role"] != "owner":
        if set(body.patch.keys()) - {"current"}:
            raise HTTPException(status_code=403, detail="직원 권한에서는 현재고만 수정 가능합니다.")
    items[body.index].update(body.patch)
    ok = save_data(d)
    return {"ok": ok}

@MOBILE_ROUTER.get("/shortages")
def shortages(store: str, authorization: str | None = Header(default=None)):
    require_auth(authorization)
    d = ensure_mobile_config(get_data())
    st = d.get("byStore", {}).get(store)
    if not st:
        raise HTTPException(status_code=404, detail="매장을 찾을 수 없습니다.")
    inv = st.get("inventory", {})
    out = []
    for cat, items in inv.items():
        for it in items:
            try:
                cur = float(it.get("current", 0) or 0)
                mn  = float(it.get("min", 0) or 0)
                if cur < mn:
                    out.append({
                        "category": cat,
                        "name": it.get("name", ""),
                        "current": cur,
                        "lack": max(0, mn-cur),
                        "origin": it.get("origin", ""),
                    })
            except:
                pass
    return {"store": store, "shortages": out}

@MOBILE_ROUTER.get("/memo")
def memo(store: str, authorization: str | None = Header(default=None)):
    require_auth(authorization)
    d = ensure_mobile_config(get_data())
    st = d.get("byStore", {}).get(store)
    if not st:
        raise HTTPException(status_code=404, detail="매장을 찾을 수 없습니다.")
    return {"memo": st.get("memo", "")}

@MOBILE_ROUTER.post("/memo_save")
def memo_save(body: MemoSaveBody, authorization: str | None = Header(default=None)):
    info = require_auth(authorization)
    if info["role"] != "owner":
        raise HTTPException(status_code=403, detail="메모 저장은 사장님만 가능합니다.")
    d = ensure_mobile_config(get_data())
    st = d.get("byStore", {}).get(body.store)
    if not st:
        raise HTTPException(status_code=404, detail="매장을 찾을 수 없습니다.")
    st["memo"] = body.memo
    ok = save_data(d)
    return {"ok": ok}

@MOBILE_ROUTER.post("/set_staff_pin")
def set_staff_pin(body: SetPinBody, authorization: str | None = Header(default=None)):
    info = require_auth(authorization)
    if info["role"] != "owner":
        raise HTTPException(status_code=403, detail="PIN 변경은 사장님만 가능합니다.")
    if not (body.pin.isdigit() and len(body.pin) == 4):
        raise HTTPException(status_code=400, detail="PIN은 4자리 숫자여야 합니다.")
    d = ensure_mobile_config(get_data())
    d["mobile"]["staff_pin"] = body.pin
    ok = save_data(d)
    return {"ok": ok}

@MOBILE_ROUTER.get("/review_links")
def review_links(authorization: str | None = Header(default=None)):
    require_auth(authorization)
    d = ensure_mobile_config(get_data())
    return {"links": d["mobile"]["review_links"]}

@MOBILE_ROUTER.post("/review_links_save")
def review_links_save(body: LinksBody, authorization: str | None = Header(default=None)):
    info = require_auth(authorization)
    if info["role"] != "owner":
        raise HTTPException(status_code=403, detail="링크 저장은 사장님만 가능합니다.")
    d = ensure_mobile_config(get_data())
    d["mobile"]["review_links"].update(body.links or {})
    ok = save_data(d)
    return {"ok": ok}
