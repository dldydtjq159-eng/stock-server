import os
import json
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import (
    create_engine, Column, Integer, String, DateTime, Text, UniqueConstraint
)
from sqlalchemy.orm import declarative_base, sessionmaker

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
DB_URL = os.getenv("DB_URL", "sqlite:////data/stock.db")

app = FastAPI(title="Stock Cloud", version="3.5")

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

    categories1_json = Column(Text, default="[]")
    categories2_json = Column(Text, default="[]")

    help_text1 = Column(Text, default="")
    help_text2 = Column(Text, default="")

    updated_at = Column(DateTime, default=datetime.utcnow)

class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True, autoincrement=True)
    store_id = Column(String, index=True)
    category_key = Column(String, index=True)
    name = Column(String, index=True)

    # 문자열 메모 필드
    real_stock = Column(String, default="")   # 실재고 메모(문자)
    price = Column(String, default="")
    vendor = Column(String, default="")
    storage = Column(String, default="")
    origin = Column(String, default="")
    note = Column(Text, default="")

    # ✅ 숫자 필드(부족목록 계산은 이걸로만!)
    stock_num = Column(Integer, default=0)    # 현재고(숫자)
    min_stock = Column(Integer, default=0)    # 기준재고(숫자)
    unit = Column(String, default="")         # 단위(개/kg 등)

    updated_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("store_id", "category_key", "name", name="uq_store_cat_name"),
    )

Base.metadata.create_all(bind=engine)

# ---- SQLite 마이그레이션(안정 버전) ----
def ensure_columns():
    if not DB_URL.startswith("sqlite"):
        return

    with engine.connect() as conn:
        cols = conn.exec_driver_sql("PRAGMA table_info(items)").fetchall()
        names = {c[1] for c in cols}

        def add_col(sql):
            conn.exec_driver_sql(sql)

        if "note" not in names:
            add_col("ALTER TABLE items ADD COLUMN note TEXT DEFAULT ''")
        if "stock_num" not in names:
            add_col("ALTER TABLE items ADD COLUMN stock_num INTEGER DEFAULT 0")
        if "min_stock" not in names:
            add_col("ALTER TABLE items ADD COLUMN min_stock INTEGER DEFAULT 0")
        if "unit" not in names:
            add_col("ALTER TABLE items ADD COLUMN unit VARCHAR DEFAULT ''")

        cols2 = conn.exec_driver_sql("PRAGMA table_info(store_meta)").fetchall()
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

DEFAULT_CATEGORIES_SET2 = [
    {"key": "chicken2", "label": "닭(2)"},
    {"key": "sauce2", "label": "소스(2)"},
    {"key": "container2", "label": "용기(2)"},
    {"key": "seasoning2", "label": "조미료(2)"},
    {"key": "oil2", "label": "식용유(2)"},
    {"key": "ricecake2", "label": "떡(2)"},
    {"key": "noodle2", "label": "면(2)"},
    {"key": "veggie2", "label": "야채(2)"},
]

DEFAULT_HELP_1 = (
    "사용방법\n"
    "1) 매장 선택\n"
    "2) 카테고리 선택\n"
    "3) 품목 추가\n"
    "4) 현재고(숫자) + 기준재고(숫자) 설정\n"
    "5) 현재고 < 기준재고면 ‘부족목록’에 필요수량이 뜹니다.\n"
)

DEFAULT_HELP_2 = "세트2도 동일하게 카테고리를 따로 관리합니다."

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
    return 2 if int(set_no) == 2 else 1

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
    note: str = ""
    stock_num: int = 0
    min_stock: int = 0
    unit: str = ""

class ItemUpdate(BaseModel):
    real_stock: str = ""
    price: str = ""
    vendor: str = ""
    storage: str = ""
    origin: str = ""
    note: str = ""
    stock_num: int = 0
    min_stock: int = 0
    unit: str = ""

# -------------------------
# Helpers
# -------------------------
def item_to_dict(r: Item):
    return {
        "id": r.id,
        "store_id": r.store_id,
        "category_key": r.category_key,
        "name": r.name,
        "real_stock": r.real_stock,
        "price": r.price,
        "vendor": r.vendor,
        "storage": r.storage,
        "origin": r.origin,
        "note": r.note or "",
        "stock_num": int(r.stock_num or 0),
        "min_stock": int(r.min_stock or 0),
        "unit": r.unit or "",
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }

# -------------------------
# Routes
# -------------------------
@app.get("/health")
def health():
    return {"ok": True, "service": "stock-server", "version": "3.5"}

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
            note=payload.note,
            stock_num=int(payload.stock_num or 0),
            min_stock=int(payload.min_stock or 0),
            unit=payload.unit or "",
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
        row.note = payload.note
        row.stock_num = int(payload.stock_num or 0)
        row.min_stock = int(payload.min_stock or 0)
        row.unit = payload.unit or ""
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
