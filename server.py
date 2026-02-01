import json
import os
import time
import traceback
import uuid
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
import requests

# =========================================================
# 기본 설정
# =========================================================
CONFIG_FILE = "config.json"

# "편집(관리자)" 권한용 로그인
ADMIN_EDIT_ID = "dldydtjq159"
ADMIN_EDIT_PW = "tkfkd4026"

FOOTER_TEXT = "만든이: by.용섭    |    버그제보: dldydtjq159@naver.com"

# 관리자 세션 저장 (창 닫아도 유지)
SESSION_FILE = "admin_session.json"
SESSION_TTL_SEC = 30 * 60  # 30분

# 서버에 저장되는 앱 설정(다른 PC에도 자동 적용)
APP_SETTINGS_CATEGORY = "app_settings"
SETTING_KEY_CATEGORIES = "categories"
SETTING_KEY_MENU_HELP = "menu_help"

# -------------------------
# 매장 설정
# -------------------------
STORES = [
    {"key": "kkyrl", "name": "김경영 요리 연구소"},
    {"key": "youth", "name": "청년회관"},
]

# -------------------------
# 기본 카테고리 (서버에 저장된 값 없을 때만 사용)
# -------------------------
DEFAULT_CATEGORIES = [
    {"title": "닭", "key": "chicken"},
    {"title": "소스", "key": "sauce"},
    {"title": "용기", "key": "container"},
    {"title": "조미료", "key": "seasoning"},
    {"title": "식용유", "key": "oil"},
    {"title": "떡", "key": "ricecake"},
    {"title": "면", "key": "noodle"},
    {"title": "야채", "key": "veggie"},
]

DEFAULT_MENU_HELP = (
    "사용방법\n"
    "1) 왼쪽 카테고리 클릭\n"
    "2) [추가]로 품목 만들기 (예: 불닭소스)\n"
    "3) 왼쪽 목록에서 선택 후 내용 입력\n"
    "4) [저장] 누르기\n\n"
    "참고\n"
    "- 카테고리/사용방법 편집은 관리자 로그인 필요\n"
    "- 재고(품목) 추가/수정/저장은 로그인 없이 가능"
)

FIELDS = [
    ("실재고", "real_stock", "예) 12kg / 30팩 / 200개"),
    ("가격", "price", "예) 1kg 6,500원 / 박스 28,000원"),
    ("구매처", "vendor", "예) ○○축산 / ○○마트 / 거래처명"),
    ("보관방법", "storage", "예) 냉동 -18℃ / 상온 / 유통기한"),
    ("원산지", "origin", "예) 국내산 / 브라질산 / 표시사항"),
]

DEFAULT_CONFIG = {
    "server_url": "https://stock-server-production-ca7d.up.railway.app",
    "admin_token": "dldydtjq159",  # Railway ADMIN_TOKEN과 동일해야 함
}

# =========================================================
# Config / API Helpers
# =========================================================
def normalize_server_url(url: str) -> str:
    url = (url or "").strip()
    if url.endswith("/"):
        url = url[:-1]
    return url

def load_config():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)
        return dict(DEFAULT_CONFIG)

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)
        return dict(DEFAULT_CONFIG)

    cfg.setdefault("server_url", DEFAULT_CONFIG["server_url"])
    cfg.setdefault("admin_token", DEFAULT_CONFIG["admin_token"])
    cfg["server_url"] = normalize_server_url(cfg["server_url"])
    cfg["admin_token"] = (cfg["admin_token"] or "").strip()
    return cfg

def open_config_file():
    try:
        os.startfile(os.path.abspath(CONFIG_FILE))
    except Exception as e:
        messagebox.showerror("config.json 열기 실패", str(e))

def is_ascii(s: str) -> bool:
    try:
        s.encode("ascii")
        return True
    except Exception:
        return False

def validate_config(cfg):
    if not cfg.get("server_url"):
        raise RuntimeError("server_url이 비어있습니다. config.json 확인!")
    if not cfg.get("admin_token"):
        raise RuntimeError("admin_token이 비어있습니다. config.json 확인!")
    if not is_ascii(cfg["admin_token"]):
        raise RuntimeError("admin_token에 한글/특수문자가 있어요. 영문/숫자만 사용하세요.")

def api_headers(cfg):
    return {"x-admin-token": cfg["admin_token"]}

def api_get(cfg, path):
    validate_config(cfg)
    url = f"{cfg['server_url']}{path}"
    r = requests.get(url, headers=api_headers(cfg), timeout=25)
    if r.status_code == 401:
        raise RuntimeError("Unauthorized: Railway ADMIN_TOKEN과 config.json admin_token이 같은지 확인!")
    if r.status_code == 404:
        raise RuntimeError(f"Not Found(404): 서버 주소/경로 확인!\n요청: {url}")
    r.raise_for_status()
    return r.json()

def api_post(cfg, path, data):
    validate_config(cfg)
    url = f"{cfg['server_url']}{path}"
    r = requests.post(url, headers=api_headers(cfg), json=data, timeout=25)
    if r.status_code == 401:
        raise RuntimeError("Unauthorized: Railway ADMIN_TOKEN과 config.json admin_token이 같은지 확인!")
    if r.status_code == 404:
        raise RuntimeError(f"Not Found(404): 서버 주소/경로 확인!\n요청: {url}")
    if r.status_code == 409:
        raise RuntimeError("같은 이름의 항목이 이미 있습니다.")
    r.raise_for_status()
    return r.json()

def api_put(cfg, path, data):
    validate_config(cfg)
    url = f"{cfg['server_url']}{path}"
    r = requests.put(url, headers=api_headers(cfg), json=data, timeout=25)
    if r.status_code == 401:
        raise RuntimeError("Unauthorized: Railway ADMIN_TOKEN과 config.json admin_token이 같은지 확인!")
    if r.status_code == 404:
        raise RuntimeError(f"Not Found(404): 수정 대상이 없습니다.\n요청: {url}")
    r.raise_for_status()
    return r.json()

def api_delete(cfg, path):
    validate_config(cfg)
    url = f"{cfg['server_url']}{path}"
    r = requests.delete(url, headers=api_headers(cfg), timeout=25)
    if r.status_code == 401:
        raise RuntimeError("Unauthorized: Railway ADMIN_TOKEN과 config.json admin_token이 같은지 확인!")
    if r.status_code == 404:
        raise RuntimeError(f"Not Found(404): 삭제 대상이 없습니다.\n요청: {url}")
    r.raise_for_status()
    return r.json()

# =========================================================
# 관리자 세션 저장/로드 (30분 유지 + 창 닫아도 유지)
# =========================================================
def save_admin_session(expires_at: int):
    try:
        with open(SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump({"expires_at": int(expires_at)}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def load_admin_session():
    try:
        if not os.path.exists(SESSION_FILE):
            return None
        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        exp = int(data.get("expires_at", 0))
        if exp <= 0:
            return None
        return exp
    except Exception:
        return None

def clear_admin_session():
    try:
        if os.path.exists(SESSION_FILE):
            os.remove(SESSION_FILE)
    except Exception:
        pass

# =========================================================
# 서버에 앱 설정 저장/로드 (카테고리, 사용방법 문구)
# =========================================================
def _find_setting_item(cfg, key_name: str):
    res = api_get(cfg, f"/api/items/{APP_SETTINGS_CATEGORY}")
    items = res.get("items", [])
    for it in items:
        if it.get("name") == key_name:
            return it
    return None

def get_setting_text(cfg, key_name: str, default_value: str = "") -> str:
    try:
        it = _find_setting_item(cfg, key_name)
        if not it:
            return default_value
        val = it.get("storage")
        return val if isinstance(val, str) and val.strip() != "" else default_value
    except Exception:
        return default_value

def set_setting_text(cfg, key_name: str, value: str):
    it = _find_setting_item(cfg, key_name)
    payload = {"real_stock": "", "price": "", "vendor": "", "storage": value, "origin": ""}

    if not it:
        api_post(cfg, f"/api/items/{APP_SETTINGS_CATEGORY}", {"name": key_name, **payload})
    else:
        api_put(cfg, f"/api/items/{APP_SETTINGS_CATEGORY}/{it['id']}", payload)

def get_setting_categories(cfg):
    raw = get_setting_text(cfg, SETTING_KEY_CATEGORIES, default_value="")
    if not raw:
        return list(DEFAULT_CATEGORIES)
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            cleaned = []
            for c in data:
                if isinstance(c, dict) and c.get("title") and c.get("key"):
                    cleaned.append({"title": str(c["title"]), "key": str(c["key"])})
            return cleaned if cleaned else list(DEFAULT_CATEGORIES)
    except Exception:
        pass
    return list(DEFAULT_CATEGORIES)

def set_setting_categories(cfg, categories_list):
    set_setting_text(cfg, SETTING_KEY_CATEGORIES, json.dumps(categories_list, ensure_ascii=False, indent=2))

# =========================================================
# UI Theme
# =========================================================
COL_BG = "#0F172A"
COL_PANEL = "#111C3A"
COL_CARD = "#162447"
COL_TEXT = "#E5E7EB"
COL_MUTED = "#A7B0C0"
COL_ACCENT = "#7C3AED"
COL_LINE = "#2A355A"

def apply_style(root: tk.Tk):
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass

    root.option_add("*Font", ("Malgun Gothic", 10))
    root.configure(bg=COL_BG)

    style.configure("TFrame", background=COL_BG)
    style.configure("Card.TFrame", background=COL_PANEL, relief="flat")
    style.configure("Inner.TFrame", background=COL_CARD, relief="flat")
    style.configure("TLabel", background=COL_BG, foreground=COL_TEXT)

    style.configure("Title.TLabel", background=COL_BG, foreground=COL_TEXT, font=("Malgun Gothic", 15, "bold"))
    style.configure("H2.TLabel", background=COL_CARD, foreground=COL_TEXT, font=("Malgun Gothic", 11, "bold"))
    style.configure("Muted.TLabel", background=COL_CARD, foreground=COL_MUTED)
    style.configure("Footer.TLabel", background=COL_BG, foreground=COL_MUTED, font=("Malgun Gothic", 9))

    style.configure("Primary.TButton", padding=10, background=COL_ACCENT, foreground="white")
    style.map("Primary.TButton", background=[("active", "#6D28D9")])

    style.configure("Ghost.TButton", padding=10, background=COL_CARD, foreground=COL_TEXT)
    style.map("Ghost.TButton", background=[("active", "#1F2B55")])

    style.configure("Danger.TButton", padding=10, background="#B91C1C", foreground="white")
    style.map("Danger.TButton", background=[("active", "#991B1B")])

    style.configure("Entry.TEntry", fieldbackground="#0B1225", foreground=COL_TEXT)

# =========================================================
# Utils
# =========================================================
def is_safe_key(s: str) -> bool:
    if not s:
        return False
    for ch in s:
        ok = ch.isalnum() or ch in ["_", "-"]
        if not ok:
            return False
    return True

def auto_key():
    return "cat_" + uuid.uuid4().hex[:6]

# =========================================================
# App
# =========================================================
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("재고관리 (PC)")
        self.geometry("980x660")
        self.resizable(False, False)

        apply_style(self)

        self.cfg = load_config()

        self.store_key = None
        self.store_name = None

        # 관리자(편집) 로그인 여부
        self.is_admin_editor = False
        self.admin_expires_at = 0

        # 서버 설정 캐시
        self.remote_categories = list(DEFAULT_CATEGORIES)
        self.remote_menu_help = DEFAULT_MENU_HELP

        # 현재 화면 추적 (세션 만료 시 UI 갱신용)
        self.current_view = "store_select"  # store_select/menu/items/category_editor

        self.container = ttk.Frame(self)
        self.container.pack(fill="both", expand=True, padx=16, pady=16)

        # ✅ 앱 시작 시 관리자 세션 자동 복원
        self._restore_admin_session()

        # ✅ 30분 만료 체크 타이머
        self.after(10_000, self._session_watchdog)  # 10초 후 첫 체크

        self.show_store_select()

    def reload_config(self):
        self.cfg = load_config()

    def load_remote_settings_safe(self):
        try:
            self.reload_config()
            self.remote_categories = get_setting_categories(self.cfg)
            self.remote_menu_help = get_setting_text(self.cfg, SETTING_KEY_MENU_HELP, DEFAULT_MENU_HELP)
        except Exception:
            self.remote_categories = list(DEFAULT_CATEGORIES)
            self.remote_menu_help = DEFAULT_MENU_HELP

    def clear(self):
        for w in self.container.winfo_children():
            w.destroy()

    def show_store_select(self):
        self.current_view = "store_select"
        self.clear()
        StoreSelectFrame(self.container, self).pack(fill="both", expand=True)

    def set_store(self, store_key: str, store_name: str):
        self.store_key = store_key
        self.store_name = store_name
        self.show_menu()

    def show_menu(self):
        self.current_view = "menu"
        self.load_remote_settings_safe()
        self.clear()
        MenuFrame(self.container, self).pack(fill="both", expand=True)

    def show_category(self, title, base_category_key):
        self.current_view = "items"
        category_key = f"{self.store_key}_{base_category_key}"
        self.clear()
        ItemsFrame(self.container, self, title=title, category=category_key).pack(fill="both", expand=True)

    def admin_login(self, user_id: str, pw: str) -> bool:
        if (user_id or "").strip() == ADMIN_EDIT_ID and (pw or "").strip() == ADMIN_EDIT_PW:
            self.is_admin_editor = True
            self.admin_expires_at = int(time.time()) + SESSION_TTL_SEC
            save_admin_session(self.admin_expires_at)
            return True
        self.is_admin_editor = False
        self.admin_expires_at = 0
        clear_admin_session()
        return False

    def admin_logout(self, show_msg=True):
        self.is_admin_editor = False
        self.admin_expires_at = 0
        clear_admin_session()
        if show_msg:
            messagebox.showinfo("로그아웃", "관리자 로그아웃 되었습니다.")
        self._refresh_view_after_auth_change()

    def show_category_editor(self):
        if not self.is_admin_editor:
            messagebox.showinfo("권한 없음", "카테고리 편집은 관리자 로그인 후 사용 가능합니다.")
            return
        self.current_view = "category_editor"
        self.load_remote_settings_safe()
        self.clear()
        CategoryEditorFrame(self.container, self).pack(fill="both", expand=True)

    # ✅ 카테고리 화면에서 매장 변경 팝업 (요구사항 3)
    def open_store_picker_popup(self):
        win = tk.Toplevel(self)
        win.title("매장 변경")
        win.geometry("360x220")
        win.resizable(False, False)
        win.configure(bg=COL_BG)
        win.transient(self)
        win.grab_set()

        wrap = ttk.Frame(win, style="Card.TFrame")
        wrap.pack(fill="both", expand=True, padx=12, pady=12)
        wrap.configure(padding=16)

        ttk.Label(wrap, text="매장을 선택하세요", style="Title.TLabel").pack(anchor="w")

        info = "선택하면 바로 해당 매장으로 전환됩니다."
        ttk.Label(wrap, text=info, foreground=COL_MUTED, background=COL_BG).pack(anchor="w", pady=(6, 12))

        for st in STORES:
            ttk.Button(
                wrap,
                text=st["name"],
                style="Primary.TButton" if st["key"] != self.store_key else "Ghost.TButton",
                command=lambda k=st["key"], n=st["name"]: self._switch_store_from_popup(win, k, n)
            ).pack(fill="x", pady=6)

        ttk.Button(wrap, text="닫기", style="Ghost.TButton", command=win.destroy).pack(fill="x", pady=(10, 0))

    def _switch_store_from_popup(self, win, store_key, store_name):
        try:
            win.destroy()
        except Exception:
            pass
        self.set_store(store_key, store_name)

    # -------------------------
    # 세션 복원 / 만료 체크
    # -------------------------
    def _restore_admin_session(self):
        exp = load_admin_session()
        now = int(time.time())
        if exp and exp > now:
            self.is_admin_editor = True
            self.admin_expires_at = exp
        else:
            self.is_admin_editor = False
            self.admin_expires_at = 0
            clear_admin_session()

    def _session_watchdog(self):
        try:
            if self.is_admin_editor:
                now = int(time.time())
                if self.admin_expires_at and now >= self.admin_expires_at:
                    # 만료
                    self.is_admin_editor = False
                    self.admin_expires_at = 0
                    clear_admin_session()
                    messagebox.showinfo("자동 로그아웃", "관리자 로그인 30분이 지나 자동 로그아웃 되었습니다.")
                    self._refresh_view_after_auth_change()
        finally:
            # 20초마다 체크 (가볍게)
            self.after(20_000, self._session_watchdog)

    def _refresh_view_after_auth_change(self):
        # 로그인/로그아웃 후 버튼 표시 상태를 즉시 반영
        if self.current_view == "store_select":
            self.show_store_select()
        elif self.current_view == "menu":
            self.show_menu()
        elif self.current_view == "category_editor":
            # 권한 잃으면 메뉴로
            if not self.is_admin_editor:
                self.show_menu()
            else:
                self.show_category_editor()
        else:
            # items 화면은 관리자 UI가 거의 없으니 유지해도 됨
            pass


# =========================================================
# Store Select Frame (관리자 로그인 포함)
# =========================================================
class StoreSelectFrame(ttk.Frame):
    def __init__(self, parent, app: App):
        super().__init__(parent)
        self.app = app

        header = ttk.Frame(self, style="Card.TFrame")
        header.pack(fill="x", pady=(0, 12))
        header.configure(padding=16)

        ttk.Label(header, text="재고관리", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text="매장을 선택하세요 (관리자 로그인 선택)", foreground=COL_MUTED, background=COL_BG).pack(anchor="w", pady=(4, 0))

        body = ttk.Frame(self, style="Card.TFrame")
        body.pack(fill="both", expand=True)
        body.configure(padding=16)

        left = ttk.Frame(body, style="Inner.TFrame")
        left.pack(side="left", fill="both", expand=True)
        left.configure(padding=16)

        ttk.Label(left, text="매장 선택", style="H2.TLabel").pack(anchor="w")

        grid = ttk.Frame(left, style="Inner.TFrame")
        grid.pack(fill="both", expand=True, pady=(10, 0))

        for i, st in enumerate(STORES):
            card = ttk.Frame(grid, style="Inner.TFrame")
            card.grid(row=i, column=0, sticky="ew", pady=8)
            grid.columnconfigure(0, weight=1)
            card.configure(padding=14)

            ttk.Label(card, text=st["name"], style="H2.TLabel").pack(anchor="w")
            ttk.Label(card, text="클릭하면 해당 매장 데이터로 들어갑니다", style="Muted.TLabel").pack(anchor="w", pady=(6, 10))
            ttk.Button(card, text="이 매장으로 시작", style="Primary.TButton",
                       command=lambda k=st["key"], n=st["name"]: self.app.set_store(k, n)).pack(fill="x")

        right = ttk.Frame(body, style="Inner.TFrame")
        right.pack(side="right", fill="y", padx=(12, 0))
        right.configure(padding=16)

        ttk.Label(right, text="관리자 로그인(편집 권한)", style="H2.TLabel").pack(anchor="w")

        ttk.Label(
            right,
            text="로그인하면:\n- 카테고리 편집 가능\n- 사용문구(사용방법) 편집 가능\n\n비로그인도 재고 입력은 가능합니다.",
            style="Muted.TLabel", justify="left"
        ).pack(anchor="w", pady=(8, 12))

        ttk.Label(right, text="아이디", background=COL_CARD, foreground=COL_TEXT).pack(anchor="w")
        self.ent_id = ttk.Entry(right, style="Entry.TEntry")
        self.ent_id.pack(fill="x", pady=(4, 10))

        ttk.Label(right, text="비밀번호", background=COL_CARD, foreground=COL_TEXT).pack(anchor="w")
        self.ent_pw = ttk.Entry(right, style="Entry.TEntry", show="*")
        self.ent_pw.pack(fill="x", pady=(4, 12))

        self.status = ttk.Label(right, text="", background=COL_CARD, foreground=COL_MUTED)
        self.status.pack(anchor="w", pady=(0, 12))
        self._refresh_status()

        btn_row = ttk.Frame(right, style="Inner.TFrame")
        btn_row.pack(fill="x")

        ttk.Button(btn_row, text="로그인", style="Primary.TButton", command=self.do_login).pack(side="left", fill="x", expand=True)
        ttk.Button(btn_row, text="로그아웃", style="Ghost.TButton", command=self.do_logout).pack(side="left", fill="x", expand=True, padx=(8, 0))

        footer = ttk.Frame(self, style="Card.TFrame")
        footer.pack(fill="x", pady=(12, 0))
        footer.configure(padding=16)

        ttk.Button(footer, text="config.json 열기", style="Ghost.TButton", command=open_config_file).pack(side="left")
        ttk.Button(footer, text="종료", style="Danger.TButton", command=self.app.destroy).pack(side="right")

        ttk.Label(self, text=FOOTER_TEXT, style="Footer.TLabel").pack(anchor="center", pady=(10, 0))

    def _refresh_status(self):
        if self.app.is_admin_editor:
            remain = max(0, int(self.app.admin_expires_at - time.time()))
            mm = remain // 60
            ss = remain % 60
            self.status.config(text=f"상태: 관리자 로그인됨 ✅ (남은시간 {mm:02d}:{ss:02d})")
        else:
            self.status.config(text="상태: 비로그인")

    def do_login(self):
        uid = self.ent_id.get().strip()
        pw = self.ent_pw.get().strip()
        if self.app.admin_login(uid, pw):
            messagebox.showinfo("로그인 성공", "관리자 편집 권한이 활성화되었습니다 ✅\n(30분 후 자동 로그아웃)")
        else:
            messagebox.showerror("로그인 실패", "아이디 또는 비밀번호가 올바르지 않습니다.")
        self._refresh_status()

    def do_logout(self):
        self.app.admin_logout(show_msg=True)
        self.ent_pw.delete(0, tk.END)
        self._refresh_status()


# =========================================================
# Menu Frame
# - 관리자일 때만 카테고리 편집 버튼 보이게 (요구사항 2)
# - 카테고리 폼에서 "매장 변경(팝업)" 버튼 추가 (요구사항 3)
# =========================================================
class MenuFrame(ttk.Frame):
    def __init__(self, parent, app: App):
        super().__init__(parent)
        self.app = app

        top = ttk.Frame(self, style="Card.TFrame")
        top.pack(fill="x", pady=(0, 12))
        top.configure(padding=16)

        ttk.Label(top, text=f"{self.app.store_name}", style="Title.TLabel").pack(anchor="w")
        ttk.Label(top, text="카테고리를 선택하세요", foreground=COL_MUTED, background=COL_BG).pack(anchor="w", pady=(4, 0))

        main = ttk.Frame(self, style="Card.TFrame")
        main.pack(fill="both", expand=True)
        main.configure(padding=16)

        # 왼쪽: 카테고리 버튼 폼
        left = ttk.Frame(main, style="Inner.TFrame")
        left.pack(side="left", fill="y")
        left.configure(padding=16)

        ttk.Label(left, text="카테고리", style="H2.TLabel").pack(anchor="w", pady=(0, 10))

        cats = self.app.remote_categories or list(DEFAULT_CATEGORIES)
        for c in cats:
            title = c.get("title", "")
            key = c.get("key", "")
            if not title or not key:
                continue
            ttk.Button(left, text=title, style="Ghost.TButton",
                       command=lambda t=title, k=key: self.app.show_category(t, k)).pack(fill="x", pady=6)

        ttk.Separator(left).pack(fill="x", pady=10)

        # ✅ 카테고리 폼에서 매장 변경(팝업)
        ttk.Button(left, text="매장 변경", style="Primary.TButton",
                   command=self.app.open_store_picker_popup).pack(fill="x", pady=6)

        # ✅ 관리자일 때만 카테고리 편집 버튼 표시
        if self.app.is_admin_editor:
            ttk.Button(left, text="카테고리 편집(관리자)", style="Ghost.TButton",
                       command=self.app.show_category_editor).pack(fill="x", pady=6)

        ttk.Button(left, text="종료", style="Danger.TButton", command=self.app.destroy).pack(fill="x", pady=6)

        # 오른쪽: 사용문구(사용방법)
        right = ttk.Frame(main, style="Inner.TFrame")
        right.pack(side="right", fill="both", expand=True, padx=(12, 0))
        right.configure(padding=16)

        ttk.Label(right, text="사용문구(사용방법)", style="H2.TLabel").pack(anchor="w")

        self.help_text = tk.Text(
            right, height=16, wrap="word",
            bg="#0B1225", fg=COL_TEXT, insertbackground=COL_TEXT,
            relief="flat", highlightthickness=1, highlightbackground=COL_LINE
        )
        self.help_text.pack(fill="both", expand=True, pady=(10, 10))
        self.help_text.insert("1.0", self.app.remote_menu_help or DEFAULT_MENU_HELP)

        btns = ttk.Frame(right, style="Inner.TFrame")
        btns.pack(fill="x")

        ttk.Button(btns, text="새로고침", style="Ghost.TButton", command=self.refresh_help).pack(side="left")

        if self.app.is_admin_editor:
            self.help_text.config(state="normal")
            ttk.Button(btns, text="저장(관리자)", style="Primary.TButton", command=self.save_help).pack(side="right")
        else:
            self.help_text.config(state="disabled")

        ttk.Label(self, text=FOOTER_TEXT, style="Footer.TLabel").pack(anchor="center", pady=(10, 0))

    def refresh_help(self):
        self.app.load_remote_settings_safe()
        self.help_text.config(state="normal")
        self.help_text.delete("1.0", tk.END)
        self.help_text.insert("1.0", self.app.remote_menu_help or DEFAULT_MENU_HELP)
        if not self.app.is_admin_editor:
            self.help_text.config(state="disabled")

    def save_help(self):
        new_text = self.help_text.get("1.0", tk.END).rstrip()
        if not new_text.strip():
            messagebox.showerror("저장 실패", "내용이 비어있습니다.")
            return
        try:
            self.app.reload_config()
            set_setting_text(self.app.cfg, SETTING_KEY_MENU_HELP, new_text)
            self.app.remote_menu_help = new_text
            messagebox.showinfo("저장 완료", "사용문구가 서버에 저장되었습니다.\n다른 PC에도 자동 적용됩니다 ✅")
        except Exception as e:
            messagebox.showerror("저장 실패", str(e))


# =========================================================
# Items Frame (재고 입력 화면)
# =========================================================
class ItemsFrame(ttk.Frame):
    def __init__(self, parent, app: App, title: str, category: str):
        super().__init__(parent)
        self.app = app
        self.title_text = title
        self.category = category

        self.items = []
        self.selected_item = None

        top = ttk.Frame(self, style="Card.TFrame")
        top.pack(fill="x", pady=(0, 12))
        top.configure(padding=16)

        ttk.Label(top, text=f"{self.app.store_name}  |  {self.title_text}", style="Title.TLabel").pack(anchor="w")
        ttk.Label(top, text="왼쪽에서 품목을 선택하고 오른쪽에 상세를 입력하세요",
                  foreground=COL_MUTED, background=COL_BG).pack(anchor="w", pady=(4, 0))

        body = ttk.Frame(self, style="Card.TFrame")
        body.pack(fill="both", expand=True)
        body.configure(padding=16)

        left = ttk.Frame(body, style="Inner.TFrame")
        left.pack(side="left", fill="y")
        left.configure(padding=16)

        ttk.Label(left, text="품목(종류) 목록", style="H2.TLabel").pack(anchor="w")

        self.listbox = tk.Listbox(
            left, font=("Malgun Gothic", 10),
            bg="#0B1225", fg=COL_TEXT,
            selectbackground=COL_ACCENT,
            highlightthickness=1, highlightbackground=COL_LINE,
            relief="flat"
        )
        self.listbox.pack(fill="both", expand=True, pady=(10, 10))
        self.listbox.bind("<<ListboxSelect>>", self.on_select)

        btn_row = ttk.Frame(left, style="Inner.TFrame")
        btn_row.pack(fill="x")

        ttk.Button(btn_row, text="추가", style="Primary.TButton", command=self.add_item).pack(side="left", fill="x", expand=True)
        ttk.Button(btn_row, text="삭제", style="Danger.TButton", command=self.delete_item).pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(btn_row, text="새로고침", style="Ghost.TButton",
                   command=lambda: self.refresh_list(preserve_id=(self.selected_item or {}).get("id"))).pack(side="left", fill="x", expand=True)

        right = ttk.Frame(body, style="Inner.TFrame")
        right.pack(side="right", fill="both", expand=True, padx=(12, 0))
        right.configure(padding=16)

        ttk.Label(right, text="선택된 품목 상세", style="H2.TLabel").pack(anchor="w")

        self.selected_name_label = ttk.Label(right, text="(품목을 선택하세요)",
                                             background=COL_CARD, foreground=COL_MUTED)
        self.selected_name_label.pack(anchor="w", pady=(8, 12))

        self.entries = {}
        for label, key, hint in FIELDS:
            row = ttk.Frame(right, style="Inner.TFrame")
            row.pack(fill="x", pady=6)

            ttk.Label(row, text=label, background=COL_CARD, foreground=COL_TEXT, width=10).pack(side="left")
            ent = ttk.Entry(row, style="Entry.TEntry")
            ent.pack(side="left", fill="x", expand=True, padx=(8, 0))
            self.entries[key] = ent

            ttk.Label(right, text=hint, style="Muted.TLabel").pack(anchor="w", pady=(0, 6))

        self.status = ttk.Label(body, text="", background=COL_PANEL, foreground=COL_MUTED)
        self.status.pack(anchor="w", pady=(10, 0))

        bottom = ttk.Frame(self, style="Card.TFrame")
        bottom.pack(fill="x", pady=(12, 0))
        bottom.configure(padding=16)

        ttk.Button(bottom, text="매장 변경", style="Ghost.TButton", command=self.app.open_store_picker_popup).pack(side="left")
        ttk.Button(bottom, text="뒤로가기", style="Ghost.TButton", command=self.app.show_menu).pack(side="left", padx=(8, 0))
        ttk.Button(bottom, text="저장", style="Primary.TButton", command=self.save_selected).pack(side="right")
        ttk.Button(bottom, text="종료", style="Danger.TButton", command=self.app.destroy).pack(side="right", padx=(0, 8))

        ttk.Label(self, text=FOOTER_TEXT, style="Footer.TLabel").pack(anchor="center", pady=(10, 0))

        self.refresh_list()

    def refresh_list(self, preserve_id=None):
        try:
            self.app.reload_config()
            res = api_get(self.app.cfg, f"/api/items/{self.category}")
            self.items = res.get("items", [])

            self.listbox.delete(0, tk.END)
            for it in self.items:
                self.listbox.insert(tk.END, it["name"])

            if preserve_id:
                for i, it in enumerate(self.items):
                    if it.get("id") == preserve_id:
                        self.listbox.selection_clear(0, tk.END)
                        self.listbox.selection_set(i)
                        self.listbox.activate(i)
                        self.selected_item = it
                        self._fill_entries_from_selected()
                        break
                else:
                    self.selected_item = None
                    self._clear_entries()
            else:
                self.selected_item = None
                self._clear_entries()

            self.status.config(text="목록 불러오기 완료 ✅")
        except Exception as e:
            self.status.config(text="목록 불러오기 실패 ❌")
            messagebox.showerror("오류", str(e))

    def _clear_entries(self):
        self.selected_name_label.config(text="(품목을 선택하세요)")
        for k in self.entries:
            self.entries[k].delete(0, tk.END)

    def _fill_entries_from_selected(self):
        self.selected_name_label.config(text=f"선택: {self.selected_item['name']}")
        for k in ["real_stock", "price", "vendor", "storage", "origin"]:
            self.entries[k].delete(0, tk.END)
            self.entries[k].insert(0, self.selected_item.get(k, "") or "")
        updated = self.selected_item.get("updated_at") or ""
        self.status.config(text=f"선택 완료 · {updated}")

    def on_select(self, _evt=None):
        idxs = self.listbox.curselection()
        if not idxs:
            return
        idx = idxs[0]
        if idx < 0 or idx >= len(self.items):
            return
        self.selected_item = self.items[idx]
        self._fill_entries_from_selected()

    def add_item(self):
        name = tk.simpledialog.askstring("품목 추가", f"{self.title_text}에 추가할 품목명을 입력하세요.\n예) 불닭소스, 매운소스")
        if not name:
            return
        name = name.strip()
        if not name:
            return
        try:
            self.app.reload_config()
            api_post(self.app.cfg, f"/api/items/{self.category}", {
                "name": name,
                "real_stock": "", "price": "", "vendor": "", "storage": "", "origin": ""
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
            self.app.reload_config()
            api_delete(self.app.cfg, f"/api/items/{self.category}/{self.selected_item['id']}")
            self.refresh_list()
            messagebox.showinfo("삭제 완료", f"'{name}' 삭제했습니다.")
        except Exception as e:
            messagebox.showerror("삭제 실패", str(e))

    def save_selected(self):
        if not self.selected_item:
            messagebox.showinfo("저장", "저장할 품목을 먼저 선택하세요.\n(왼쪽 목록에서 선택)")
            return

        payload = {
            "real_stock": self.entries["real_stock"].get().strip(),
            "price": self.entries["price"].get().strip(),
            "vendor": self.entries["vendor"].get().strip(),
            "storage": self.entries["storage"].get().strip(),
            "origin": self.entries["origin"].get().strip(),
        }

        try:
            self.app.reload_config()
            res = api_put(self.app.cfg, f"/api/items/{self.category}/{self.selected_item['id']}", payload)
            self.status.config(text=f"저장 완료 ✅ · {res.get('updated_at', '')}")

            keep_id = self.selected_item["id"]
            self.refresh_list(preserve_id=keep_id)
            messagebox.showinfo("저장 완료", "저장되었습니다 ✅")
        except Exception as e:
            self.status.config(text="저장 실패 ❌")
            messagebox.showerror("저장 실패", str(e))


# =========================================================
# Category Editor (관리자만)
# =========================================================
class CategoryEditorFrame(ttk.Frame):
    def __init__(self, parent, app: App):
        super().__init__(parent)
        self.app = app
        self.categories = list(app.remote_categories or DEFAULT_CATEGORIES)

        top = ttk.Frame(self, style="Card.TFrame")
        top.pack(fill="x", pady=(0, 12))
        top.configure(padding=16)

        ttk.Label(top, text="카테고리 편집 (관리자)", style="Title.TLabel").pack(anchor="w")
        ttk.Label(top, text="추가/삭제/이름변경/순서이동 후 저장하면 다른 PC에도 적용됩니다",
                  foreground=COL_MUTED, background=COL_BG).pack(anchor="w", pady=(4, 0))

        body = ttk.Frame(self, style="Card.TFrame")
        body.pack(fill="both", expand=True)
        body.configure(padding=16)

        left = ttk.Frame(body, style="Inner.TFrame")
        left.pack(side="left", fill="both", expand=True)
        left.configure(padding=16)

        ttk.Label(left, text="카테고리 목록", style="H2.TLabel").pack(anchor="w")

        self.listbox = tk.Listbox(
            left, font=("Malgun Gothic", 10),
            bg="#0B1225", fg=COL_TEXT,
            selectbackground=COL_ACCENT,
            highlightthickness=1, highlightbackground=COL_LINE,
            relief="flat"
        )
        self.listbox.pack(fill="both", expand=True, pady=(10, 10))

        right = ttk.Frame(body, style="Inner.TFrame")
        right.pack(side="right", fill="y", padx=(12, 0))
        right.configure(padding=16)

        ttk.Label(right, text="작업", style="H2.TLabel").pack(anchor="w", pady=(0, 10))

        ttk.Button(right, text="추가", style="Primary.TButton", command=self.add_cat).pack(fill="x", pady=6)
        ttk.Button(right, text="이름변경", style="Ghost.TButton", command=self.rename_cat).pack(fill="x", pady=6)
        ttk.Button(right, text="삭제", style="Danger.TButton", command=self.delete_cat).pack(fill="x", pady=6)
        ttk.Button(right, text="위로", style="Ghost.TButton", command=lambda: self.move_cat(-1)).pack(fill="x", pady=6)
        ttk.Button(right, text="아래로", style="Ghost.TButton", command=lambda: self.move_cat(+1)).pack(fill="x", pady=6)

        self.status = ttk.Label(body, text="", background=COL_PANEL, foreground=COL_MUTED)
        self.status.pack(anchor="w", pady=(10, 0))

        bottom = ttk.Frame(self, style="Card.TFrame")
        bottom.pack(fill="x", pady=(12, 0))
        bottom.configure(padding=16)

        ttk.Button(bottom, text="매장 변경", style="Ghost.TButton", command=self.app.open_store_picker_popup).pack(side="left")
        ttk.Button(bottom, text="뒤로가기", style="Ghost.TButton", command=self.app.show_menu).pack(side="left", padx=(8, 0))
        ttk.Button(bottom, text="저장", style="Primary.TButton", command=self.save).pack(side="right")
        ttk.Button(bottom, text="종료", style="Danger.TButton", command=self.app.destroy).pack(side="right", padx=(0, 8))

        ttk.Label(self, text=FOOTER_TEXT, style="Footer.TLabel").pack(anchor="center", pady=(10, 0))

        self.refresh()

    def refresh(self):
        self.listbox.delete(0, tk.END)
        for c in self.categories:
            self.listbox.insert(tk.END, f"{c.get('title','')}  ({c.get('key','')})")
        self.status.config(text="불러오기 완료 ✅")

    def selected_index(self):
        sel = self.listbox.curselection()
        return sel[0] if sel else None

    def add_cat(self):
        title = tk.simpledialog.askstring("카테고리 추가", "버튼 이름 입력 (예: 포장재)")
        if not title:
            return
        title = title.strip()
        if not title:
            return

        key = tk.simpledialog.askstring("카테고리 키", "영문 키 입력(예: packaging)\n비우면 자동 생성됩니다")
        if key is None:
            return
        key = key.strip()
        if not key:
            key = auto_key()

        if not is_safe_key(key):
            messagebox.showerror("키 오류", "키는 영어/숫자/_/- 만 가능합니다.")
            return

        for c in self.categories:
            if c.get("key") == key:
                messagebox.showerror("중복", f"'{key}' 키가 이미 있습니다.")
                return

        self.categories.append({"title": title, "key": key})
        self.refresh()
        self.status.config(text="추가됨 ✅ (저장해야 적용)")

    def rename_cat(self):
        idx = self.selected_index()
        if idx is None:
            messagebox.showinfo("선택", "변경할 카테고리를 선택하세요.")
            return
        cur = self.categories[idx]
        new_title = tk.simpledialog.askstring("이름변경", f"새 이름 입력 (현재: {cur.get('title','')})")
        if not new_title:
            return
        new_title = new_title.strip()
        if not new_title:
            return
        self.categories[idx]["title"] = new_title
        self.refresh()
        self.listbox.selection_set(idx)
        self.status.config(text="이름 변경됨 ✅ (저장해야 적용)")

    def delete_cat(self):
        idx = self.selected_index()
        if idx is None:
            messagebox.showinfo("선택", "삭제할 카테고리를 선택하세요.")
            return
        cur = self.categories[idx]
        if not messagebox.askyesno("삭제 확인", f"'{cur.get('title','')}' 삭제할까요?"):
            return
        del self.categories[idx]
        self.refresh()
        self.status.config(text="삭제됨 ✅ (저장해야 적용)")

    def move_cat(self, delta):
        idx = self.selected_index()
        if idx is None:
            return
        new_idx = idx + delta
        if new_idx < 0 or new_idx >= len(self.categories):
            return
        self.categories[idx], self.categories[new_idx] = self.categories[new_idx], self.categories[idx]
        self.refresh()
        self.listbox.selection_set(new_idx)
        self.status.config(text="순서 변경됨 ✅ (저장해야 적용)")

    def save(self):
        try:
            self.app.reload_config()
            set_setting_categories(self.app.cfg, self.categories)
            self.app.remote_categories = list(self.categories)
            messagebox.showinfo("저장 완료", "카테고리가 서버에 저장되었습니다.\n다른 PC에도 자동 적용됩니다 ✅")
            self.status.config(text="저장 완료 ✅")
        except Exception as e:
            messagebox.showerror("저장 실패", str(e))


# =========================================================
# 안전 실행
# =========================================================
def run_safe():
    try:
        App().mainloop()
    except Exception as e:
        with open("error.log", "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        try:
            messagebox.showerror("프로그램 오류", f"{e}\n\n자세한 내용은 error.log 확인")
        except Exception:
            pass

if __name__ == "__main__":
    run_safe()
