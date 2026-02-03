import os, json, re, socket, ctypes, traceback, webbrowser
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import requests

LOCK_PORT = 48123
APP_TITLE = "김경영 재고 자동화"

DEFAULT_CONFIG = {
  "server_url": "https://stock-server-production-13ac.up.railway.app",
  "admin_token": "dldydtjq159",
  "last_store_id": "lab"
}

ADMIN_ID = "dldydtjq159"
ADMIN_PW = "tkfkd4026"
SESSION_MINUTES = 30

CONFIG_FILE = "config.json"
SESSION_FILE = "admin_session.json"

def ensure_single_instance():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", LOCK_PORT))
        s.listen(1)
        return s
    except:
        messagebox.showinfo("중복실행","이미 실행 중입니다.")
        raise SystemExit

def load_config():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE,"w",encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG,f,ensure_ascii=False,indent=2)
        return DEFAULT_CONFIG.copy()
    return json.load(open(CONFIG_FILE,"r",encoding="utf-8"))

def save_config(cfg):
    json.dump(cfg,open(CONFIG_FILE,"w",encoding="utf-8"),ensure_ascii=False,indent=2)

def session_save():
    expires = datetime.now()+timedelta(minutes=SESSION_MINUTES)
    json.dump({"expires_at":expires.isoformat()},
              open(SESSION_FILE,"w",encoding="utf-8"))

def session_load():
    if not os.path.exists(SESSION_FILE): return None
    s=json.load(open(SESSION_FILE))
    if datetime.fromisoformat(s["expires_at"])>=datetime.now():
        return s
    return None

def is_admin(): return session_load() is not None

def api_get(cfg,path):
    r=requests.get(cfg["server_url"]+path,timeout=20)
    r.raise_for_status()
    return r.json()

def api_put_admin(cfg,path,payload):
    r=requests.put(cfg["server_url"]+path,
                   headers={"x-admin-token":cfg["admin_token"]},
                   json=payload,timeout=20)
    r.raise_for_status()
    return r.json()

def api_post(cfg,path,payload):
    r=requests.post(cfg["server_url"]+path,json=payload,timeout=20)
    r.raise_for_status()
    return r.json()

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self.title(APP_TITLE)
        self.geometry("1100x720")
        self.configure(bg="#0b1220")
        self.container = ttk.Frame(self)
        self.container.pack(fill="both",expand=True,padx=16,pady=16)
        self.show_main()

    def clear(self):
        for w in self.container.winfo_children(): w.destroy()

    def show_main(self):
        self.clear()
        f=ttk.Frame(self.container); f.pack(fill="both",expand=True)

        ttk.Label(f,text="김경영 자동화 대시보드",
                   font=("Malgun Gothic",22,"bold")).pack(pady=20)

        row=ttk.Frame(f); row.pack(pady=20)

        ttk.Button(row,text="김경영 요리 연구소",style="Accent.TButton",
                   command=lambda:self.show_store("lab","김경영 요리 연구소")).pack(side="left",padx=10,ipady=10)
        ttk.Button(row,text="청년회관",style="Accent.TButton",
                   command=lambda:self.show_store("youth","청년회관")).pack(side="left",padx=10,ipady=10)
        ttk.Button(row,text="원가·순수익 계산",style="Accent.TButton",
                   command=self.show_cost).pack(side="left",padx=10,ipady=10)

        btn=ttk.Button(f,text="관리자 로그인",command=self.admin_login)
        btn.pack(pady=20)

    def admin_login(self):
        d=AdminLoginDialog(self); self.wait_window(d)

    def show_store(self,sid,name):
        self.current_store=sid
        self.current_name=name
        self.clear()
        StoreFrame(self.container,self,sid,name).pack(fill="both",expand=True)

    def show_cost(self):
        self.clear()
        CostFrame(self.container,self).pack(fill="both",expand=True)

class AdminLoginDialog(tk.Toplevel):
    def __init__(self,app):
        super().__init__(app); self.app=app
        self.title("관리자 로그인"); self.geometry("360x200")

        ttk.Label(self,text="아이디").pack()
        self.e1=tk.Entry(self); self.e1.pack()
        ttk.Label(self,text="비밀번호").pack()
        self.e2=tk.Entry(self,show="*"); self.e2.pack()

        ttk.Button(self,text="로그인",command=self.ok).pack(pady=10)

    def ok(self):
        if self.e1.get()==ADMIN_ID and self.e2.get()==ADMIN_PW:
            session_save()
            messagebox.showinfo("성공","로그인 성공")
            self.destroy()
        else:
            messagebox.showerror("실패","아이디/비번 오류")

class StoreFrame(ttk.Frame):
    def __init__(self,parent,app,sid,name):
        super().__init__(parent)
        self.app=app; self.sid=sid

        top=ttk.Frame(self); top.pack(fill="x")
        ttk.Label(top,text=name,font=("Malgun Gothic",18,"bold")).pack(side="left")
        ttk.Button(top,text="부족목록",command=self.open_short).pack(side="right")

        body=ttk.Frame(self); body.pack(fill="both",expand=True)

        left=ttk.Frame(body); left.pack(side="left",fill="y",padx=10)
        ttk.Button(left,text="재료").pack(fill="x",pady=5)
        ttk.Button(left,text="발주").pack(fill="x",pady=5)

        right=ttk.Frame(body); right.pack(side="right",fill="both",expand=True)
        self.notice=tk.Text(right,height=10)
        self.notice.pack(fill="both",expand=True)

    def open_short(self):
        ShortageDialog(self.app,self.sid)

class ShortageDialog(tk.Toplevel):
    def __init__(self,app,sid):
        super().__init__(app)
        self.title("부족목록"); self.geometry("900x500")
        self.sid=sid; self.app=app

        btn=ttk.Button(self,text="바탕화면 발주서 저장",command=self.save_order)
        btn.pack(pady=10)

        self.tree=ttk.Treeview(self,columns=("cat","name","cur","min","need","vendor","origin"),show="headings")
        for c in ["cat","name","cur","min","need","vendor","origin"]:
            self.tree.heading(c,text=c)
        self.tree.pack(fill="both",expand=True)
        self.refresh()

    def refresh(self):
        data=api_get(self.app.cfg,f"/api/shortages/{self.sid}")["shortages"]
        for r in data:
            self.tree.insert("","end",values=(
                r["category_label"],r["name"],r["current_stock"],
                r["min_stock"],r["need"],r["vendor"],r["origin"]
            ))

    def save_order(self):
        text="발주서 자동생성"
        fname=f"발주서_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
        path=os.path.join(os.path.expanduser("~"),"Desktop",fname)
        open(path,"w",encoding="utf-8").write(text)
        api_post(self.app.cfg,f"/api/orders/{self.sid}",{"text":text})
        messagebox.showinfo("저장",f"{path} 저장됨")

class CostFrame(ttk.Frame):
    def __init__(self,parent,app):
        super().__init__(parent)
        ttk.Label(self,text="원가·순수익 계산기",font=("Malgun Gothic",18)).pack(pady=10)
        ttk.Label(self,text="(예: 닭 2kg = 10000원)").pack()
        self.cost=tk.Entry(self); self.cost.pack()
        self.per=tk.Entry(self); self.per.pack()
        ttk.Button(self,text="계산",command=self.calc).pack(pady=10)
        self.res=tk.Label(self,text="결과: "); self.res.pack()

    def calc(self):
        try:
            cost=float(self.cost.get())
            per=float(self.per.get())
            profit=cost/per
            self.res.config(text=f"1인분 원가: {profit:.0f}원")
        except:
            self.res.config(text="입력 오류")

if __name__=="__main__":
    ensure_single_instance()
    app=App()
    app.mainloop()
