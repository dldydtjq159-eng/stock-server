import os, json, re, webbrowser, socket, ctypes, traceback
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import requests

# ================================
# 기본 설정
# ================================
APP_TITLE = "김경영 재고 & 원가 통합관리"
CONFIG_FILE = "config.json"
SESSION_FILE = "admin_session.json"

DEFAULT_CONFIG = {
    "server_url": "https://stock-server-production-13ac.up.railway.app",
    "admin_token": "dldydtjq159",
    "last_store_id": "lab"
}

ADMIN_ID = "dldydtjq159"
ADMIN_PW = "tkfkd4026"
SESSION_MINUTES = 30

LOCK_PORT = 48123

# ================================
# 단일 실행 보장
# ================================
def ensure_single_instance():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", LOCK_PORT))
        s.listen(1)
        return s
    except OSError:
        messagebox.showinfo("이미 실행중", "프로그램이 이미 실행 중입니다.")
        raise SystemExit

def minimize_console():
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 6)
    except:
        pass

# ================================
# 설정 로드
# ================================
def load_config():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)
        return dict(DEFAULT_CONFIG)

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    for k,v in DEFAULT_CONFIG.items():
        cfg.setdefault(k, v)

    if cfg["server_url"].endswith("/"):
        cfg["server_url"] = cfg["server_url"][:-1]
    return cfg

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

# ================================
# 관리자 세션
# ================================
def session_save():
    expires = datetime.now() + timedelta(minutes=SESSION_MINUTES)
    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump({"expires_at": expires.isoformat()}, f)

def session_load():
    if not os.path.exists(SESSION_FILE):
        return None
    try:
        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            s = json.load(f)
        exp = datetime.fromisoformat(s["expires_at"])
        if datetime.now() <= exp:
            return s
    except:
        return None
    return None

def session_clear():
    if os.path.exists(SESSION_FILE):
        os.remove(SESSION_FILE)

def is_admin():
    return session_load() is not None

def admin_remaining_seconds():
    s = session_load()
    if not s:
        return 0
    exp = datetime.fromisoformat(s["expires_at"])
    return max(0, int((exp - datetime.now()).total_seconds()))

# ================================
# API HELPER
# ================================
def api_get(cfg, path):
    url = cfg["server_url"] + path
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return r.json()

def api_post(cfg, path, payload):
    url = cfg["server_url"] + path
    r = requests.post(url, json=payload, timeout=15)
    r.raise_for_status()
    return r.json()

def api_put_admin(cfg, path, payload):
    url = cfg["server_url"] + path
    r = requests.put(url, json=payload,
                     headers={"x-admin-token": cfg["admin_token"]},
                     timeout=15)
    if r.status_code == 401:
        raise RuntimeError("관리자 토큰 오류")
    r.raise_for_status()
    return r.json()

# ================================
# 앱 시작
# ================================
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        minimize_console()
        ensure_single_instance()

        self.cfg = load_config()
        self.title(APP_TITLE)
        self.geometry("1120x720")
        self.configure(bg="#0b1220")

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TButton", font=("Malgun Gothic", 11), padding=6)

        self.container = ttk.Frame(self)
        self.container.pack(fill="both", expand=True, padx=16, pady=16)

        self.after(100, self.show_main)
        self.after(1000, self.tick_admin)

    # ---------------- 메인 ----------------
    def show_main(self):
        self.clear()

        top = ttk.Frame(self.container)
        top.pack(fill="x")

        self.admin_badge = ttk.Label(top, text="")
        self.admin_badge.pack(side="right")

        ttk.Label(self.container,
                   text="📦 김경영 재고 & 원가 통합 시스템",
                   font=("Malgun Gothic", 20, "bold")).pack(pady=20)

        ttk.Button(self.container, text="🏬 김경영 요리 연구소",
                   command=lambda: self.show_store("lab","김경영 요리 연구소")).pack(fill="x", pady=8)

        ttk.Button(self.container, text="🏛 청년회관",
                   command=lambda: self.show_store("youth","청년회관")).pack(fill="x", pady=8)

        ttk.Button(self.container, text="💰 원가 & 순수익 계산",
                   command=self.show_profit).pack(fill="x", pady=8)

        if is_admin():
            ttk.Button(self.container, text="📢 공지사항 관리",
                       command=self.edit_notice).pack(fill="x", pady=8)
            ttk.Button(self.container, text="🔓 로그아웃",
                       command=self.admin_logout).pack(fill="x", pady=8)
        else:
            ttk.Button(self.container, text="🔐 관리자 로그인",
                       command=self.admin_login).pack(fill="x", pady=8)

        ttk.Button(self.container, text="종료",
                   command=self.destroy).pack(fill="x", pady=8)

    # ---------------- 매장 화면 ----------------
    def show_store(self, store_id, store_name):
        self.current_store_id = store_id
        self.current_store_name = store_name
        self.cfg["last_store_id"] = store_id
        save_config(self.cfg)

        self.clear()

        ttk.Label(self.container,
                   text=f"🏬 {store_name}",
                   font=("Malgun Gothic", 18, "bold")).pack(pady=10)

        btnrow = ttk.Frame(self.container)
        btnrow.pack(fill="x", pady=10)

        ttk.Button(btnrow, text="🧂 재료 관리",
                   command=lambda: self.show_category("재료")).pack(side="left", expand=True, fill="x", padx=6)

        ttk.Button(btnrow, text="📦 발주 관리",
                   command=lambda: self.show_category("발주")).pack(side="left", expand=True, fill="x", padx=6)

        ttk.Button(btnrow, text="⚠ 부족목록",
                   command=self.show_shortages).pack(side="left", expand=True, fill="x", padx=6)

        ttk.Button(btnrow, text="⬅ 뒤로",
                   command=self.show_main).pack(side="right", padx=6)

    # ---------------- 카테고리 화면 ----------------
    def show_category(self, title):
        self.clear()

        ttk.Label(self.container,
                   text=f"{title} 관리",
                   font=("Malgun Gothic", 16, "bold")).pack(pady=10)

        left = ttk.Frame(self.container)
        left.pack(side="left", fill="y", padx=10)

        ttk.Button(left, text="➕ 카테고리 추가",
                   command=self.add_category).pack(fill="x", pady=4)

        ttk.Button(left, text="➖ 카테고리 삭제",
                   command=self.del_category).pack(fill="x", pady=4)

        right = ttk.Frame(self.container)
        right.pack(side="right", fill="both", expand=True)

        ttk.Label(right, text="📢 공지사항",
                   font=("Malgun Gothic", 12, "bold")).pack(anchor="w")

        self.notice_box = tk.Text(right, height=12)
        self.notice_box.pack(fill="both", expand=True, pady=6)

        ttk.Button(right, text="저장",
                   command=self.save_notice).pack(fill="x", pady=6)

        ttk.Button(right, text="⬅ 뒤로",
                   command=lambda: self.show_store(self.current_store_id,
                                                   self.current_store_name)).pack(fill="x")

    # ---------------- 부족목록 ----------------
    def show_shortages(self):
        win = tk.Toplevel(self)
        win.title("부족목록")
        win.geometry("900x520")

        data = api_get(self.cfg, f"/api/shortages/{self.current_store_id}")

        cols = ("카테고리","품목","현재고","최소","부족","구매처","원산지")
        tree = ttk.Treeview(win, columns=cols, show="headings")

        for c in cols:
            tree.heading(c, text=c)

        tree.pack(fill="both", expand=True)

        for r in data["shortages"]:
            tree.insert("", "end", values=(
                r.get("category_key",""),
                r.get("name",""),
                r.get("current_stock",0),
                r.get("min_stock",0),
                r.get("need",0),
                r.get("vendor",""),
                r.get("origin","")
            ))

        ttk.Button(win, text="📄 발주서 저장(바탕화면)",
                   command=lambda: self.export_order(data["shortages"])).pack(fill="x", pady=8)

    def export_order(self, rows):
        path = os.path.join(os.path.expanduser("~"), "Desktop",
                            f"발주서_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")

        with open(path, "w", encoding="utf-8") as f:
            f.write("[발주서]\n")
            for r in rows:
                f.write(f"{r['name']} | 부족 {r['need']}\n")

        messagebox.showinfo("저장완료", f"바탕화면에 저장됨:\n{path}")

    # ---------------- 원가 계산 ----------------
    def show_profit(self):
        win = tk.Toplevel(self)
        win.title("원가 계산")
        win.geometry("600x400")

        ttk.Label(win, text="원가 계산기", font=("Malgun Gothic", 16)).pack(pady=10)

        ttk.Label(win, text="재료 원가(원)").pack()
        e1 = ttk.Entry(win); e1.pack()

        ttk.Label(win, text="배민 수수료(%)").pack()
        e2 = ttk.Entry(win); e2.pack()

        def calc():
            cost = float(e1.get())
            fee = float(e2.get())/100
            result = cost - (cost * fee)
            messagebox.showinfo("결과", f"예상 순이익: {int(result)}원")

        ttk.Button(win, text="계산", command=calc).pack(pady=10)

    # ---------------- 공지사항 ----------------
    def edit_notice(self):
        win = tk.Toplevel(self)
        win.title("공지사항 수정")
        win.geometry("700x400")

        txt = tk.Text(win)
        txt.pack(fill="both", expand=True)

        ttk.Button(win, text="저장",
                   command=lambda: messagebox.showinfo("저장","공지 저장됨")).pack()

    # ---------------- 관리자 ----------------
    def admin_login(self):
        d = tk.Toplevel(self)
        d.title("관리자 로그인")
        d.geometry("350x200")

        ttk.Label(d, text="아이디").pack()
        e1 = ttk.Entry(d); e1.pack()

        ttk.Label(d, text="비밀번호").pack()
        e2 = ttk.Entry(d, show="*"); e2.pack()

        def go():
            if e1.get()==ADMIN_ID and e2.get()==ADMIN_PW:
                session_save()
                messagebox.showinfo("성공","로그인 성공(30분 유지)")
                d.destroy()
                self.show_main()
            else:
                messagebox.showerror("실패","아이디/비번 오류")

        ttk.Button(d, text="로그인", command=go).pack(pady=8)

    def admin_logout(self):
        session_clear()
        messagebox.showinfo("로그아웃","완료")
        self.show_main()

    def tick_admin(self):
        rem = admin_remaining_seconds()
        if hasattr(self, "admin_badge"):
            if is_admin():
                self.admin_badge.config(text=f"관리자 ON  {rem//60:02d}:{rem%60:02d}")
            else:
                self.admin_badge.config(text="관리자 OFF")
        self.after(1000, self.tick_admin)

    def clear(self):
        for w in self.container.winfo_children():
            w.destroy()

# ================================
# 실행
# ================================
if __name__ == "__main__":
    app = App()
    app.mainloop()
