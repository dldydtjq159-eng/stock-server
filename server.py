import os
import json
import socket
import ctypes
import traceback
import webbrowser
from datetime import datetime, timedelta

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import requests

# =========================
# 단일 실행(중복 실행 방지)
# =========================
LOCK_PORT = 48123

def ensure_single_instance():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", LOCK_PORT))
        s.listen(1)
        return s
    except OSError:
        messagebox.showinfo("이미 실행중", "재고관리 프로그램이 이미 실행 중입니다.\n(작업표시줄에서 찾아보세요)")
        raise SystemExit

# =========================
# 콘솔창 최소화(가능한 경우)
# =========================
def minimize_console():
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE
    except Exception:
        pass

# =========================
# 파일 경로
# =========================
APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(APP_DIR, "config.json")
SESSION_FILE = os.path.join(APP_DIR, "admin_session.json")

DEFAULT_CONFIG = {
    "server_url": "https://stock-server-production-ca7d.up.railway.app",
    "admin_token": "dldydtjq159",
    "last_store_id": "lab",
}

# 관리자 로그인(로컬 앱에서만)
ADMIN_ID = "dldydtjq159"
ADMIN_PW = "tkfkd4026"
SESSION_MINUTES = 30

APP_TITLE = "재고관리 (PC)"
FOOTER_MADE_BY = "만든이: by.용섭"
FOOTER_BUG = "버그제보: dldydtjq159@naver.com"

# =========================
# Helpers
# =========================
def normalize_server_url(url: str) -> str:
    url = (url or "").strip()
    return url[:-1] if url.endswith("/") else url

def load_config():
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        save_config(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)

    cfg.setdefault("server_url", DEFAULT_CONFIG["server_url"])
    cfg.setdefault("admin_token", DEFAULT_CONFIG["admin_token"])
    cfg.setdefault("last_store_id", DEFAULT_CONFIG["last_store_id"])
    cfg["server_url"] = normalize_server_url(cfg["server_url"])
    return cfg

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

def open_config_file():
    try:
        os.startfile(os.path.abspath(CONFIG_FILE))
    except Exception as e:
        messagebox.showerror("오류", str(e))

def desktop_path():
    return os.path.join(os.path.expanduser("~"), "Desktop")

def write_desktop_text(filename: str, content: str) -> str:
    path = os.path.join(desktop_path(), filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path

# =========================
# Admin session (persist)
# =========================
def session_load():
    if not os.path.exists(SESSION_FILE):
        return None
    try:
        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            s = json.load(f)
        exp = s.get("expires_at")
        if not exp:
            return None
        exp_dt = datetime.fromisoformat(exp)
        if datetime.now() <= exp_dt:
            return s
        return None
    except Exception:
        return None

def session_save():
    expires = datetime.now() + timedelta(minutes=SESSION_MINUTES)
    s = {"expires_at": expires.isoformat()}
    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)

def session_clear():
    try:
        if os.path.exists(SESSION_FILE):
            os.remove(SESSION_FILE)
    except Exception:
        pass

def is_admin_logged_in():
    return session_load() is not None

def admin_remaining_seconds():
    s = session_load()
    if not s:
        return 0
    exp_dt = datetime.fromisoformat(s["expires_at"])
    diff = exp_dt - datetime.now()
    return max(0, int(diff.total_seconds()))

# =========================
# API
# =========================
def api_get(cfg, path, timeout=20):
    url = f"{cfg['server_url']}{path}"
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return r.json()

def api_put_admin(cfg, path, payload, timeout=20):
    url = f"{cfg['server_url']}{path}"
    headers = {"x-admin-token": cfg["admin_token"]}
    r = requests.put(url, headers=headers, json=payload, timeout=timeout)
    if r.status_code == 401:
        raise RuntimeError("Unauthorized: ADMIN_TOKEN 확인")
    r.raise_for_status()
    return r.json()

def api_items_list(cfg, store_id, category_key):
    return api_get(cfg, f"/api/stores/{store_id}/items/{category_key}")

def api_items_add(cfg, store_id, category_key, payload):
    url = f"{cfg['server_url']}/api/stores/{store_id}/items/{category_key}"
    r = requests.post(url, json=payload, timeout=20)
    if r.status_code == 409:
        raise RuntimeError("이미 같은 이름의 품목이 있습니다.")
    r.raise_for_status()
    return r.json()

def api_items_update(cfg, store_id, category_key, item_id, payload):
    url = f"{cfg['server_url']}/api/stores/{store_id}/items/{category_key}/{item_id}"
    r = requests.put(url, json=payload, timeout=20)
    if r.status_code == 404:
        raise RuntimeError("수정 대상이 없습니다(404).")
    r.raise_for_status()
    return r.json()

def api_items_delete(cfg, store_id, category_key, item_id):
    url = f"{cfg['server_url']}/api/stores/{store_id}/items/{category_key}/{item_id}"
    r = requests.delete(url, timeout=20)
    if r.status_code == 404:
        raise RuntimeError("삭제 대상이 없습니다(404).")
    r.raise_for_status()
    return r.json()

def api_stores(cfg):
    return api_get(cfg, "/api/stores")

def api_store_meta(cfg, store_id):
    return api_get(cfg, f"/api/stores/{store_id}/meta")

def api_store_meta_update(cfg, store_id, usage_text, categories):
    payload = {"usage_text": usage_text, "categories": categories}
    return api_put_admin(cfg, f"/api/stores/{store_id}/meta", payload)

def api_shortages(cfg, store_id):
    return api_get(cfg, f"/api/shortages/{store_id}")

# =========================
# UI Theme
# =========================
BG = "#0b1220"
PANEL = "#0f1b33"
PANEL2 = "#13213a"
ACCENT = "#2d4cff"
DANGER = "#c0392b"
TEXT = "#e8eefc"
MUTED = "#9db1d6"
GOOD = "#7CFF9A"
WARN = "#ffcc66"

# =========================
# App
# =========================
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.cfg = load_config()

        self.title(APP_TITLE)
        self.geometry("1000x620")
        self.minsize(1000, 620)
        self.configure(bg=BG)

        self._setup_style()

        self.container = ttk.Frame(self)
        self.container.pack(fill="both", expand=True, padx=16, pady=16)

        self.current_store_id = self.cfg.get("last_store_id", "lab")
        self.current_store_name = ""
        self.meta = None

        self.shortage_win = None  # 부족목록 창 핸들

        self.after(100, self.show_store_select)
        self.after(1000, self._tick_admin)

    def _setup_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=TEXT, font=("Malgun Gothic", 10))
        style.configure("Title.TLabel", background=BG, foreground=TEXT, font=("Malgun Gothic", 18, "bold"))
        style.configure("Small.TLabel", background=BG, foreground=MUTED, font=("Malgun Gothic", 9))

        style.configure("Card.TFrame", background=PANEL, relief="flat")

        style.configure("Accent.TButton", font=("Malgun Gothic", 11, "bold"), padding=10)
        style.map("Accent.TButton", background=[("active", "#325cff"), ("!active", ACCENT)],
                  foreground=[("active", "white"), ("!active", "white")])

        style.configure("Ghost.TButton", font=("Malgun Gothic", 10, "bold"), padding=10)
        style.map("Ghost.TButton", background=[("active", PANEL2), ("!active", PANEL2)],
                  foreground=[("active", "white"), ("!active", "white")])

        style.configure("Danger.TButton", font=("Malgun Gothic", 10, "bold"), padding=10)
        style.map("Danger.TButton", background=[("active", "#d35454"), ("!active", DANGER)],
                  foreground=[("active", "white"), ("!active", "white")])

    def _tick_admin(self):
        # 세션 만료되면 자동 OFF
        if not is_admin_logged_in():
            pass
        self.after(1000, self._tick_admin)

    def clear(self):
        # 화면 이동할 때 부족목록 창은 자동 닫기(요청사항)
        self.close_shortage_if_open()

        for w in self.container.winfo_children():
            w.destroy()

    def close_shortage_if_open(self):
        try:
            if self.shortage_win and self.shortage_win.winfo_exists():
                self.shortage_win.destroy()
        except Exception:
            pass
        self.shortage_win = None

    def show_store_select(self):
        self.clear()
        StoreSelectFrame(self.container, self).pack(fill="both", expand=True)

    def show_categories(self, store_id, store_name):
        self.current_store_id = store_id
        self.current_store_name = store_name
        self.cfg["last_store_id"] = store_id
        save_config(self.cfg)

        try:
            self.meta = api_store_meta(self.cfg, store_id)["meta"]
        except Exception as e:
            messagebox.showerror("서버 연결 실패", str(e))
            self.show_store_select()
            return

        self.clear()
        CategoriesFrame(self.container, self).pack(fill="both", expand=True)

    def show_items(self, category_key, category_label):
        self.clear()
        ItemsFrame(self.container, self, category_key, category_label).pack(fill="both", expand=True)

    def admin_login_dialog(self):
        d = AdminLoginDialog(self)
        self.wait_window(d)
        # 로그인 후 화면 갱신
        # 현재가 카테고리/매장선택이면 즉시 반영
        self.refresh_current_screen()

    def refresh_current_screen(self):
        # 현재 화면이 어떤 프레임인지 확인해서 새로고침
        children = self.container.winfo_children()
        if not children:
            self.show_store_select()
            return
        f = children[0]
        if isinstance(f, CategoriesFrame):
            self.show_categories(self.current_store_id, self.current_store_name)
        elif isinstance(f, StoreSelectFrame):
            self.show_store_select()
        else:
            # items 화면이면 카테고리로 이동 (안전)
            self.show_categories(self.current_store_id, self.current_store_name)

    def open_shortages(self):
        # 부족목록 창 이미 있으면 앞으로
        try:
            if self.shortage_win and self.shortage_win.winfo_exists():
                self.shortage_win.lift()
                return
        except Exception:
            pass

        self.shortage_win = ShortageWindow(self)

# =========================
# Frames
# =========================
class TopBar(ttk.Frame):
    def __init__(self, parent, app: App, title: str):
        super().__init__(parent)
        self.app = app

        left = ttk.Frame(self)
        left.pack(side="left", fill="x", expand=True)

        ttk.Label(left, text=title, style="Title.TLabel").pack(side="left")

        self.admin_label = ttk.Label(left, text="", foreground=GOOD, font=("Malgun Gothic", 10, "bold"))
        self.admin_label.pack(side="left", padx=12)

        right = ttk.Frame(self)
        right.pack(side="right")

        ttk.Button(right, text="부족목록", style="Accent.TButton", command=self.app.open_shortages).pack(side="left", padx=6)
        ttk.Button(right, text="매장선택", style="Ghost.TButton", command=self.app.show_store_select).pack(side="left", padx=6)

        if is_admin_logged_in():
            ttk.Button(right, text="로그아웃", style="Danger.TButton", command=self.logout).pack(side="left", padx=6)
        else:
            ttk.Button(right, text="관리자 로그인", style="Ghost.TButton", command=self.app.admin_login_dialog).pack(side="left", padx=6)

        ttk.Button(right, text="종료", style="Danger.TButton", command=self.app.destroy).pack(side="left", padx=6)

        self._tick()

    def logout(self):
        session_clear()
        messagebox.showinfo("로그아웃", "관리자 로그아웃 완료!")
        self.app.refresh_current_screen()

    def _tick(self):
        if is_admin_logged_in():
            rem = admin_remaining_seconds()
            self.admin_label.config(text=f"관리자: ON (남은시간 {rem//60:02d}:{rem%60:02d})")
            if rem <= 0:
                session_clear()
                self.app.refresh_current_screen()
        else:
            self.admin_label.config(text="관리자: OFF")
        self.after(1000, self._tick)


class StoreSelectFrame(ttk.Frame):
    def __init__(self, parent, app: App):
        super().__init__(parent)
        self.app = app

        TopBar(self, app, "매장 선택").pack(fill="x", pady=(0, 12))

        card = ttk.Frame(self, style="Card.TFrame")
        card.pack(fill="both", expand=True)

        wrap = ttk.Frame(card)
        wrap.pack(fill="both", expand=True, padx=14, pady=14)

        ttk.Label(wrap, text="매장을 클릭하면 재고 관리가 시작됩니다.", font=("Malgun Gothic", 12, "bold")).pack(anchor="w", pady=(0, 12))

        # stores
        try:
            stores = api_stores(self.app.cfg)["stores"]
        except Exception as e:
            messagebox.showerror("서버 연결 실패", str(e))
            stores = []

        # ✅ 혹시 서버가 꼬여서 중복 오면 여기서도 방어
        uniq = []
        seen = set()
        for st in stores:
            if st["id"] in seen:
                continue
            seen.add(st["id"])
            uniq.append(st)

        for st in uniq:
            btn = ttk.Button(
                wrap,
                text=f"▶  {st['name']}",
                style="Accent.TButton",
                command=lambda sid=st["id"], name=st["name"]: self.app.show_categories(sid, name)
            )
            btn.pack(fill="x", pady=8, ipady=10)

        ttk.Label(wrap, text=f"{FOOTER_MADE_BY}   |   {FOOTER_BUG}", style="Small.TLabel").pack(anchor="w", pady=(18, 0))


class CategoriesFrame(ttk.Frame):
    def __init__(self, parent, app: App):
        super().__init__(parent)
        self.app = app

        TopBar(self, app, f"식재료 | {self.app.current_store_name}").pack(fill="x", pady=(0, 12))

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)

        left = ttk.Frame(body, style="Card.TFrame")
        left.pack(side="left", fill="y", padx=(0, 12))

        right = ttk.Frame(body, style="Card.TFrame")
        right.pack(side="right", fill="both", expand=True)

        # 카테고리 목록(스크롤)
        ttk.Label(left, text="카테고리", font=("Malgun Gothic", 12, "bold"), background=PANEL, foreground=TEXT).pack(anchor="w", padx=12, pady=(12, 8))

        canvas = tk.Canvas(left, bg=PANEL, highlightthickness=0)
        canvas.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=(0, 10))
        sb = ttk.Scrollbar(left, orient="vertical", command=canvas.yview)
        sb.pack(side="right", fill="y", padx=(0, 10), pady=(0, 10))
        canvas.configure(yscrollcommand=sb.set)

        inner = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=inner, anchor="nw")

        def on_configure(_):
            canvas.configure(scrollregion=canvas.bbox("all"))
        inner.bind("<Configure>", on_configure)

        cats = (self.app.meta or {}).get("categories", [])
        cats = sorted(cats, key=lambda x: (x.get("sort", 0), x.get("label", "")))

        for c in cats:
            b = ttk.Button(inner, text=c["label"], style="Ghost.TButton",
                           command=lambda k=c["key"], l=c["label"]: self.app.show_items(k, l))
            b.pack(fill="x", pady=6, ipady=8)

        # 관리자 전용 버튼
        if is_admin_logged_in():
            ttk.Separator(inner).pack(fill="x", pady=10)
            ttk.Button(inner, text="카테고리 편집(관리자)", style="Accent.TButton", command=self.open_category_editor).pack(fill="x", pady=6, ipady=8)
            ttk.Button(inner, text="사용문구 편집(관리자)", style="Accent.TButton", command=self.open_usage_editor).pack(fill="x", pady=6, ipady=8)
            ttk.Button(inner, text="config.json 열기", style="Ghost.TButton", command=open_config_file).pack(fill="x", pady=6, ipady=8)

        # 사용방법 패널
        ttk.Label(right, text="사용방법", font=("Malgun Gothic", 12, "bold"), background=PANEL, foreground=TEXT).pack(anchor="w", padx=12, pady=(12, 8))

        usage = (self.app.meta or {}).get("usage_text", "")

        txt = tk.Text(right, wrap="word", bg=PANEL2, fg=TEXT, insertbackground=TEXT, relief="flat", font=("Malgun Gothic", 11))
        txt.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        txt.insert("1.0", usage)
        txt.config(state="disabled")

        ttk.Label(right, text=f"{FOOTER_MADE_BY}   |   {FOOTER_BUG}", style="Small.TLabel", background=PANEL).pack(anchor="w", padx=12, pady=(0, 12))

    def open_usage_editor(self):
        if not is_admin_logged_in():
            return
        UsageEditorDialog(self.app)

    def open_category_editor(self):
        if not is_admin_logged_in():
            return
        CategoryEditorDialog(self.app)


class ItemsFrame(ttk.Frame):
    def __init__(self, parent, app: App, category_key: str, category_label: str):
        super().__init__(parent)
        self.app = app
        self.category_key = category_key
        self.category_label = category_label

        TopBar(self, app, f"{self.app.current_store_name} | {category_label}").pack(fill="x", pady=(0, 12))

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)

        left = ttk.Frame(body, style="Card.TFrame")
        left.pack(side="left", fill="both", expand=True, padx=(0, 12))

        right = ttk.Frame(body, style="Card.TFrame")
        right.pack(side="right", fill="both", expand=True)

        # 왼쪽 목록
        ttk.Label(left, text="품목 목록", font=("Malgun Gothic", 12, "bold"), background=PANEL, foreground=TEXT).pack(anchor="w", padx=12, pady=(12, 8))

        self.search_var = tk.StringVar()
        search_entry = tk.Entry(left, textvariable=self.search_var, font=("Malgun Gothic", 11),
                                bg=PANEL2, fg=TEXT, insertbackground=TEXT, relief="flat")
        search_entry.pack(fill="x", padx=12, pady=(0, 8), ipady=6)
        search_entry.bind("<KeyRelease>", lambda e: self.apply_filter())

        self.listbox = tk.Listbox(left, font=("Malgun Gothic", 11), bg=PANEL2, fg=TEXT,
                                  selectbackground=ACCENT, relief="flat", highlightthickness=0)
        self.listbox.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        self.listbox.bind("<<ListboxSelect>>", self.on_select)

        btnrow = ttk.Frame(left, style="Card.TFrame")
        btnrow.pack(fill="x", padx=12, pady=(0, 12))

        ttk.Button(btnrow, text="추가", style="Accent.TButton", command=self.add_item).pack(side="left", fill="x", expand=True, padx=4, ipady=6)
        ttk.Button(btnrow, text="삭제", style="Danger.TButton", command=self.delete_item).pack(side="left", fill="x", expand=True, padx=4, ipady=6)
        ttk.Button(btnrow, text="새로고침", style="Ghost.TButton", command=self.refresh_list).pack(side="left", fill="x", expand=True, padx=4, ipady=6)

        # 오른쪽 상세
        ttk.Label(right, text="선택 품목 상세", font=("Malgun Gothic", 12, "bold"), background=PANEL, foreground=TEXT).pack(anchor="w", padx=12, pady=(12, 8))

        self.selected_name = ttk.Label(right, text="(왼쪽에서 품목을 선택하세요)", style="Small.TLabel", background=PANEL)
        self.selected_name.pack(anchor="w", padx=12, pady=(0, 10))

        form = ttk.Frame(right, style="Card.TFrame")
        form.pack(fill="both", expand=False, padx=12, pady=(0, 12))

        self.entries = {}
        self._row(form, "현재고", "current_stock", "숫자 입력 (예: 3)")
        self._row(form, "최소수량", "min_stock", "숫자 입력 (예: 2)  |  최소보다 적으면 부족목록에 표시")
        self._row(form, "단위", "unit", "예: 개 / kg / L")

        self._row(form, "가격", "price", "예: 1kg 6,500원 / 박스 28,000원")
        self._row(form, "구매처", "vendor", "예: ○○축산 / ○○마트")
        self._row(form, "보관", "storage", "예: 냉동 -18℃ / 상온")
        self._row(form, "원산지", "origin", "예: 국내산 / 브라질산")

        # 구매링크 + 바로가기 버튼
        link_row = ttk.Frame(form, style="Card.TFrame")
        link_row.pack(fill="x", pady=6)
        ttk.Label(link_row, text="구매링크", width=10, font=("Malgun Gothic", 10, "bold"),
                  background=PANEL, foreground=TEXT).pack(side="left")
        ent = tk.Entry(link_row, font=("Malgun Gothic", 11), bg=PANEL2, fg=TEXT,
                       insertbackground=TEXT, relief="flat")
        ent.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 8))
        self.entries["buy_link"] = ent
        ttk.Button(link_row, text="바로가기", style="Ghost.TButton", command=self.open_link).pack(side="left")

        self._row(form, "메모", "memo", "예: 소분 필요 / 유통기한 확인")

        self.status = ttk.Label(right, text="", style="Small.TLabel", background=PANEL)
        self.status.pack(anchor="w", padx=12, pady=(0, 10))

        save_row = ttk.Frame(right, style="Card.TFrame")
        save_row.pack(fill="x", padx=12, pady=(0, 12))
        ttk.Button(save_row, text="저장", style="Accent.TButton", command=self.save_selected).pack(side="left", fill="x", expand=True, padx=4, ipady=10)
        ttk.Button(save_row, text="카테고리로", style="Ghost.TButton",
                   command=lambda: self.app.show_categories(self.app.current_store_id, self.app.current_store_name)).pack(side="left", fill="x", expand=True, padx=4, ipady=10)

        self.items_all = []
        self.items_view = []
        self.selected_item = None

        self.refresh_list()

    def _row(self, parent, label, key, hint):
        row = ttk.Frame(parent, style="Card.TFrame")
        row.pack(fill="x", pady=6)
        ttk.Label(row, text=label, width=10, font=("Malgun Gothic", 10, "bold"),
                  background=PANEL, foreground=TEXT).pack(side="left")
        ent = tk.Entry(row, font=("Malgun Gothic", 11), bg=PANEL2, fg=TEXT,
                       insertbackground=TEXT, relief="flat")
        ent.pack(side="left", fill="x", expand=True, ipady=6)
        self.entries[key] = ent

        hint_label = ttk.Label(parent, text=hint, style="Small.TLabel", background=PANEL)
        hint_label.pack(anchor="w", padx=92)

    def open_link(self):
        url = (self.entries.get("buy_link").get() or "").strip()
        if not url:
            messagebox.showinfo("구매링크", "구매링크가 비어있습니다.")
            return
        if not (url.startswith("http://") or url.startswith("https://")):
            url = "https://" + url
        webbrowser.open(url)

    def refresh_list(self, keep_id=None):
        try:
            res = api_items_list(self.app.cfg, self.app.current_store_id, self.category_key)
            self.items_all = res.get("items", [])
            self.apply_filter(keep_id=keep_id)
            self.status.config(text="목록 불러오기 완료 ✅")
        except Exception as e:
            self.status.config(text="목록 불러오기 실패 ❌")
            messagebox.showerror("오류", str(e))

    def apply_filter(self, keep_id=None):
        q = (self.search_var.get() or "").strip().lower()
        if q:
            self.items_view = [it for it in self.items_all if q in (it.get("name","").lower())]
        else:
            self.items_view = list(self.items_all)

        self.listbox.delete(0, tk.END)
        for it in self.items_view:
            self.listbox.insert(tk.END, it["name"])

        # 선택 유지
        self.selected_item = None
        if keep_id:
            for idx, it in enumerate(self.items_view):
                if it["id"] == keep_id:
                    self.listbox.selection_set(idx)
                    self.listbox.see(idx)
                    self.selected_item = it
                    self.fill_form(it)
                    break
        else:
            self.clear_form()

    def clear_form(self):
        self.selected_name.config(text="(왼쪽에서 품목을 선택하세요)")
        for k in self.entries:
            self.entries[k].delete(0, tk.END)

    def fill_form(self, it):
        self.selected_name.config(text=f"선택: {it.get('name','')}")
        for k in self.entries:
            self.entries[k].delete(0, tk.END)
            self.entries[k].insert(0, str(it.get(k, "") or ""))
        self.status.config(text=f"선택 완료 · {it.get('updated_at','')}")

    def on_select(self, _evt=None):
        idxs = self.listbox.curselection()
        if not idxs:
            return
        idx = idxs[0]
        if idx < 0 or idx >= len(self.items_view):
            return
        self.selected_item = self.items_view[idx]
        self.fill_form(self.selected_item)

    def add_item(self):
        name = simpledialog.askstring("품목 추가", f"[{self.category_label}]에 추가할 품목명을 입력하세요.")
        if not name:
            return
        name = name.strip()
        if not name:
            return
        try:
            api_items_add(self.app.cfg, self.app.current_store_id, self.category_key, {
                "name": name,
                "current_stock": 0,
                "min_stock": 0,
                "unit": "",
                "price": "",
                "vendor": "",
                "storage": "",
                "origin": "",
                "buy_link": "",
                "memo": ""
            })
            self.refresh_list()
            messagebox.showinfo("추가 완료", f"'{name}' 추가했습니다.")
        except Exception as e:
            messagebox.showerror("추가 실패", str(e))

    def delete_item(self):
        if not self.selected_item:
            messagebox.showinfo("삭제", "삭제할 품목을 먼저 선택하세요.")
            return
        name = self.selected_item["name"]
        if not messagebox.askyesno("삭제 확인", f"'{name}' 삭제할까요?"):
            return
        try:
            api_items_delete(self.app.cfg, self.app.current_store_id, self.category_key, self.selected_item["id"])
            self.refresh_list()
            messagebox.showinfo("삭제 완료", f"'{name}' 삭제했습니다.")
        except Exception as e:
            messagebox.showerror("삭제 실패", str(e))

    def save_selected(self):
        if not self.selected_item:
            messagebox.showinfo("저장", "저장할 품목을 먼저 선택하세요.")
            return
        payload = {}
        for k in self.entries:
            payload[k] = self.entries[k].get().strip()

        try:
            res = api_items_update(self.app.cfg, self.app.current_store_id, self.category_key, self.selected_item["id"], payload)
            self.status.config(text=f"저장 완료 ✅ · {res.get('updated_at','')}")
            self.refresh_list(keep_id=self.selected_item["id"])
            messagebox.showinfo("저장", "서버에 저장했습니다. 다른 PC에서도 동일하게 보입니다!")
        except Exception as e:
            self.status.config(text="저장 실패 ❌")
            messagebox.showerror("저장 실패", str(e))


# =========================
# 부족목록 창
# =========================
class ShortageWindow(tk.Toplevel):
    def __init__(self, app: App):
        super().__init__(app)
        self.app = app
        self.title(f"부족목록 | {app.current_store_name}")
        self.geometry("900x520")
        self.configure(bg=BG)
        self.resizable(True, True)

        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True, padx=14, pady=14)

        top = ttk.Frame(frame)
        top.pack(fill="x", pady=(0, 10))

        ttk.Label(top, text="부족목록", style="Title.TLabel").pack(side="left")
        ttk.Button(top, text="닫기", style="Danger.TButton", command=self.on_close).pack(side="right")

        # list
        cols = ("sel", "category", "name", "current", "min", "need", "price", "link")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings", height=14)
        self.tree.heading("sel", text="선택")
        self.tree.heading("category", text="카테고리")
        self.tree.heading("name", text="품목")
        self.tree.heading("current", text="현재고")
        self.tree.heading("min", text="최소")
        self.tree.heading("need", text="부족")
        self.tree.heading("price", text="가격")
        self.tree.heading("link", text="구매링크")

        self.tree.column("sel", width=60, anchor="center")
        self.tree.column("category", width=120)
        self.tree.column("name", width=170)
        self.tree.column("current", width=80, anchor="e")
        self.tree.column("min", width=80, anchor="e")
        self.tree.column("need", width=80, anchor="e")
        self.tree.column("price", width=150)
        self.tree.column("link", width=160)

        self.tree.pack(fill="both", expand=True)

        bottom = ttk.Frame(frame)
        bottom.pack(fill="x", pady=(10, 0))

        ttk.Button(bottom, text="전체 선택", style="Ghost.TButton", command=self.select_all).pack(side="left", padx=4)
        ttk.Button(bottom, text="전체 해제", style="Ghost.TButton", command=self.unselect_all).pack(side="left", padx=4)

        ttk.Button(bottom, text="발주서 저장(바탕화면)", style="Accent.TButton", command=self.save_order).pack(side="right", padx=4)
        ttk.Button(bottom, text="구매링크 열기", style="Accent.TButton", command=self.open_selected_link).pack(side="right", padx=4)
        ttk.Button(bottom, text="정보 가져오기(메모장)", style="Ghost.TButton", command=self.export_notepad).pack(side="right", padx=4)

        self.data = []
        self.checked = set()

        self.load()

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_close(self):
        # ✅ 닫아도 현재 페이지 유지: 그냥 창만 닫기
        self.app.shortage_win = None
        self.destroy()

    def load(self):
        try:
            res = api_shortages(self.app.cfg, self.app.current_store_id)
            self.data = res.get("shortages", [])
        except Exception as e:
            messagebox.showerror("부족목록 오류", str(e))
            self.data = []

        self.tree.delete(*self.tree.get_children())

        for i, s in enumerate(self.data):
            iid = f"row{i}"
            self.tree.insert("", "end", iid=iid, values=(
                "□",
                s.get("category_label", ""),
                s.get("name", ""),
                self._fmt_num(s.get("current_stock", 0), s.get("unit","")),
                self._fmt_num(s.get("min_stock", 0), s.get("unit","")),
                self._fmt_num(s.get("need", 0), s.get("unit","")),
                s.get("price",""),
                (s.get("buy_link","") or "")[:30]
            ))

        self.tree.bind("<Double-1>", self.on_double_click)
        self.tree.bind("<Button-1>", self.on_click_toggle)

    def _fmt_num(self, n, unit):
        try:
            n = float(n)
            if n.is_integer():
                n = int(n)
        except Exception:
            pass
        unit = unit or ""
        return f"{n}{unit}"

    def on_click_toggle(self, event):
        # 클릭한 행의 '선택' 칸 누르면 토글
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        col = self.tree.identify_column(event.x)
        row = self.tree.identify_row(event.y)
        if not row:
            return
        if col != "#1":  # sel
            return

        idx = int(row.replace("row", ""))
        if idx in self.checked:
            self.checked.remove(idx)
            vals = list(self.tree.item(row, "values"))
            vals[0] = "□"
            self.tree.item(row, values=vals)
        else:
            self.checked.add(idx)
            vals = list(self.tree.item(row, "values"))
            vals[0] = "■"
            self.tree.item(row, values=vals)

    def on_double_click(self, event):
        # 더블클릭: 해당 카테고리로 이동 + 품목 리스트 열기
        row = self.tree.identify_row(event.y)
        if not row:
            return
        idx = int(row.replace("row", ""))
        s = self.data[idx]
        cat_key = s.get("category_key")
        cat_label = s.get("category_label")

        # 부족목록 창 자동 닫기(요청사항)
        self.on_close()

        # 카테고리 화면/아이템 화면으로 이동
        self.app.show_items(cat_key, cat_label)

    def select_all(self):
        self.checked = set(range(len(self.data)))
        for row in self.tree.get_children():
            vals = list(self.tree.item(row, "values"))
            vals[0] = "■"
            self.tree.item(row, values=vals)

    def unselect_all(self):
        self.checked = set()
        for row in self.tree.get_children():
            vals = list(self.tree.item(row, "values"))
            vals[0] = "□"
            self.tree.item(row, values=vals)

    def selected_rows(self):
        if not self.checked:
            return []
        return [self.data[i] for i in sorted(self.checked)]

    def export_notepad(self):
        rows = self.selected_rows() or self.data
        if not rows:
            messagebox.showinfo("정보", "부족 항목이 없습니다.")
            return

        text = self._make_text(rows)
        # 바탕화면에 임시 파일 생성 후 메모장 열기
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"부족목록_{self.app.current_store_name}_{ts}.txt"
        path = write_desktop_text(filename, text)
        try:
            os.startfile(path)  # 메모장으로 열림
        except Exception:
            messagebox.showinfo("저장됨", f"바탕화면에 저장 완료:\n{path}")

    def save_order(self):
        rows = self.selected_rows() or self.data
        if not rows:
            messagebox.showinfo("발주서", "부족 항목이 없습니다.")
            return

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        text = self._make_text(rows, header=f"[발주서] {self.app.current_store_name}  |  저장시간: {ts}")

        fn_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"발주서_{self.app.current_store_name}_{fn_ts}.txt"
        path = write_desktop_text(filename, text)
        messagebox.showinfo("발주서 저장", f"바탕화면에 저장했습니다.\n\n{path}")

    def open_selected_link(self):
        rows = self.selected_rows()
        if not rows:
            messagebox.showinfo("구매링크", "체크된 항목이 없습니다.\n(왼쪽 선택칸 체크 후 사용)")
            return
        # 첫 번째 유효 링크 열기
        for r in rows:
            url = (r.get("buy_link") or "").strip()
            if url:
                if not (url.startswith("http://") or url.startswith("https://")):
                    url = "https://" + url
                webbrowser.open(url)
                return
        messagebox.showinfo("구매링크", "선택된 항목에 구매링크가 없습니다.")

    def _make_text(self, rows, header=None):
        header = header or f"[부족목록] {self.app.current_store_name}  |  생성시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        lines = [header, ""]
        lines.append("카테고리\t품목\t현재고\t최소\t부족\t가격\t구매링크")
        for r in rows:
            lines.append(
                f"{r.get('category_label','')}\t{r.get('name','')}\t"
                f"{r.get('current_stock',0)}{r.get('unit','')}\t"
                f"{r.get('min_stock',0)}{r.get('unit','')}\t"
                f"{r.get('need',0)}{r.get('unit','')}\t"
                f"{r.get('price','')}\t{r.get('buy_link','')}"
            )
        return "\n".join(lines)

# =========================
# Dialogs
# =========================
class AdminLoginDialog(tk.Toplevel):
    def __init__(self, app: App):
        super().__init__(app)
        self.app = app
        self.title("관리자 로그인")
        self.geometry("380x220")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.grab_set()

        ttk.Label(self, text="관리자 로그인", style="Title.TLabel").pack(pady=(14, 6))

        frm = ttk.Frame(self)
        frm.pack(fill="x", padx=18, pady=10)

        ttk.Label(frm, text="아이디", font=("Malgun Gothic", 10, "bold")).grid(row=0, column=0, sticky="w", pady=6)
        self.e_id = tk.Entry(frm, font=("Malgun Gothic", 11), bg=PANEL2, fg=TEXT, insertbackground=TEXT, relief="flat")
        self.e_id.grid(row=0, column=1, sticky="ew", padx=10)

        ttk.Label(frm, text="비번", font=("Malgun Gothic", 10, "bold")).grid(row=1, column=0, sticky="w", pady=6)
        self.e_pw = tk.Entry(frm, show="*", font=("Malgun Gothic", 11), bg=PANEL2, fg=TEXT, insertbackground=TEXT, relief="flat")
        self.e_pw.grid(row=1, column=1, sticky="ew", padx=10)

        frm.columnconfigure(1, weight=1)

        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=18, pady=12)
        ttk.Button(btns, text="로그인", style="Accent.TButton", command=self.do_login).pack(side="left", fill="x", expand=True, ipady=8, padx=4)
        ttk.Button(btns, text="취소", style="Ghost.TButton", command=self.destroy).pack(side="left", fill="x", expand=True, ipady=8, padx=4)

        ttk.Label(self, text="로그인 성공 시 30분 유지 (프로그램 껐다 켜도 유지)", style="Small.TLabel").pack(pady=(0, 10))

    def do_login(self):
        uid = self.e_id.get().strip()
        pw = self.e_pw.get().strip()
        if uid == ADMIN_ID and pw == ADMIN_PW:
            session_save()
            messagebox.showinfo("성공", "관리자 로그인 성공! (30분 유지)")
            self.destroy()
        else:
            messagebox.showerror("실패", "아이디 또는 비밀번호가 틀립니다.")

class UsageEditorDialog(tk.Toplevel):
    def __init__(self, app: App):
        super().__init__(app)
        self.app = app
        self.cfg = app.cfg

        self.title("사용문구 편집 (관리자)")
        self.geometry("720x520")
        self.configure(bg=BG)
        self.grab_set()

        ttk.Label(self, text=f"사용문구 편집 | {app.current_store_name}", style="Title.TLabel").pack(pady=(14, 8))

        self.text = tk.Text(self, wrap="word", bg=PANEL2, fg=TEXT, insertbackground=TEXT, relief="flat", font=("Malgun Gothic", 11))
        self.text.pack(fill="both", expand=True, padx=14, pady=10)

        usage = (app.meta or {}).get("usage_text", "")
        self.text.insert("1.0", usage)

        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=14, pady=12)
        ttk.Button(btns, text="저장", style="Accent.TButton", command=self.save).pack(side="left", fill="x", expand=True, ipady=10, padx=4)
        ttk.Button(btns, text="닫기", style="Ghost.TButton", command=self.destroy).pack(side="left", fill="x", expand=True, ipady=10, padx=4)

    def save(self):
        try:
            usage_text = self.text.get("1.0", "end").rstrip()
            cats = (self.app.meta or {}).get("categories", [])
            api_store_meta_update(self.cfg, self.app.current_store_id, usage_text, cats)
            messagebox.showinfo("저장", "사용문구 저장 완료! 다른 PC에도 자동 반영됩니다.")
            self.app.meta = api_store_meta(self.cfg, self.app.current_store_id)["meta"]
        except Exception as e:
            messagebox.showerror("저장 실패", str(e))

class CategoryEditorDialog(tk.Toplevel):
    def __init__(self, app: App):
        super().__init__(app)
        self.app = app
        self.cfg = app.cfg

        self.title("카테고리 편집 (관리자)")
        self.geometry("760x560")
        self.configure(bg=BG)
        self.grab_set()

        ttk.Label(self, text=f"카테고리 편집 | {app.current_store_name}", style="Title.TLabel").pack(pady=(14, 8))

        self.cats = sorted((app.meta or {}).get("categories", []), key=lambda x: (x.get("sort", 0), x.get("label", "")))

        main = ttk.Frame(self)
        main.pack(fill="both", expand=True, padx=14, pady=10)

        self.tree = ttk.Treeview(main, columns=("key", "label", "sort"), show="headings", height=14)
        self.tree.heading("key", text="key(고정ID)")
        self.tree.heading("label", text="표시이름")
        self.tree.heading("sort", text="순서")
        self.tree.column("key", width=200)
        self.tree.column("label", width=360)
        self.tree.column("sort", width=100, anchor="center")
        self.tree.pack(fill="both", expand=True)

        for c in self.cats:
            self.tree.insert("", "end", values=(c["key"], c["label"], c.get("sort", 0)))

        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=14, pady=10)

        ttk.Button(btns, text="추가", style="Accent.TButton", command=self.add_cat).pack(side="left", padx=4, ipady=8)
        ttk.Button(btns, text="이름수정", style="Accent.TButton", command=self.edit_label).pack(side="left", padx=4, ipady=8)
        ttk.Button(btns, text="순서변경", style="Accent.TButton", command=self.edit_sort).pack(side="left", padx=4, ipady=8)
        ttk.Button(btns, text="삭제", style="Danger.TButton", command=self.delete_cat).pack(side="left", padx=4, ipady=8)

        b2 = ttk.Frame(self)
        b2.pack(fill="x", padx=14, pady=12)
        ttk.Button(b2, text="저장(전체 반영)", style="Accent.TButton", command=self.save_all).pack(side="left", fill="x", expand=True, ipady=10, padx=4)
        ttk.Button(b2, text="닫기", style="Ghost.TButton", command=self.destroy).pack(side="left", fill="x", expand=True, ipady=10, padx=4)

        ttk.Label(self, text="※ key는 데이터 분류용 ID입니다. 보통 label/순서만 바꾸는 걸 추천합니다.", style="Small.TLabel").pack(anchor="w", padx=16, pady=(0, 10))

    def _selected(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return sel[0]

    def add_cat(self):
        label = simpledialog.askstring("카테고리 추가", "카테고리 이름을 입력하세요.\n예) 포장재, 음료 등")
        if not label:
            return
        label = label.strip()
        if not label:
            return
        # key는 자동 생성
        key = "cat" + datetime.now().strftime("%H%M%S")
        sort = len(self.tree.get_children()) * 10
        self.tree.insert("", "end", values=(key, label, sort))

    def edit_label(self):
        it = self._selected()
        if not it:
            return
        key, label, sort = self.tree.item(it, "values")
        new_label = simpledialog.askstring("이름 수정", f"'{label}' → 새 이름")
        if not new_label:
            return
        new_label = new_label.strip()
        if not new_label:
            return
        self.tree.item(it, values=(key, new_label, sort))

    def edit_sort(self):
        it = self._selected()
        if not it:
            return
        key, label, sort = self.tree.item(it, "values")
        new_sort = simpledialog.askinteger("순서 변경", f"'{label}' 순서를 숫자로 입력\n(작을수록 위)", initialvalue=int(sort))
        if new_sort is None:
            return
        self.tree.item(it, values=(key, label, int(new_sort)))

    def delete_cat(self):
        it = self._selected()
        if not it:
            return
        key, label, sort = self.tree.item(it, "values")
        if messagebox.askyesno("삭제", f"'{label}' 카테고리를 삭제할까요?"):
            self.tree.delete(it)

    def save_all(self):
        try:
            cats = []
            for it in self.tree.get_children():
                key, label, sort = self.tree.item(it, "values")
                cats.append({"key": key, "label": label, "sort": int(sort)})

            usage_text = (self.app.meta or {}).get("usage_text", "")
            api_store_meta_update(self.cfg, self.app.current_store_id, usage_text, cats)

            messagebox.showinfo("저장", "카테고리 저장 완료! 다른 PC에도 자동 반영됩니다.")
            self.app.meta = api_store_meta(self.cfg, self.app.current_store_id)["meta"]
            self.app.show_categories(self.app.current_store_id, self.app.current_store_name)
            self.destroy()
        except Exception as e:
            messagebox.showerror("저장 실패", str(e))

# =========================
# run
# =========================
def run_safe():
    minimize_console()
    lock = ensure_single_instance()
    try:
        app = App()
        app.mainloop()
    except SystemExit:
        pass
    except Exception as e:
        with open(os.path.join(APP_DIR, "error.log"), "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        try:
            messagebox.showerror("프로그램 오류", f"{e}\n\n자세한 내용은 error.log 확인")
        except Exception:
            pass
    finally:
        try:
            lock.close()
        except Exception:
            pass

if __name__ == "__main__":
    run_safe()
