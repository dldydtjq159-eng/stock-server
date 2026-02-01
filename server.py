import os
from datetime import datetime
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, DateTime, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
DB_URL = os.getenv("DB_URL", "sqlite:////data/stock.db")  # Railway Volume: /data

app = FastAPI(title="Stock Cloud", version="1.1")

engine = create_engine(
    DB_URL,
    connect_args={"check_same_thread": False, "timeout": 30} if DB_URL.startswith("sqlite") else {},
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

def require_token(x_admin_token: str):
    if not ADMIN_TOKEN or x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

class InventoryCard(Base):
    __tablename__ = "inventory_cards"
    id = Column(Integer, primary_key=True)
    key = Column(String, nullable=False)
    title = Column(String, default="")
    real_stock = Column(String, default="")
    price = Column(String, default="")
    vendor = Column(String, default="")
    storage = Column(String, default="")
    origin = Column(String, default="")
    updated_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("key", name="uq_inventory_key"),)

Base.metadata.create_all(bind=engine)

class CardPayload(BaseModel):
    title: str = ""
    real_stock: str = ""
    price: str = ""
    vendor: str = ""
    storage: str = ""
    origin: str = ""

@app.get("/api/cards/{key}")
def get_card(key: str, x_admin_token: str = Header(default="")):
    require_token(x_admin_token)
    db = SessionLocal()
    row = db.query(InventoryCard).filter(InventoryCard.key == key).first()
    if not row:
        row = InventoryCard(key=key, title=key)
        db.add(row)
        db.commit()
        db.refresh(row)

    data = {
        "key": row.key,
        "title": row.title,
        "real_stock": row.real_stock,
        "price": row.price,
        "vendor": row.vendor,
        "storage": row.storage,
        "origin": row.origin,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None
    }
    db.close()
    return data

@app.post("/api/cards/{key}")
def save_card(key: str, payload: CardPayload, x_admin_token: str = Header(default="")):
    require_token(x_admin_token)
    db = SessionLocal()
    row = db.query(InventoryCard).filter(InventoryCard.key == key).first()
    if not row:
        row = InventoryCard(key=key)
        db.add(row)

    row.title = payload.title or row.title or key
    row.real_stock = payload.real_stock
    row.price = payload.price
    row.vendor = payload.vendor
    row.storage = payload.storage
    row.origin = payload.origin
    row.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(row)
    db.close()
    return {"ok": True, "updated_at": row.updated_at.isoformat()}
