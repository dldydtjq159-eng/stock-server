import json
import os
import traceback
import tkinter as tk
from tkinter import messagebox
from tkinter import simpledialog
import requests

CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "server_url": "https://stock-server-production-ca7d.up.railway.app",
    "admin_token": "dldydtjq159"  # Railway ADMIN_TOKEN과 반드시 동일
}

# -------------------------
# Helpers
# -------------------------
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
    r = requests.get(url, headers=api_headers(cfg), timeout=10)
    if r.status_code == 401:
        raise RuntimeError("토큰이 없거나 틀립니다. Railway ADMIN_TOKEN과 config.json 토큰이 같은지 확인!")
    if r.status_code == 404:
        raise RuntimeError(f"주소가 없습니다(404). 서버 업데이트/도메인 확인!\n요청: {url}")
    r.raise_for_status()
    return r.json()

def api_post(cfg, path, data):
    validate_config(cfg)
    url = f"{cfg['server_url']}{path}"
    r = requests.post(url, headers=api_headers(cfg), json=data, timeout=10)
    if r.status_code == 401:
        raise RuntimeError("토큰이 없거나 틀립니다. Railway ADMIN_TOKEN과 config.json 토큰이 같은지 확인!")
    if r.status_code == 404:
        raise RuntimeError(f"주소가 없습니다(404). 서버 업데이트/도메인 확인!\n요청: {url}")
    if r.status_code == 409:
        raise RuntimeError("같은 이름의 품목이 이미 있습니다.")
    r.raise_for_status()
    return r.json()

def api_put(cfg, path, data):
    validate_config(cfg)
    url = f"{cfg['server_url']}{path}"
    r = requests.put(url, headers=api_headers(cfg), json=data, timeout=10)
    if r.status_code == 401:
        raise RuntimeError("토큰이 없거나 틀립니다. Railway ADMIN_TOKEN과 config.json 토큰이 같은지 확인!")
    if r.status_code == 404:
        raise RuntimeError(f"수정 대상이 없습니다(404).\n요청: {url}")
    r.raise_for_status()
    return r.json()

def api_delete(cfg, path):
    validate_config(cfg)
    url = f"{cfg['server_url']}{path}"
    r = requests.delete(url, headers=api_headers(cfg), timeout=10)
    if r.status_code == 401:
        raise RuntimeError("토큰이 없거나 틀립니다. Railway ADMIN_TOKEN과 config.json 토큰이 같은지 확인!")
    if r.status_code == 404:
        raise RuntimeError(f"삭제 대상이 없습니다(404).\n요청: {url}")
    r.raise_for_status()
    return r.json()

# -------------------------
# UI Theme
# -------------------------
BG = "#F28C28"
PANEL = "#F6A04D"
DARK = "#1f1f1f"

# ✅ 버튼 변경
CATEGORIES = [
    ("닭", "chicken"),
    ("소스", "sauce"),
    ("용기", "container"),
    ("조미료", "seasoning"),
    ("식용유", "oil"),
    ("떡", "ricecake"),
    ("면", "noodle"),
    ("야채", "veggie"),
]

FIELDS = [
    ("실재고", "real_stock", "예) 12kg / 30팩 / 200개"),
    ("가격", "price", "예) 1kg 6,500원 / 박스 28,000원"),
    ("구매처", "vendor", "예) ○○축산 / ○○마트 / 거래처명"),
    ("보관방법", "storage", "예) 냉동 -18℃ / 상온 / 유통기한"),
    ("원산지", "origin", "예) 국내산 / 브라질산 / 표시사항"),
]

# -------------------------
# App
# -------------------------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("재고관리 (PC)")
        self.geometry("920x520")
        self.resizable(False, False)
        self.configure(bg=BG)

        self.cfg = load_config()

        self.container = tk.Frame(self, bg=BG)
        self.container.pack(fill="both", expand=True, padx=10, pady=10)

        self.show_menu()

    def reload_config(self):
        self.cfg = load_config()

    def clear(self):
        for w in self.container.winfo_children():
            w.destroy()

    def show_menu(self):
        self.clear()
        MenuFrame(self.container, self).place(x=0, y=0, width=900, height=500)

    def show_category(self, title, key):
        self.clear()
        ItemsFrame(self.container, self, title=title, category=key).place(x=0, y=0, width=900, height=500)


class MenuFrame(tk.Frame):
    def __init__(self, parent, app: App):
        super().__init__(parent, bg=BG)
        self.app = app

        left = tk.Frame(self, bg=PANEL, highlightthickness=1, highlightbackground="white")
        left.place(x=0, y=0, width=320, height=420)

        tk.Label(left, text="■ 항목 선택", bg=PANEL, fg=DARK, font=("Malgun Gothic", 12, "bold")).place(x=10, y=10)

        y = 55
        for title, key in CATEGORIES:
            tk.Button(
                left, text=title,
                font=("Malgun Gothic", 11, "bold"),
                command=lambda t=title, k=key: self.app.show_category(t, k)
            ).place(x=18, y=y, width=280, height=38)
            y += 45

        right = tk.Frame(self, bg=PANEL, highlightthickness=1, highlightbackground="white")
        right.place(x=340, y=0, width=560, height=420)

        tk.Label(
            right,
            text="▶ 카테고리 클릭 → 품목(종류) 추가/선택 → 저장\n\n"
                 "예) 소스 → [추가] → 매운소스 / 불닭소스 …\n\n"
                 "문제 해결:\n"
                 "- Unauthorized: Railway ADMIN_TOKEN과 config.json 토큰 일치\n"
                 "- 404 Not Found: server.py(3.0) 업로드/배포 확인",
            bg=PANEL, fg=DARK, font=("Malgun Gothic", 10, "bold"),
            justify="left"
        ).place(x=15, y=25)

        tk.Button(right, text="config.json 열기", font=("Malgun Gothic", 10, "bold"),
                  command=open_config_file).place(x=20, y=340, width=150, height=40)

        tk.Button(right, text="종료", font=("Malgun Gothic", 10, "bold"),
                  command=self.app.destroy).place(x=200, y=340, width=120, height=40)


class ItemsFrame(tk.Frame):
    """
    카테고리(예: sauce) 안에서 여러 품목을 추가/선택/삭제하고
    선택된 품목의 상세 정보를 저장하는 화면
    """
    def __init__(self, parent, app: App, title: str, category: str):
        super().__init__(parent, bg=BG)
        self.app = app
        self.title_text = title
        self.category = category

        self.items = []          # 서버에서 받은 items list
        self.selected_item = None

        # 상단 패널
        panel = tk.Frame(self, bg=PANEL, highlightthickness=1, highlightbackground="white")
        panel.place(x=0, y=0, width=900, height=430)

        tk.Label(panel, text=f"■ {self.title_text} (품목 관리)", bg=PANEL, fg=DARK,
                 font=("Malgun Gothic", 12, "bold")).place(x=15, y=12)

        # 왼쪽: 품목 리스트
        left = tk.Frame(panel, bg=PANEL)
        left.place(x=15, y=50, width=260, height=360)

        tk.Label(left, text="품목(종류) 목록", bg=PANEL, fg=DARK, font=("Malgun Gothic", 10, "bold")).place(x=0, y=0)

        self.listbox = tk.Listbox(left, font=("Malgun Gothic", 10))
        self.listbox.place(x=0, y=28, width=260, height=250)
        self.listbox.bind("<<ListboxSelect>>", self.on_select)

        tk.Button(left, text="추가", font=("Malgun Gothic", 10, "bold"),
                  command=self.add_item).place(x=0, y=290, width=80, height=36)

        tk.Button(left, text="삭제", font=("Malgun Gothic", 10, "bold"),
                  command=self.delete_item).place(x=90, y=290, width=80, height=36)

        tk.Button(left, text="새로고침", font=("Malgun Gothic", 10, "bold"),
                  command=self.refresh_list).place(x=180, y=290, width=80, height=36)

        # 오른쪽: 상세 입력
        right = tk.Frame(panel, bg=PANEL)
        right.place(x=300, y=50, width=585, height=360)

        tk.Label(right, text="선택된 품목 상세", bg=PANEL, fg=DARK, font=("Malgun Gothic", 10, "bold")).place(x=0, y=0)

        self.selected_name_label = tk.Label(right, text="(품목을 선택하세요)", bg=PANEL, fg=DARK,
                                            font=("Malgun Gothic", 10, "bold"))
        self.selected_name_label.place(x=0, y=26)

        self.entries = {}
        y = 60
        for label, key, hint in FIELDS:
            tk.Label(right, text=label, bg=PANEL, fg=DARK, font=("Malgun Gothic", 10, "bold")).place(x=0, y=y)
            ent = tk.Entry(right, font=("Malgun Gothic", 10))
            ent.place(x=110, y=y-2, width=470, height=28)
            self.entries[key] = ent
            tk.Label(right, text=hint, bg=PANEL, fg="#2b2b2b", font=("Malgun Gothic", 8)).place(x=110, y=y+28)
            y += 52

        self.status = tk.Label(panel, text="", bg=PANEL, fg=DARK, font=("Malgun Gothic", 9, "bold"))
        self.status.place(x=15, y=405)

        # 하단 버튼
        tk.Button(self, text="뒤로가기", font=("Malgun Gothic", 11, "bold"),
                  command=self.app.show_menu).place(x=20, y=445, width=140, height=44)

        tk.Button(self, text="저장", font=("Malgun Gothic", 11, "bold"),
                  command=self.save_selected).place(x=380, y=445, width=140, height=44)

        tk.Button(self, text="종료", font=("Malgun Gothic", 11, "bold"),
                  command=self.app.destroy).place(x=740, y=445, width=140, height=44)

        # 초기 로딩
        self.refresh_list()

    def refresh_list(self):
        try:
            self.app.reload_config()
            res = api_get(self.app.cfg, f"/api/items/{self.category}")
            self.items = res.get("items", [])
            self.listbox.delete(0, tk.END)
            for it in self.items:
                self.listbox.insert(tk.END, it["name"])
            self.selected_item = None
            self.selected_name_label.config(text="(품목을 선택하세요)")
            for k in self.entries:
                self.entries[k].delete(0, tk.END)
            self.status.config(text="목록 불러오기 완료 ✅")
        except Exception as e:
            self.status.config(text="목록 불러오기 실패 ❌")
            messagebox.showerror("오류", str(e))

    def on_select(self, _evt=None):
        idxs = self.listbox.curselection()
        if not idxs:
            return
        idx = idxs[0]
        if idx < 0 or idx >= len(self.items):
            return
        self.selected_item = self.items[idx]
        self.selected_name_label.config(text=f"선택: {self.selected_item['name']}")

        for k in ["real_stock", "price", "vendor", "storage", "origin"]:
            self.entries[k].delete(0, tk.END)
            self.entries[k].insert(0, self.selected_item.get(k, "") or "")

        updated = self.selected_item.get("updated_at") or ""
        self.status.config(text=f"선택 완료 · {updated}")

    def add_item(self):
        name = simpledialog.askstring("품목 추가", f"{self.title_text}에 추가할 품목명을 입력하세요.\n예) 불닭소스, 매운소스")
        if not name:
            return
        name = name.strip()
        if not name:
            return
        try:
            self.app.reload_config()
            api_post(self.app.cfg, f"/api/items/{self.category}", {
                "name": name,
                "real_stock": "",
                "price": "",
                "vendor": "",
                "storage": "",
                "origin": ""
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
            messagebox.showinfo("저장", "서버에 저장했습니다. 다른 PC에서도 동일하게 보입니다!")
            # 저장 후 목록 갱신해서 updated_at 반영
            self.refresh_list()
        except Exception as e:
            self.status.config(text="저장 실패 ❌")
            messagebox.showerror("저장 실패", str(e))


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


