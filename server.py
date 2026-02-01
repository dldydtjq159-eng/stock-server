from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from typing import List
import sqlite3, os, time

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "dldydtjq159")
DB_PATH = "/data/stock.db"

app = FastAPI()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def admin_check(token):
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

@app.get("/")
def root():
    return {"ok": True, "service": "stock-server", "version": "stable"}

# ---------- 매장 ----------
@app.get("/api/stores")
def stores():
    return {
        "stores": [
            {"id": "store1", "name": "김경영 요리연구소"},
            {"id": "store2", "name": "청년회관"},
        ]
    }

# ---------- 카테고리 ----------
@app.get("/api/categories/{store_id}")
def categories(store_id: str):
    db = get_db()
    db.execute(
        "CREATE TABLE IF NOT EXISTS categories (store TEXT, id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT)"
    )
    rows = db.execute(
        "SELECT id, name FROM categories WHERE store=?", (store_id,)
    ).fetchall()
    return {"categories": [dict(r) for r in rows]}

@app.post("/api/categories/{store_id}")
def add_category(store_id: str, data: dict, x_admin_token: str = Header("")):
    admin_check(x_admin_token)
    db = get_db()
    db.execute(
        "INSERT INTO categories (store, name) VALUES (?, ?)",
        (store_id, data["name"]),
    )
    db.commit()
    return {"ok": True}

# ---------- 품목 ----------
@app.get("/api/items/{store_id}/{cat_id}")
def items(store_id: str, cat_id: int):
    db = get_db()
    db.execute(
        """CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            store TEXT,
            category INTEGER,
            name TEXT,
            stock INTEGER DEFAULT 0,
            min_stock INTEGER DEFAULT 0
        )"""
    )
    rows = db.execute(
        "SELECT * FROM items WHERE store=? AND category=?",
        (store_id, cat_id),
    ).fetchall()
    return {"items": [dict(r) for r in rows]}

@app.post("/api/items/{store_id}/{cat_id}")
def add_item(store_id: str, cat_id: int, data: dict):
    db = get_db()
    db.execute(
        "INSERT INTO items (store, category, name) VALUES (?, ?, ?)",
        (store_id, cat_id, data["name"]),
    )
    db.commit()
    return {"ok": True}

# ---------- 부족목록 ----------
@app.get("/api/shortage/{store_id}")
def shortage(store_id: str):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM items WHERE store=? AND stock < min_stock",
        (store_id,),
    ).fetchall()

    result = []
    for r in rows:
        need = r["min_stock"] - r["stock"]
        result.append({
            "name": r["name"],
            "stock": r["stock"],
            "need": need,
            "category_name": "카테고리"
        })
    return {"shortage": result}
