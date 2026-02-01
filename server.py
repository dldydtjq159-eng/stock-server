import os
import json
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

SERVICE = "stock-server"
VERSION = "4.0"

# ✅ Railway Variables에서 ADMIN_TOKEN 설정 권장 (없으면 기본값 사용)
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "dldydtjq159")

# ✅ Railway 볼륨 Mount path를 /data 로 설정하면 영구 저장됨
DATA_DIR = os.getenv("DATA_DIR", "/data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "stock.db")

app = FastAPI(title=SERVICE)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DEFAULT_STORES = [
    {"id": "lab", "name": "김경영 요리 연구소"},
    {"id": "hall", "name": "청년회관"},
]

DEFAULT_CATEGORIES = [
    {"label": "닭", "key": "chicken"},

