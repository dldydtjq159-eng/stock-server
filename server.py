import os
from datetime import datetime

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, DateTime, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker

# -------------------------
# Config
# -------------------------
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
DB_URL = os.getenv("DB_URL", "sqlite:////data/stock.db")  # Railway Volume: /data

app = FastAPI(title="Stock Cloud", version="2.0")

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
# DB Model
# -------------------------
class Card(Base):
    __tablename__ = "cards"
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String, nullable=False)       # chicken, sauce ...
    title = Column(String, default="")

    real_stock = Column(String, default="")
    price = Column(String, default="")
    vendor = Column(String, default="")
    storage = Column(String, default="")
    origin = Column(String, default="")

    updated_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("key", name="uq_cards_key"),)


Base.metadata.create_all(bind=engine)


# -------------------------
# Schema
# -------------------------
class CardPayload(BaseModel):
    title: str = ""
    real_stock: str = ""
    price: str = ""
    vendor: str = ""
    storage: str = ""
    origin: str = ""


# -------------------------
# Routes
# -------------------------
@app.get("/")
def root():
    return {"ok": True, "service": "stock-server", "version": "2.0"}


@app.get("/api/health")
def health():
    return {"ok": True, "time": datetime.utcnow().isoformat()}


@app.get("/api/cards/{card_key}")
def get_card(card_key: str, x_admin_token: str = Header(default="")):
    require_token(x_admin_token)

    db = SessionLocal()
    row = db.query(Card).filter(Card.key == card_key).first()
    if not row:
        row = Card(key=card_key, title=card_key)
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
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
    db.close()
    return data


@app.post("/api/cards/{card_key}")
def save_card(card_key: str, payload: CardPayload, x_admin_token: str = Header(default="")):
    require_token(x_admin_token)

    db = SessionLocal()
    row = db.query(Card).filter(Card.key == card_key).first()
    if not row:
        row = Card(key=card_key)
        db.add(row)

    row.title = payload.title
    row.real_stock = payload.real_stock
    row.price = payload.price
    row.vendor = payload.vendor
    row.storage = payload.storage
    row.origin = payload.origin
    row.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(row)

    out = {"ok": True, "updated_at": row.updated_at.isoformat()}
    db.close()
    return out

