# server.py
import os
import json
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

SERVICE = "stock-server"
VERSION = "4.1"

# ✅ Railway에서 Volume Mount path를 /data 로 설정해야 함
DATA_DIR = os.getenv("DATA_DIR", "/data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "stock.db")

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "").strip()  # Railway Variables에서 설정 권장

app = FastAPI(title=SERVICE)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------
# DB helpers
# -------------------------
def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def db_connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    con = db_connect()
    cur = con.cursor()

    # stores
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS stores (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    # store_meta: categories_json + usage_text
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS store_meta (
            store_id TEXT PRIMARY KEY,
            usage_text TEXT NOT NULL DEFAULT '',
            categories_json TEXT NOT NULL DEFAULT '[]',
            updated_at TEXT NOT NULL,
            FOREIGN KEY (store_id) REFERENCES stores(id) ON DELETE CASCADE
        )
        """
    )

    # items
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS items (
            id TEXT PRIMARY KEY,
            store_id TEXT NOT NULL,
            category_key TEXT NOT NULL,
            name TEXT NOT NULL,
            current_qty REAL NOT NULL DEFAULT 0,
            min_qty REAL NOT NULL DEFAULT 0,
            unit TEXT NOT NULL DEFAULT '',
            price TEXT NOT NULL DEFAULT '',
            vendor TEXT NOT NULL DEFAULT '',
            storage TEXT NOT NULL DEFAULT '',
            origin TEXT NOT NULL DEFAULT '',
            buy_link TEXT NOT NULL DEFAULT '',
            memo TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(store_id, category_key, name),
            FOREIGN KEY (store_id) REFERENCES stores(id) ON DELETE CASCADE
        )
        """
    )

    con.commit()
    con.close()


def ensure_default_data():
    """
    기본 매장 2개 + 기본 카테고리 생성(없으면)
    """
    con = db_connect()
    cur = con.cursor()

    default_stores = [
        ("lab", "김경영 요리 연구소"),
        ("youth", "청년회관"),
    ]

    for sid, sname in default_stores:
        cur.execute("SELECT id FROM stores WHERE id=?", (sid,))
        if cur.fetchone() is None:
            cur.execute(
                "INSERT INTO stores(id, name, created_at) VALUES (?,?,?)",
                (sid, sname, now_iso()),
            )

        # meta 없으면 생성
        cur.execute("SELECT store_id FROM store_meta WHERE store_id=?", (sid,))
        if cur.fetchone() is None:
            default_categories = [
                {"key": "chicken", "label": "닭", "sort": 10},
                {"key": "sauce", "label": "소스", "sort": 20},
                {"key": "container", "label": "용기", "sort": 30},
                {"key": "seasoning", "label": "조미료", "sort": 40},
                {"key": "oil", "label": "식용유", "sort": 50},
                {"key": "ricecake", "label": "떡", "sort": 60},
                {"key": "noodle", "label": "면", "sort": 70},
                {"key": "veggie", "label": "야채", "sort": 80},
            ]
            cur.execute(
                """
                INSERT INTO store_meta(store_id, usage_text, categories_json, updated_at)
                VALUES (?,?,?,?)
                """,
                (sid, "카테고리 클릭 → 품목 추가/선택 → 저장", json.dumps(default_categories, ensure_ascii=False), now_iso()),
            )

    con.commit()
    con.close()


@app.on_event("startup")
def _startup():
    init_db()
    ensure_default_data()


# -------------------------
# Auth
# -------------------------
def require_admin(x_admin_token: Optional[str]):
    # 토큰이 비어있으면 아예 관리자 기능 막기
    if not ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="ADMIN_TOKEN is not set on server.")
    if not x_admin_token or x_admin_token.strip() != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")


# -------------------------
# Schemas
# -------------------------
class StoreMetaUpdate(BaseModel):
    usage_text: str = ""
    categories: List[Dict[str, Any]] = Field(default_factory=list)


class ItemCreate(BaseModel):
    name: str
    current_qty: float = 0
    min_qty: float = 0
    unit: str = ""
    price: str = ""
    vendor: str = ""
    storage: str = ""
    origin: str = ""
    buy_link: str = ""
    memo: str = ""


class ItemUpdate(BaseModel):
    current_qty: float = 0
    min_qty: float = 0
    unit: str = ""
    price: str = ""
    vendor: str = ""
    storage: str = ""
    origin: str = ""
    buy_link: str = ""
    memo: str = ""


# -------------------------
# Routes
# -------------------------
@app.get("/")
def root():
    return {"ok": True, "service": SERVICE
