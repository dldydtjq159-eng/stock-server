import os
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import (
    create_engine, Column, Integer, String, DateTime, Text, Boolean
)
from sqlalchemy.orm import declarative_base, sessionmaker

# -------------------------------------------------
# Config
# -------------------------------------------------
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
DB_URL = os.getenv("DB_URL", "sqlite:////data/stock.db")  # Railway Volume: /data

app = FastAPI(title="Stock Cloud", version="3.1")

engine = create_engine(
    DB_URL,
    connect_args={"check_same_thread": False} if DB_URL.startswith("sqlite") else {}
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

def require_admin_token(x_admin_token: str):
    if not ADMIN_TOKEN or x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

# -------------------------------------------------
# DB Models
# -------------------------------------------------
class Store(Base):
    __tablename__ = "stores"
    id = Column(String, primary_key=True)  # "kky" 같은 문자열
    name = Column(String, nullable=False)

class StoreHelpText(Base):
    __tablename__ = "store_help_text"
    id = Column(Integer, primary_key=True, autoincrement=True)
    store_id = Column(String, nullable=False)
    set_no = Column(Integer, default=1)
    text = Column(Text, default="")

class StoreCategories(Base):
    __tablename__ = "store_categories"
    id = Column(Integer, primary_key=True, autoincrement=True)
    store_id = Column(String, nullable=False)
    set_no = Column(Integer, default=1)
    categories_json = Column(Text, default="[]")  # [{"key":"chicken","label":"닭"}, ...]

class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True, autoincrement=True)
    store_id = Column(String, nullable=False)
    set_no = Column(Integer, default=1)

    category_key = Column(String, nullable=False)
    name = Column(String, nullable=False)

    stock_num = Column(Integer, default=0)
    min_stock = Column(Integer, default=0)
    unit = Column(String, default="")

    real_stock = Column(String, default="")  # 메모/실재고 텍스트
    price = Column(String, default="")
    vendor = Column(String, default="")
    storage = Column(String, default="")
    origin = Column(String, default="")
    note = Column(String, default="")

    buy_url = Column(String, default="")  # ✅ 구매링크

    updated_at = Column(DateTime, default=datetime.utcnow)

# -------------------------------------------------
# Create tables
# -------------------------------------------------
Base.metadata.create_all(bind=engine)

# -------------------------------------------------
# SQLite 컬럼 자동 추가(기존 DB 유지용)
# -------------------------------------------------
def sqlite_has_column(table: str, column: str) -> bool:
    if not DB_URL.startswith("sqlite"):
        return True
    with engine.connect() as conn:
        rows = conn.exec_driver_sql(f"PRAGMA table_info({table});").fetchall()
        cols = [r[1] for r in rows]  # (cid, name, type, notnull, dflt_value, pk)
        return column in cols

def sqlite_add_column(table: str, ddl: str):
    if not DB_URL.startswith("sqlite"):
        return
    with engine.connect() as conn:
        conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {ddl};")

# buy_url 컬럼이 기존 DB에 없으면 추가
try:
    if not sqlite_has_column("items", "buy_url"):
        sqlite_add_column("items", "buy_url TEXT DEFAULT ''")
except Exception:
    # ALTER TABLE 실패해도 서버는 떠야 하니 무시
    pass

# -------------------------------------------------
# Default seed (처음 사용자 편하게)
# -------------------------------------------------
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

def ensure_defaults():
    db = SessionLocal()
    try:
        # stores
        for st in DEFAULT_STORES:
            ex = db.query(Store).filter(Store.id == st["id"]).first()
            if not ex:
                db.add(Store(id=st["id"], name=st["name"]))
        db.commit()

        # categories & helptext for each store and set 1/2
        for st in DEFAULT_STORES:
            for set_no in (1, 2):
                c = db.query(StoreCategories).filter(
                    StoreCategories.store_id == st["id"],
                    StoreCategories.set_no == set_no
                ).first()
                if not c:
                    import json
                    db.add(StoreCategories(
                        store_id=st["id"],
                        set_no=set_no,
                        categories_json=json.dumps(DEFAULT_CATEGORIES, ensure_ascii=False)
                    ))
                h = db.query(StoreHelpText).filter(
                    StoreHelpText.store_id == st["id"],
                    StoreHelpText.set_no == set_no
                ).first()
                if not h:
                    db.add(StoreHelpText(
                        store_id=st["id"],
                        set_no=set_no,
                        text="▶ 카테고리 클릭 → 품목(종류) 추가/선택 → 저장\n▶ 기준재고 미만이면 부족목록에 자동 표시됩니다."
                    ))
        db.commit()
    finally:
        db.close()

ensure_defaults()

# -------------------------------------------------
# Schemas
# -------------------------------------------------
class ItemCreate(BaseModel):
    name: str
    stock_num: int = 0
    min_stock: int = 0
    unit: str = ""
    real_stock: str = ""
    price: str = ""
    vendor: str = ""
    storage: str = ""
    origin: str = ""
    note: str = ""
    buy_url: str = ""  # ✅

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
    buy_url: str = ""  # ✅

class HelpTextPayload(BaseModel):
    text: str = ""

class CategoriesPayload(BaseModel):
    categories: List[Dict[str, str]] = []
    deleted_keys: List[str] = []

# -------------------------------------------------
# Utils
# -------------------------------------------------
def item_to_dict(it: Item) -> Dict[str, Any]:
    return {
        "id": it.id,
        "store_id": it.store_id,
        "set_no": it.set_no,
        "category_key": it.category_key,
        "name": it.name,
        "stock_num": it.stock_num,
        "min_stock": it.min_stock,
        "unit": it.unit,
        "real_stock": it.real_stock,
        "price": it.price,
        "vendor": it.vendor,
        "storage": it.storage,
        "origin": it.origin,
        "note": it.note,
        "buy_url": it.buy_url,  # ✅
        "updated_at": it.updated_at.isoformat() if it.updated_at else None
    }

# -------------------------------------------------
# Routes
# -------------------------------------------------
@app.get("/")
def root():
    return {"ok": True, "service": "stock-server", "version": "3.1"}

@app.get("/api/stores")
def list_stores():
    db = SessionLocal()
    try:
        stores = db.query(Store).order_by(Store.name.asc()).all()
        return {"stores": [{"id": s.id, "name": s.name} for s in stores]}
    finally:
        db.close()

@app.get("/api/stores/{store_id}/meta")
def store_meta(store_id: str, set: int = Query(1)):
    set_no = 2 if int(set) == 2 else 1
    db = SessionLocal()
    try:
        st = db.query(Store).filter(Store.id == store_id).first()
        if not st:
            raise HTTPException(404, "store not found")

        c = db.query(StoreCategories).filter(
            StoreCategories.store_id == store_id,
            StoreCategories.set_no == set_no
        ).first()
        h = db.query(StoreHelpText).filter(
            StoreHelpText.store_id == store_id,
            StoreHelpText.set_no == set_no
        ).first()

        import json
        cats = json.loads(c.categories_json) if c and c.categories_json else []
        help_text = h.text if h else ""

        return {
            "store": {"id": st.id, "name": st.name},
            "set": set_no,
            "categories": cats,
            "help_text": help_text
        }
    finally:
        db.close()

# Items list by category
@app.get("/api/items/{store_id}/{category_key}")
def list_items(store_id: str, category_key: str, set: int = Query(1)):
    set_no = 2 if int(set) == 2 else 1
    db = SessionLocal()
    try:
        q = db.query(Item).filter(
            Item.store_id == store_id,
            Item.set_no == set_no,
            Item.category_key == category_key
        ).order_by(Item.name.asc())
        items = [item_to_dict(x) for x in q.all()]
        return {"items": items}
    finally:
        db.close()

# All items
@app.get("/api/items/{store_id}/all")
def list_items_all(store_id: str, set: int = Query(1)):
    set_no = 2 if int(set) == 2 else 1
    db = SessionLocal()
    try:
        q = db.query(Item).filter(Item.store_id == store_id, Item.set_no == set_no)
        items = [item_to_dict(x) for x in q.all()]
        return {"items": items}
    finally:
        db.close()

# Add item
@app.post("/api/items/{store_id}/{category_key}")
def add_item(store_id: str, category_key: str, payload: ItemCreate, set: int = Query(1)):
    set_no = 2 if int(set) == 2 else 1
    db = SessionLocal()
    try:
        # unique by (store, set, category, name)
        exists = db.query(Item).filter(
            Item.store_id == store_id,
            Item.set_no == set_no,
            Item.category_key == category_key,
            Item.name == payload.name
        ).first()
        if exists:
            raise HTTPException(status_code=409, detail="duplicate name")

        it = Item(
            store_id=store_id,
            set_no=set_no,
            category_key=category_key,
            name=payload.name.strip(),
            stock_num=payload.stock_num,
            min_stock=payload.min_stock,
            unit=payload.unit,
            real_stock=payload.real_stock,
            price=payload.price,
            vendor=payload.vendor,
            storage=payload.storage,
            origin=payload.origin,
            note=payload.note,
            buy_url=payload.buy_url,  # ✅
            updated_at=datetime.utcnow()
        )
        db.add(it)
        db.commit()
        db.refresh(it)
        return {"ok": True, "id": it.id}
    finally:
        db.close()

# Update item
@app.put("/api/items/{store_id}/{category_key}/{item_id}")
def update_item(store_id: str, category_key: str, item_id: int, payload: ItemUpdate, set: int = Query(1)):
    set_no = 2 if int(set) == 2 else 1
    db = SessionLocal()
    try:
        it = db.query(Item).filter(
            Item.id == item_id,
            Item.store_id == store_id,
            Item.set_no == set_no,
            Item.category_key == category_key
        ).first()
        if not it:
            raise HTTPException(404, "item not found")

        it.stock_num = payload.stock_num
        it.min_stock = payload.min_stock
        it.unit = payload.unit
        it.real_stock = payload.real_stock
        it.price = payload.price
        it.vendor = payload.vendor
        it.storage = payload.storage
        it.origin = payload.origin
        it.note = payload.note
        it.buy_url = payload.buy_url  # ✅
        it.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(it)
        return {"ok": True, "updated_at": it.updated_at.isoformat()}
    finally:
        db.close()

# Delete item
@app.delete("/api/items/{store_id}/{category_key}/{item_id}")
def delete_item(store_id: str, category_key: str, item_id: int, set: int = Query(1)):
    set_no = 2 if int(set) == 2 else 1
    db = SessionLocal()
    try:
        it = db.query(Item).filter(
            Item.id == item_id,
            Item.store_id == store_id,
            Item.set_no == set_no,
            Item.category_key == category_key
        ).first()
        if not it:
            raise HTTPException(404, "item not found")
        db.delete(it)
        db.commit()
        return {"ok": True}
    finally:
        db.close()

# Admin: help text
@app.put("/api/admin/stores/{store_id}/helptext")
def admin_helptext(store_id: str, payload: HelpTextPayload, set: int = Query(1), x_admin_token: str = Header(default="")):
    require_admin_token(x_admin_token)
    set_no = 2 if int(set) == 2 else 1
    db = SessionLocal()
    try:
        row = db.query(StoreHelpText).filter(StoreHelpText.store_id == store_id, StoreHelpText.set_no == set_no).first()
        if not row:
            row = StoreHelpText(store_id=store_id, set_no=set_no, text=payload.text)
            db.add(row)
        else:
            row.text = payload.text
        db.commit()
        return {"ok": True}
    finally:
        db.close()

# Admin: categories + deleted category items cleanup
@app.put("/api/admin/stores/{store_id}/categories")
def admin_categories(store_id: str, payload: CategoriesPayload, set: int = Query(1), x_admin_token: str = Header(default="")):
    require_admin_token(x_admin_token)
    set_no = 2 if int(set) == 2 else 1
    db = SessionLocal()
    try:
        import json

        row = db.query(StoreCategories).filter(StoreCategories.store_id == store_id, StoreCategories.set_no == set_no).first()
        if not row:
            row = StoreCategories(store_id=store_id, set_no=set_no, categories_json="[]")
            db.add(row)

        # 삭제된 카테고리 품목들 서버에서 실제 삭제
        deleted_keys = payload.deleted_keys or []
        if deleted_keys:
            db.query(Item).filter(
                Item.store_id == store_id,
                Item.set_no == set_no,
                Item.category_key.in_(deleted_keys)
            ).delete(synchronize_session=False)

        row.categories_json = json.dumps(payload.categories or [], ensure_ascii=False)
        db.commit()
        return {"ok": True}
    finally:
        db.close()


