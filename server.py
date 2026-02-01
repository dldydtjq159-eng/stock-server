import os
import json
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import (
    create_engine, Column, Integer, String, DateTime, Text, UniqueConstraint, text
)
from sqlalchemy.orm import declarative_base, sessionmaker

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
DB_URL = os.getenv("DB_URL", "sqlite:////data/stock.db")

app = FastAPI(title="Stock Cloud", version="3.4")

engine = create_engine(
    DB_URL,
    connect_args={"check_same_thread": False} if DB_URL.startswith("sqlite") else {}
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

def require_token(x_admin_token: str):
    if not ADMIN_TOKEN or x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

# -------------------------
# Models
# -------------------------
class StoreMeta(Base):
    __tablename__ = "store_meta"
    id = Column(Integer, primary_key=True, autoincrement=True)
    store_id = Column(String, unique=True, index=True)
    store_name = Column(String, default="")

    # ✅ 카테고리 세트 1/2
    categories1_json = Column(Text, default="[]")
    categories2_json = Column(Text, default="[]")

    # ✅ 사용방법 문구 세트 1/2
    help_text1 = Column(Text, default="")
    help_text2 = Column(Text, default="")

    updated_at = Column(DateTime, default=datetime.utcnow)

class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True, autoincrement=True)
    store_id = Column(String, index=True)
    category_key = Column(String, index=True)
    name = Column(String, index=True)

    real_stock = Column(String, default="")
    price = Column(String, default="")
    vendor = Column(String, default="")
    storage = Column(String, default="")
    origin = Column(String, default="")

    stock_num = Column(Integer, default=0)
    unit = Column(String, default="")
    min_stock = Column(Integer, default=0)
    note = Column(Text, default="")

    updated_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("store_id", "category_key", "name", name="uq_store_cat_name"),
    )

Base.metadata.create_all(bind=engine)

# ---- SQLite 마이그레이션 ----
def ensure_columns():
    if not DB_URL.startswith("sqlite"):
        return

    with engine.connect() as conn:
        # items 컬럼
        cols = conn.execute(text("PRAGMA table_info(items)")).fetchall()
        names = {c[1] for c in cols}

        def add_col(sql):
            conn.execute(text(sql))

        if "stock_num" not in names:
            add_col("ALTER TABLE items ADD COLUMN stock_num INTEGER DEFAULT 0")
        if "unit" not in names:
            add_col("ALTER TABLE items ADD COLUMN unit VARCHAR DEFAULT ''")
        if "min_stock" not in names:
            add_col("ALTER TABLE items ADD COLUMN min_stock INTEGER DEFAULT 0")
        if "note" not in names:
            add_col("ALTER TABLE items ADD COLUMN note TEXT DEFAULT ''")

        # store_meta 컬럼
        cols2 = conn.execute(text("PRAGMA table_info(store_meta)")).fetchall()
        names2 = {c[1] for c in cols2}

        if "categories1_json" not in names2:
            add_col("ALTER TABLE store_meta ADD COLUMN categories1_json TEXT DEFAULT '[]'")
        if "categories2_json" not in names2:
            add_col("ALTER TABLE store_meta ADD COLUMN categories2_json TEXT DEFAULT '[]'")
        if "help_text1" not in names2:
            add_col("ALTER TABLE store_meta ADD COLUMN help_text1 TEXT DEFAULT ''")
        if "help_text2" not in names2:
            add_col("ALTER TABLE store_meta ADD COLUMN help_text2 TEXT DEFAULT ''")

ensure_columns()

# -------------------------
# Defaults
# -------------------------
DEFAULT_STORES = [
    {"id": "kitchenlab", "name": "김경영 요리 연구소"},
    {"id": "youthhall", "name": "청년회관"},
]

DEFAULT_CATEGORIES_SET1 = [
    {"key": "chicken", "label": "닭"},
    {"key": "sauce", "label": "소스"},
    {"key": "container", "label": "용기"},
    {"key": "seasoning", "label": "조미료"},
    {"key": "oil", "label": "식용유"},
    {"key": "ricecake", "label": "떡"},
    {"key": "noodle", "label": "면"},
    {"key": "veggie", "label": "야채"},
]

# 세트2 기본값(원하면 나중에 관리자에서 수정)
DEFAULT_CATEGORIES_SET2 = [
    {"key": "chicken", "label": "닭(세트2)"},
    {"key": "sauce", "label": "소스(세트2)"},
    {"key": "container", "label": "용기(세트2)"},
    {"key": "seasoning", "label": "조미료(세트2)"},
    {"key": "oil", "label": "식용유(세트2)"},
    {"key": "ricecake", "label": "떡(세트2)"},
    {"key": "noodle", "label": "면(세트2)"},
    {"key": "veggie", "label": "야채(세트2)"},
]

DEFAULT_HELP_1 = (
    "사용방법(세트 1)\n"
    "1) 매장 선택\n"
    "2) 카테고리 선택\n"
    "3) 품목 추가 후 입력\n"
    "4) 저장하면 모든 PC에서 동일하게 보입니다.\n\n"
    "TIP: 최소수량 설정 → 부족목록에서 자동 모음\n"
)

DEFAULT_HELP_2 = (
    "사용방법(세트 2)\n"
    "세트 2는 카테고리를 따로 관리할 수 있습니다.\n"
)

def ensure_store_meta():
    db = SessionLocal()
    try:
        for s in DEFAULT_STORES:
            row = db.query(StoreMeta).filter(StoreMeta.store_id == s["id"]).first()
            if not row:
                row = StoreMeta(
                    store_id=s["id"],
                    store_name=s["name"],
                    categories1_json=json.dumps(DEFAULT_CATEGORIES_SET1, ensure_ascii=False),
                    categories2_json=json.dumps(DEFAULT_CATEGORIES_SET2, ensure_ascii=False),
                    help_text1=DEFAULT_HELP_1,
                    help_text2=DEFAULT_HELP_2,
                    updated_at=datetime.utcnow()
                )
                db.add(row)
            else:
                # 기존 row가 set 컬럼 비어있으면 채워넣기
                if not (row.categories1_json or "").strip():
                    row.categories1_json = json.dumps(DEFAULT_CATEGORIES_SET1, ensure_ascii=False)
                if not (row.categories2_json or "").strip():
                    row.categories2_json = json.dumps(DEFAULT_CATEGORIES_SET2, ensure_ascii=False)
                if not (row.help_text1 or "").strip():
                    row.help_text1 = DEFAULT_HELP_1
                if not (row.help_text2 or "").strip():
                    row.help_text2 = DEFAULT_HELP_2
        db.commit()
    finally:
        db.close()

ensure_store_meta()

def pick_set(set_no: int) -> int:
    return 2 if set_no == 2 else 1

# -------------------------
# Schemas
# -------------------------
class Category(BaseModel):
    key: str
    label: str

class CategoriesPayload(BaseModel):
    categories: List[Category]
    deleted_keys: Optional[List[str]] = None

class HelpTextPayload(BaseModel):
    text: str

class ItemCreate(BaseModel):
    name: str
    real_stock: str = ""
    price: str = ""
    vendor: str = ""
    storage: str = ""
    origin: str = ""
    stock_num: int = 0
    unit: str = ""
    min_stock: int = 0
    note: str = ""

class ItemUpdate(BaseModel):
    real_stock: str = ""
    price: str = ""
    vendor: str = ""
    storage: str = ""
    origin: str = ""
    stock_num: int = 0
    unit: str = ""
    min_stock: int = 0
    note: str = ""

# -------------------------
# Routes
# -------------------------
@app.get("/health")
def health():
    return {"ok": True, "service": "stock-server", "version": "3.4"}

@app.get("/api/stores")
def stores():
    return {"stores": DEFAULT_STORES}

@app.get("/api/stores/{store_id}/meta")
def store_meta(store_id: str, set: int = Query(default=1)):
    set_no = pick_set(set)
    db = SessionLocal()
    try:
        row = db.query(StoreMeta).filter(StoreMeta.store_id == store_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="store not found")

        if set_no == 1:
            cats_json = row.categories1_json or "[]"
            help_text = row.help_text1 or ""
        else:
            cats_json = row.categories2_json or "[]"
            help_text = row.help_text2 or ""

        try:
            categories = json.loads(cats_json)
        except Exception:
            categories = []

        return {
            "store": {"id": row.store_id, "name": row.store_name},
            "set": set_no,
            "categories": categories,
            "help_text": help_text,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None
        }
    finally:
        db.close()

def item_to_dict(r: Item):
    return {
        "id": r.id,
        "name": r.name,
        "real_stock": r.real_stock,
        "price": r.price,
        "vendor": r.vendor,
        "storage": r.storage,
        "origin": r.origin,
        "stock_num": int(r.stock_num or 0),
        "unit": r.unit or "",
        "min_stock": int(r.min_stock or 0),
        "note": r.note or "",
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        "category_key": r.category_key,
        "store_id": r.store_id,
    }

# ---- Items (no token needed) ----
@app.get("/api/items/{store_id}/{cat_key}")
def list_items(store_id: str, cat_key: str):
    db = SessionLocal()
    try:
        rows = (
            db.query(Item)
            .filter(Item.store_id == store_id, Item.category_key == cat_key)
            .order_by(Item.name.asc())
            .all()
        )
        return {"items": [item_to_dict(r) for r in rows]}
    finally:
        db.close()

@app.get("/api/items/{store_id}/all")
def list_all_items(store_id: str):
    db = SessionLocal()
    try:
        rows = (
            db.query(Item)
            .filter(Item.store_id == store_id)
            .order_by(Item.category_key.asc(), Item.name.asc())
            .all()
        )
        return {"items": [item_to_dict(r) for r in rows]}
    finally:
        db.close()

@app.post("/api/items/{store_id}/{cat_key}")
def add_item(store_id: str, cat_key: str, payload: ItemCreate):
    db = SessionLocal()
    try:
        name = (payload.name or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="name required")

        row = Item(
            store_id=store_id,
            category_key=cat_key,
            name=name,
            real_stock=payload.real_stock,
            price=payload.price,
            vendor=payload.vendor,
            storage=payload.storage,
            origin=payload.origin,
            stock_num=payload.stock_num,
            unit=payload.unit,
            min_stock=payload.min_stock,
            note=payload.note,
            updated_at=datetime.utcnow()
        )
        db.add(row)
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise HTTPException(status_code=409, detail="duplicate name")

        db.refresh(row)
        return {"ok": True, "id": row.id, "updated_at": row.updated_at.isoformat()}
    finally:
        db.close()

@app.put("/api/items/{store_id}/{cat_key}/{item_id}")
def update_item(store_id: str, cat_key: str, item_id: int, payload: ItemUpdate):
    db = SessionLocal()
    try:
        row = (
            db.query(Item)
            .filter(Item.id == item_id, Item.store_id == store_id, Item.category_key == cat_key)
            .first()
        )
        if not row:
            raise HTTPException(status_code=404, detail="item not found")

        row.real_stock = payload.real_stock
        row.price = payload.price
        row.vendor = payload.vendor
        row.storage = payload.storage
        row.origin = payload.origin
        row.stock_num = payload.stock_num
        row.unit = payload.unit
        row.min_stock = payload.min_stock
        row.note = payload.note
        row.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(row)
        return {"ok": True, "updated_at": row.updated_at.isoformat()}
    finally:
        db.close()

@app.delete("/api/items/{store_id}/{cat_key}/{item_id}")
def delete_item(store_id: str, cat_key: str, item_id: int):
    db = SessionLocal()
    try:
        row = (
            db.query(Item)
            .filter(Item.id == item_id, Item.store_id == store_id, Item.category_key == cat_key)
            .first()
        )
        if not row:
            raise HTTPException(status_code=404, detail="item not found")

        db.delete(row)
        db.commit()
        return {"ok": True}
    finally:
        db.close()

# ---- Admin: categories/helptext (세트별) ----
@app.put("/api/admin/stores/{store_id}/helptext")
def admin_helptext(
    store_id: str,
    payload: HelpTextPayload,
    set: int = Query(default=1),
    x_admin_token: str = Header(default="")
):
    require_token(x_admin_token)
    set_no = pick_set(set)
    db = SessionLocal()
    try:
        row = db.query(StoreMeta).filter(StoreMeta.store_id == store_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="store not found")

        if set_no == 1:
            row.help_text1 = payload.text or ""
        else:
            row.help_text2 = payload.text or ""

        row.updated_at = datetime.utcnow()
        db.commit()
        return {"ok": True, "set": set_no, "updated_at": row.updated_at.isoformat()}
    finally:
        db.close()

@app.put("/api/admin/stores/{store_id}/categories")
def admin_categories(
    store_id: str,
    payload: CategoriesPayload,
    set: int = Query(default=1),
    x_admin_token: str = Header(default="")
):
    require_token(x_admin_token)
    set_no = pick_set(set)
    db = SessionLocal()
    try:
        row = db.query(StoreMeta).filter(StoreMeta.store_id == store_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="store not found")

        cats = [{"key": c.key, "label": c.label} for c in payload.categories]
        if set_no == 1:
            row.categories1_json = json.dumps(cats, ensure_ascii=False)
        else:
            row.categories2_json = json.dumps(cats, ensure_ascii=False)

        row.updated_at = datetime.utcnow()

        deleted_keys = payload.deleted_keys or []
        deleted_keys = [k.strip() for k in deleted_keys if isinstance(k, str) and k.strip()]
        if deleted_keys:
            (
                db.query(Item)
                .filter(Item.store_id == store_id, Item.category_key.in_(deleted_keys))
                .delete(synchronize_session=False)
            )

        db.commit()
        return {"ok": True, "set": set_no, "deleted_keys": deleted_keys, "updated_at": row.updated_at.isoformat()}
    finally:
        db.close()
