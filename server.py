import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Header, Query
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker

# =========================================================
# Basic Config
# =========================================================
APP_VERSION = "4.0"

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")  # Railway Variables에 설정
DB_URL = os.getenv("DB_URL", "sqlite:////data/stock.db")  # Railway Volume: /data

app = FastAPI(title="Stock Cloud", version=APP_VERSION)

engine = create_engine(
    DB_URL,
    connect_args={"check_same_thread": False} if DB_URL.startswith("sqlite") else {}
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def require_admin(x_admin_token: str):
    if not ADMIN_TOKEN or x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")


def norm_menu(v: Optional[int]) -> int:
    return 2 if int(v or 1) == 2 else 1


# =========================================================
# DB Models
# =========================================================
class Store(Base):
    __tablename__ = "stores"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)


class StoreMeta(Base):
    """
    store_id + menu_no 별로 categories/help를 저장
    """
    __tablename__ = "store_meta"
    id = Column(Integer, primary_key=True, autoincrement=True)
    store_id = Column(String, nullable=False)
    menu_no = Column(Integer, default=1)

    categories_json = Column(Text, default="[]")
    help_text = Column(Text, default="")


class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True, autoincrement=True)

    store_id = Column(String, nullable=False)
    menu_no = Column(Integer, default=1)
    category_key = Column(String, nullable=False)

    name = Column(String, nullable=False)

    # 부족목록 계산용(숫자)
    stock_num = Column(Integer, default=0)   # 현재고
    min_stock = Column(Integer, default=0)   # 기준재고
    unit = Column(String, default="")

    # 상세 정보(문자)
    real_stock = Column(String, default="")  # 실재고 메모
    price = Column(String, default="")
    vendor = Column(String, default="")
    storage = Column(String, default="")
    origin = Column(String, default="")
    note = Column(String, default="")
    buy_url = Column(String, default="")

    updated_at = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(bind=engine)

# =========================================================
# Seed Defaults (중복 방지)
# =========================================================
DEFAULT_STORES = [
    {"id": "kky", "name": "김경영 요리 연구소"},
    {"id": "yhc", "name": "청년회관"},
]

DEFAULT_CATEGORIES = [
    {"key": "chicken", "label": "닭"},
    {"key": "sauce", "label": "소스"},
    {"key": "container", "label": "용기"},
    {"key": "seasoning", "label": "조미료"},
    {"key": "oil", "label": "식용유"},
    {"key": "ricecake", "label": "떡"},
    {"key": "noodle", "label": "면"},
    {"key": "veggie", "label": "야채"},
]

DEFAULT_HELP = (
    "▶ 카테고리 클릭 → 품목 추가/선택 → 저장\n"
    "▶ 부족목록은 (기준재고 > 0) 그리고 (현재고 < 기준재고) 일 때 표시됩니다.\n"
    "▶ 구매링크를 입력하면 버튼으로 사이트를 바로 열 수 있어요.\n"
)

def ensure_defaults():
    db = SessionLocal()
    try:
        # stores seed
        for st in DEFAULT_STORES:
            if not db.query(Store).filter(Store.id == st["id"]).first():
                db.add(Store(id=st["id"], name=st["name"]))
        db.commit()

        # store_meta seed (menu 1,2)
        for st in DEFAULT_STORES:
            for menu_no in (1, 2):
                row = db.query(StoreMeta).filter(
                    StoreMeta.store_id == st["id"],
                    StoreMeta.menu_no == menu_no
                ).first()
                if not row:
                    db.add(StoreMeta(
                        store_id=st["id"],
                        menu_no=menu_no,
                        categories_json=json.dumps(DEFAULT_CATEGORIES, ensure_ascii=False),
                        help_text=DEFAULT_HELP
                    ))
        db.commit()
    finally:
        db.close()

ensure_defaults()

# =========================================================
# Schemas
# =========================================================
class ItemCreate(BaseModel):
    name: str = Field(..., min_length=1)

    stock_num: int = 0
    min_stock: int = 0
    unit: str = ""

    real_stock: str = ""
    price: str = ""
    vendor: str = ""
    storage: str = ""
    origin: str = ""
    note: str = ""
    buy_url: str = ""


class ItemUpdate(BaseModel):
    stock_num: int = 0
    min_stock: int = 0
    unit: str = ""

    real_stock: str = ""
    price: str = ""
    vendor: str = ""
    storage: str = ""
    origin: str = ""
    note: str = ""
    buy_url: str = ""


class AdminCategoriesPayload(BaseModel):
    categories: List[Dict[str, str]] = []
    deleted_keys: List[str] = []   # 삭제한 카테고리 key 목록(서버에서 아이템도 같이 삭제)


class AdminHelpPayload(BaseModel):
    help_text: str = ""


# =========================================================
# Helpers
# =========================================================
def item_to_dict(it: Item) -> Dict[str, Any]:
    return {
        "id": it.id,
        "store_id": it.store_id,
        "menu": it.menu_no,
        "category_key": it.category_key,
        "name": it.name,

        "stock_num": int(it.stock_num or 0),
        "min_stock": int(it.min_stock or 0),
        "unit": it.unit or "",

        "real_stock": it.real_stock or "",
        "price": it.price or "",
        "vendor": it.vendor or "",
        "storage": it.storage or "",
        "origin": it.origin or "",
        "note": it.note or "",
        "buy_url": it.buy_url or "",

        "updated_at": it.updated_at.isoformat() if it.updated_at else None
    }


# =========================================================
# Routes
# =========================================================
@app.get("/")
def root():
    return {"ok": True, "service": "stock-server", "version": APP_VERSION}


@app.get("/api/stores")
def list_stores():
    db = SessionLocal()
    try:
        stores = db.query(Store).all()
        # 이름 중복 제거
        by_name = {}
        for s in stores:
            nm = (s.name or "").strip()
            if nm and nm not in by_name:
                by_name[nm] = s
        uniq = list(by_name.values())
        uniq.sort(key=lambda x: (x.name or ""))
        return {"stores": [{"id": s.id, "name": s.name} for s in uniq]}
    finally:
        db.close()


@app.get("/api/meta/{store_id}")
def get_meta(store_id: str, menu: int = Query(1), set: Optional[int] = Query(None)):
    """
    ✅ menu 파라미터가 공식.
    ✅ 예전 호환으로 set도 받아줌.
    """
    menu_no = norm_menu(menu if menu is not None else set)
    db = SessionLocal()
    try:
        st = db.query(Store).filter(Store.id == store_id).first()
        if not st:
            raise HTTPException(404, "store not found")

        meta = db.query(StoreMeta).filter(StoreMeta.store_id == store_id, StoreMeta.menu_no == menu_no).first()
        if not meta:
            # 방어적으로 생성
            meta = StoreMeta(
                store_id=store_id, menu_no=menu_no,
                categories_json=json.dumps(DEFAULT_CATEGORIES, ensure_ascii=False),
                help_text=DEFAULT_HELP
            )
            db.add(meta)
            db.commit()
            db.refresh(meta)

        cats = json.loads(meta.categories_json or "[]")
        return {
            "store": {"id": st.id, "name": st.name},
            "menu": menu_no,
            "categories": cats,
            "help_text": meta.help_text or ""
        }
    finally:
        db.close()


@app.get("/api/items/{store_id}/{category_key}")
def list_items(store_id: str, category_key: str, menu: int = Query(1), set: Optional[int] = Query(None)):
    menu_no = norm_menu(menu if menu is not None else set)
    db = SessionLocal()
    try:
        q = db.query(Item).filter(
            Item.store_id == store_id,
            Item.menu_no == menu_no,
            Item.category_key == category_key
        ).order_by(Item.name.asc())
        return {"items": [item_to_dict(x) for x in q.all()]}
    finally:
        db.close()


@app.post("/api/items/{store_id}/{category_key}")
def add_item(store_id: str, category_key: str, payload: ItemCreate, menu: int = Query(1), set: Optional[int] = Query(None)):
    menu_no = norm_menu(menu if menu is not None else set)
    db = SessionLocal()
    try:
        # 이름 중복 방지
        exists = db.query(Item).filter(
            Item.store_id == store_id,
            Item.menu_no == menu_no,
            Item.category_key == category_key,
            Item.name == payload.name.strip()
        ).first()
        if exists:
            raise HTTPException(status_code=409, detail="duplicate name")

        it = Item(
            store_id=store_id,
            menu_no=menu_no,
            category_key=category_key,
            name=payload.name.strip(),

            stock_num=int(payload.stock_num or 0),
            min_stock=int(payload.min_stock or 0),
            unit=payload.unit or "",

            real_stock=payload.real_stock or "",
            price=payload.price or "",
            vendor=payload.vendor or "",
            storage=payload.storage or "",
            origin=payload.origin or "",
            note=payload.note or "",
            buy_url=payload.buy_url or "",

            updated_at=datetime.utcnow()
        )
        db.add(it)
        db.commit()
        db.refresh(it)
        return {"ok": True, "id": it.id}
    finally:
        db.close()


@app.put("/api/items/{store_id}/{category_key}/{item_id}")
def update_item(store_id: str, category_key: str, item_id: int, payload: ItemUpdate, menu: int = Query(1), set: Optional[int] = Query(None)):
    menu_no = norm_menu(menu if menu is not None else set)
    db = SessionLocal()
    try:
        it = db.query(Item).filter(
            Item.id == item_id,
            Item.store_id == store_id,
            Item.menu_no == menu_no,
            Item.category_key == category_key
        ).first()
        if not it:
            raise HTTPException(404, "item not found")

        it.stock_num = int(payload.stock_num or 0)
        it.min_stock = int(payload.min_stock or 0)
        it.unit = payload.unit or ""

        it.real_stock = payload.real_stock or ""
        it.price = payload.price or ""
        it.vendor = payload.vendor or ""
        it.storage = payload.storage or ""
        it.origin = payload.origin or ""
        it.note = payload.note or ""
        it.buy_url = payload.buy_url or ""

        it.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(it)
        return {"ok": True, "updated_at": it.updated_at.isoformat()}
    finally:
        db.close()


@app.delete("/api/items/{store_id}/{category_key}/{item_id}")
def delete_item(store_id: str, category_key: str, item_id: int, menu: int = Query(1), set: Optional[int] = Query(None)):
    menu_no = norm_menu(menu if menu is not None else set)
    db = SessionLocal()
    try:
        it = db.query(Item).filter(
            Item.id == item_id,
            Item.store_id == store_id,
            Item.menu_no == menu_no,
            Item.category_key == category_key
        ).first()
        if not it:
            raise HTTPException(404, "item not found")
        db.delete(it)
        db.commit()
        return {"ok": True}
    finally:
        db.close()


@app.get("/api/shortage/{store_id}")
def shortage(store_id: str, menu: int = Query(1), set: Optional[int] = Query(None)):
    """
    ✅ 부족목록은 서버에서 계산해 내려줌 = PC가 흔들려도 안정적
    """
    menu_no = norm_menu(menu if menu is not None else set)
    db = SessionLocal()
    try:
        q = db.query(Item).filter(Item.store_id == store_id, Item.menu_no == menu_no).all()
        rows = []
        for it in q:
            mn = int(it.min_stock or 0)
            st = int(it.stock_num or 0)
            if mn > 0 and st < mn:
                need = mn - st
                d = item_to_dict(it)
                d["need_qty"] = need
                rows.append(d)
        rows.sort(key=lambda x: (-int(x.get("need_qty", 0)), x.get("category_key",""), x.get("name","")))
        return {"items": rows}
    finally:
        db.close()


# =========================================================
# Admin Routes (카테고리/사용문구 편집은 서버 토큰 필요)
# =========================================================
@app.put("/api/admin/meta/{store_id}/categories")
def admin_update_categories(
    store_id: str,
    payload: AdminCategoriesPayload,
    menu: int = Query(1),
    x_admin_token: str = Header(default="")
):
    require_admin(x_admin_token)
    menu_no = norm_menu(menu)
    db = SessionLocal()
    try:
        meta = db.query(StoreMeta).filter(StoreMeta.store_id == store_id, StoreMeta.menu_no == menu_no).first()
        if not meta:
            meta = StoreMeta(
                store_id=store_id, menu_no=menu_no,
                categories_json=json.dumps(DEFAULT_CATEGORIES, ensure_ascii=False),
                help_text=DEFAULT_HELP
            )
            db.add(meta)
            db.commit()
            db.refresh(meta)

        # 삭제된 카테고리의 품목도 서버에서 실제 삭제
        deleted_keys = payload.deleted_keys or []
        if deleted_keys:
            db.query(Item).filter(
                Item.store_id == store_id,
                Item.menu_no == menu_no,
                Item.category_key.in_(deleted_keys)
            ).delete(synchronize_session=False)

        meta.categories_json = json.dumps(payload.categories or [], ensure_ascii=False)
        db.commit()
        return {"ok": True}
    finally:
        db.close()


@app.put("/api/admin/meta/{store_id}/help")
def admin_update_help(
    store_id: str,
    payload: AdminHelpPayload,
    menu: int = Query(1),
    x_admin_token: str = Header(default="")
):
    require_admin(x_admin_token)
    menu_no = norm_menu(menu)
    db = SessionLocal()
    try:
        meta = db.query(StoreMeta).filter(StoreMeta.store_id == store_id, StoreMeta.menu_no == menu_no).first()
        if not meta:
            meta = StoreMeta(
                store_id=store_id, menu_no=menu_no,
                categories_json=json.dumps(DEFAULT_CATEGORIES, ensure_ascii=False),
                help_text=DEFAULT_HELP
            )
            db.add(meta)
            db.commit()
            db.refresh(meta)

        meta.help_text = payload.help_text or ""
        db.commit()
        return {"ok": True}
    finally:
        db.close()
