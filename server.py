import os
import json
import tkinter as tk
from tkinter import ttk, messagebox
import requests
from datetime import datetime, timedelta

APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(APP_DIR, "config.json")

def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.cfg = load_config()

        self.title("재고관리 시스템")
        self.geometry("1000x650")
        self.configure(bg="#0b1220")

        self.build_main()

    def build_main(self):
        for w in self.winfo_children():
            w.destroy()

        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True, padx=20, pady=20)

        ttk.Label(frame, text="매장 선택", font=("Malgun Gothic", 18, "bold")).pack(pady=10)

        ttk.Button(frame, text="김경영 요리 연구소",
                   command=lambda: self.open_store("lab")).pack(fill="x", pady=8, ipady=10)

        ttk.Button(frame, text="청년회관",
                   command=lambda: self.open_store("youth")).pack(fill="x", pady=8, ipady=10)

        ttk.Button(frame, text="서버 상태 확인", command=self.check_server).pack(pady=10)

    def check_server(self):
        try:
            r = requests.get(self.cfg["server_url"], timeout=10)
            r.raise_for_status()
            info = r.json()
            messagebox.showinfo("서버 상태", f"정상 작동중\n버전: {info['version']}")
        except Exception as e:
            messagebox.showerror("서버 오류", str(e))

    def open_store(self, store_id):
        for w in self.winfo_children():
            w.destroy()

        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True, padx=20, pady=20)

        ttk.Label(frame, text="재고 관리", font=("Malgun Gothic", 16, "bold")).pack(pady=10)

        ttk.Button(frame, text="부족 목록 보기",
                   command=lambda: self.open_shortage(store_id)).pack(fill="x", pady=8, ipady=10)

        ttk.Button(frame, text="뒤로가기", command=self.build_main).pack(pady=15)

    def open_shortage(self, store_id):
        try:
            r = requests.get(self.cfg["server_url"] + f"/api/shortages/{store_id}")
            data = r.json()["shortages"]
        except Exception as e:
            messagebox.showerror("오류", str(e))
            return

        txt = "\n".join([f"{x['name']} 부족: {x['need']}" for x in data])
        messagebox.showinfo("부족 목록", txt or "부족 없음")

if __name__ == "__main__":
    app = App()
    app.mainloop()
