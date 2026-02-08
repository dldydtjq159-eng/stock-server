import os
import json
import time
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from passlib.context import CryptContext
import jwt

# ============================================================
# ENV
# ============================================================
TOKEN_SECRET = os.environ.get("TOKEN_SECRET")
SUPERADMIN_ID = os.environ.get("SUPERADMIN_ID")
SUPERADMIN_PW = os.environ.get("SUPERADMIN_PW")

if not TOKEN_SECRET:
    raise RuntimeError("TOKEN_SECRET is required")
if not SUPERADMIN_ID or not SUPERADMIN_PW:
    raise RuntimeError("SUPERADMIN_ID/SUPERADMIN_PW are required")

JWT_ALG = "HS256"
JWT_TTL_SEC = 60 * 60 * 12  # 12h
pwd_ctx = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# ============================================================
# Storage (simple JSON file; Railway filesystem may be ephemeral)
# ============================================================
DATA_FILE = os.environ.get("DATA_FILE", "data.json")
ADMINS_FILE = os.environ.get("ADMINS_FILE", "admins.json")

def _read_json(path: str, default: Any):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except:
        pass
    return default

def _write_json(path: str, obj: Any):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def _ensure_files():
    if not os.path.exists(DATA_FILE):
        _write_json(DATA_FILE, {"stores": ["김경영 요리 연구소", "청년회관"], "byStore": {}, "lastSync": ""})
    if not os.path.exists(ADMINS_FILE):
        _write_json(ADMINS_FILE, {
            "superadmin": {"id": SUPERADMIN_ID, "pw_hash": pwd_ctx.hash(SUPERADMIN_PW)},
            "admins": []
        })
