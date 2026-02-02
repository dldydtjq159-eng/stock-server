# =========================
# STOCK SERVER v6 (ALL-IN-ONE)
# 레시피 자동차감 + 발주이력 + 부족알림(이메일) 포함
# =========================
import os, json, sqlite3, re, smtplib
from email.mime.text import MIMEText
from datetime import datetime
from flask import Flask, request, jsonify

DB = "stock.db"

APP_EMAIL = "YOUR_GMAIL@gmail.com"
APP_PASSWORD = "qygd kavp wxia mptz"   # ← 네가 준 앱비번 사용

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "dldydtjq159")

app = Flask(__name__)

# -------- DB ----------
def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def init_db():
    c = db()
    cur = c.cursor()

    cur.executescript("""
    CREATE TABLE IF NOT EXISTS stores(
        id TEXT PRIMARY KEY,
        name TEXT,
        usage_text TEXT DEFAULT ''
    );

    CREATE TABLE IF NOT EXISTS categories(
        store_id TEXT,
        key TEXT,
        label TEXT,
        sort INTEGER,
        PRIMARY KEY(store_id, key)
    );

    CREATE TABLE IF NOT EXISTS items(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_id TEXT,
        category_key TEXT,
        name TEXT,
        current_stock REAL DEFAULT 0,
        min_stock REAL DEFAULT 0,
        unit TEXT DEFAULT '',
        price TEXT DEFAULT '',
        vendor TEXT DEFAULT '',
        storage TEXT DEFAULT '',
        origin TEXT DEFAULT '',
        buy_link TEXT DEFAULT '',
        memo TEXT DEFAULT '',
        updated_at TEXT
    );

    CREATE TABLE IF NOT EXISTS recipes(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_id TEXT,
        menu TEXT UNIQUE
    );

    CREATE TABLE IF NOT EXISTS recipe_items(
        recipe_id INTEGER,
        item_id INTEGER,
        qty REAL
    );

    CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_id TEXT,
        menu TEXT,
        count INTEGER,
        created_at TEXT
    );
    """)
    c.commit()
    c.close()

init_db()

# -------- 보안 ----------
def check_admin():
    token = request.headers.get("x-admin-token","")
    if token != ADMIN_TOKEN:
        return False
    return True

# -------- 이메일 알림 ----------
def send_email(subject, body):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = APP_EMAIL
    msg["To"] = APP_EMAIL

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(APP_EMAIL, APP_PASSWORD)
        s.sendmail(APP_EMAIL, APP_EMAIL, msg.as_string())

# -------- API ----------
@app.route("/api/stores", methods=["GET"])
def list_stores():
    c = db()
    rows = c.execute("SELECT * FROM stores").fetchall()
    c.close()
    return jsonify({"stores":[dict(r) for r in rows]})

@app.route("/api/stores/<sid>/meta", methods=["GET"])
def store_meta(sid):
    c = db()
    store = c.execute("SELECT * FROM stores WHERE id=?", (sid,)).fetchone()
    cats = c.execute("SELECT key,label,sort FROM categories WHERE store_id=? ORDER BY sort",(sid,)).fetchall()
    c.close()
    return jsonify({
        "meta":{
            "usage_text": store["usage_text"] if store else "",
            "categories":[dict(r) for r in cats]
        }
    })

@app.route("/api/stores/<sid>/meta", methods=["PUT"])
def update_meta(sid):
    if not check_admin():
        return jsonify({"error":"unauthorized"}),401

    data = request.json
    usage = data.get("usage_text","")
    cats = data.get("categories",[])

    c = db()
    c.execute("INSERT OR IGNORE INTO stores(id,name,usage_text) VALUES(?,?,?)",(sid,sid,usage))
    c.execute("UPDATE stores SET usage_text=? WHERE id=?",(usage,sid))
    c.execute("DELETE FROM categories WHERE store_id=?",(sid,))

    for i,cx in enumerate(cats):
        c.execute("""
        INSERT INTO categories(store_id,key,label,sort)
        VALUES(?,?,?,?)
        """,(sid,cx["key"],cx["label"],i*10))
    c.commit()
    c.close()
    return jsonify({"ok":True})

@app.route("/api/stores/<sid>/items/<cat>", methods=["GET"])
def items_list(sid,cat):
    c = db()
    rows = c.execute("""
      SELECT * FROM items 
      WHERE store_id=? AND category_key=?
      ORDER BY name
    """,(sid,cat)).fetchall()
    c.close()
    return jsonify({"items":[dict(r) for r in rows]})

@app.route("/api/stores/<sid>/items/<cat>", methods=["POST"])
def add_item(sid,cat):
    data = request.json
    name = data["name"]

    c = db()
    exists = c.execute("""
      SELECT 1 FROM items WHERE store_id=? AND category_key=? AND name=?
    """,(sid,cat,name)).fetchone()
    if exists:
        return jsonify({"error":"duplicate"}),409

    c.execute("""
      INSERT INTO items(store_id,category_key,name,current_stock,min_stock,unit,
        price,vendor,storage,origin,buy_link,memo,updated_at)
      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
    """,(
        sid,cat,name,
        data.get("current_stock",0),
        data.get("min_stock",0),
        data.get("unit",""),
        data.get("price",""),
        data.get("vendor",""),
        data.get("storage",""),
        data.get("origin",""),
        data.get("buy_link",""),
        data.get("memo",""),
        now()
    ))
    c.commit()
    c.close()
    return jsonify({"ok":True})

@app.route("/api/stores/<sid>/items/<cat>/<iid>", methods=["PUT"])
def update_item(sid,cat,iid):
    data = request.json
    c = db()
    c.execute("""
      UPDATE items SET
        current_stock=?,
        min_stock=?,
        unit=?,
        price=?,
        vendor=?,
        storage=?,
        origin=?,
        buy_link=?,
        memo=?,
        updated_at=?
      WHERE id=?
    """,(
        data.get("current_stock",0),
        data.get("min_stock",0),
        data.get("unit",""),
        data.get("price",""),
        data.get("vendor",""),
        data.get("storage",""),
        data.get("origin",""),
        data.get("buy_link",""),
        data.get("memo",""),
        now(),
        iid
    ))
    c.commit()
    c.close()
    return jsonify({"ok":True,"updated_at":now()})

@app.route("/api/stores/<sid>/items/<cat>/<iid>", methods=["DELETE"])
def delete_item(sid,cat,iid):
    c = db()
    c.execute("DELETE FROM items WHERE id=?",(iid,))
    c.commit()
    c.close()
    return jsonify({"ok":True})

# -------- 레시피 ----------
@app.route("/api/recipes", methods=["POST"])
def add_recipe():
    data = request.json
    menu = data["menu"]
    store_id = data["store_id"]
    items = data["items"]   # [{item_id, qty}]

    c = db()
    cur = c.cursor()
    cur.execute("INSERT INTO recipes(store_id,menu) VALUES(?,?)",(store_id,menu))
    rid = cur.lastrowid

    for it in items:
        cur.execute("""
        INSERT INTO recipe_items(recipe_id,item_id,qty)
        VALUES(?,?,?)
        """,(rid,it["item_id"],it["qty"]))

    c.commit()
    c.close()
    return jsonify({"ok":True})

# -------- 주문 → 자동 차감 ----------
@app.route("/api/recipes/use", methods=["POST"])
def use_recipe():
    data = request.json
    store_id = data["store_id"]
    menu = data["menu"]
    count = int(data["count"])

    c = db()
    cur = c.cursor()

    rid = cur.execute("SELECT id FROM recipes WHERE menu=?",(menu,)).fetchone()
    if not rid:
        return jsonify({"error":"recipe_not_found"}),404
    rid = rid["id"]

    rows = cur.execute("""
      SELECT i.id, i.current_stock, ri.qty, i.min_stock, i.name
      FROM recipe_items ri
      JOIN items i ON i.id = ri.item_id
      WHERE ri.recipe_id=?
    """,(rid,)).fetchall()

    shortage = []
    for r in rows:
        need = r["qty"] * count
        new_stock = r["current_stock"] - need
        cur.execute("""
          UPDATE items SET current_stock=?, updated_at=?
          WHERE id=?
        """,(new_stock,now(),r["id"]))

        if new_stock < r["min_stock"]:
            shortage.append(f"{r['name']} 부족 ({new_stock})")

    cur.execute("""
      INSERT INTO orders(store_id,menu,count,created_at)
      VALUES(?,?,?,?)
    """,(store_id,menu,count,now()))

    c.commit()
    c.close()

    if shortage:
        send_email("재고 부족 알림", "\n".join(shortage))

    return jsonify({"ok":True,"shortage":shortage})

@app.route("/api/shortages/<sid>", methods=["GET"])
def shortages(sid):
    c = db()
    rows = c.execute("""
      SELECT 
        c.label as category_label,
        i.name,
        i.current_stock,
        i.min_stock,
        (i.min_stock - i.current_stock) as need,
        i.unit,
        i.price,
        i.buy_link,
        i.category_key
      FROM items i
      LEFT JOIN categories c 
        ON c.store_id=i.store_id AND c.key=i.category_key
      WHERE i.current_stock < i.min_stock
    """,(sid,)).fetchall()
    c.close()
    return jsonify({"shortages":[dict(r) for r in rows]})

if __name__=="__main__":
    app.run(host="0.0.0.0", port=5000)
