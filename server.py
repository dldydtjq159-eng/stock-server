# ==============================
# STOCK SERVER (FastAPI)
# ==============================

import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import smtplib
from email.mime.text import MIMEText

APP_VERSION = "6.0"
SERVICE = "stock-server"

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "dldydtjq159").strip()
DATA_DIR = os.getenv("DATA_DIR", "/data").strip()
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "stock.db")

APP_EMAIL = os.getenv("APP_EMAIL", "dldydtjq159@naver.com").strip()
APP_PASSWORD = os.getenv("APP_PASSWORD", "").strip()

app = FastAPI(title=SERVICE, version=APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================
# ✅ 여기부터 중요 (404 해결 핵심)
# ==============================

@app.get("/")
def root():
    return {
        "ok": True,
        "service": SERVICE,
        "version": APP_VERSION,
        "hint": "use /ok/version or /version"
    }

@app.get("/ok/version")
def ok_version():
    return {
        "service": SERVICE,
        "version": APP_VERSION,
        "status": "running",
        "time": datetime.utcnow().isoformat()
    }

@app.get("/version")
def version():
    return {"version": APP_VERSION}

# ==============================
# DB 초기화
# ==============================

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        created_at TEXT NOT NULL
    )
    """)
    conn.commit()
    conn.close()

init_db()

# ==============================
# 모델
# ==============================

class Item(BaseModel):
    name: str
    quantity: int = Field(..., ge=0)

# ==============================
# CRUD API
# ==============================

@app.post("/items")
def create_item(item: Item):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.utcnow().isoformat()
    c.execute(
        "INSERT INTO items (name, quantity, created_at) VALUES (?, ?, ?)",
        (item.name, item.quantity, now),
    )
    conn.commit()
    conn.close()
    return {"message": "item created"}

@app.get("/items")
def list_items():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, name, quantity, created_at FROM items")
    rows = c.fetchall()
    conn.close()

    return [
        {"id": r[0], "name": r[1], "quantity": r[2], "created_at": r[3]}
        for r in rows
    ]

@app.delete("/items/{item_id}")
def delete_item(item_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return {"message": f"item {item_id} deleted"}
    
