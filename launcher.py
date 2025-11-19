# launcher.py

import tkinter as tk
from tkinter import messagebox, ttk
from PIL import Image, ImageTk
from pathlib import Path
import json
import db
import importlib

BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
CFG_FILE = BASE_DIR / "config.json"

WIDTH, HEIGHT = 480, 720

db.init_db()

# Theme
BG = "#000000"           # full black background
PANEL = "#0b0b0c"        # panel slightly above black
BTN_BG = "#111316"
BTN_ACTIVE = "#1b1f22"
FG = "#e6eef0"
MUTED = "#8f9699"
ACCENT = "#00c0d6"

def center_window(root, w=WIDTH, h=HEIGHT):
    root.update_idletasks()
    ws = root.winfo_screenwidth(); hs = root.winfo_screenheight()
    x = (ws // 2) - (w // 2); y = (hs // 2) - (h // 2)
    root.geometry(f"{w}x{h}+{x}+{y}")

def load_config():
    try:
        if CFG_FILE.exists():
            return json.loads(CFG_FILE.read_text(encoding='utf-8'))
    except Exception:
        pass
    return {}

def save_config(cfg):
    try:
        CFG_FILE.write_text(json.dumps(cfg, indent=2), encoding='utf-8')
    except Exception:
        pass

def safe_load_image(name, w=None, h=None):
    p = ASSETS_DIR / name
    if not p.exists(): return None
    try:
        im = Image.open(p)
        if w and h: im = im.resize((w, h), Image.LANCZOS)
        return ImageTk.PhotoImage(im)
    except Exception:
        return None

class DarkButton(tk.Button):
    def __init__(self, master=None, **kw):
        kw.setdefault('bg', BTN_BG); kw.setdefault('activebackground', BTN_ACTIVE)
        kw.setdefault('fg', FG); kw.setdefault('bd', 0); kw.setdefault('relief', 'flat')
        kw.setdefault('font', ('Helvetica', 11, 'bold'))
        super().__init__(master, **kw)
        self.bind("<Enter>", lambda e: self.configure(bg=BTN_ACTIVE))
        self.bind("<Leave>", lambda e: self.configure(bg=BTN_BG))

class Launcher:
    def __init__(self, root):
        self.root = root
        self.root.title("Car Dodger")
        self.root.resizable(False, False)
        center_window(self.root)

        self.cfg = load_config()
        self.user_id = None
        self.username = None
        self.selected_car = self.cfg.get("selected_car", "player1.png")
        self.difficulty = self.cfg.get("difficulty", "Casual")
        self.in_resume = False

        self.player1_img = safe_load_image("player1.png", 96, 144)
        self.player2_img = safe_load_image("player2.png", 96, 144)

        self.container = tk.Frame(self.root, bg=BG); self.container.pack(fill='both', expand=True)

        # central escape handler — only allows menu if logged in; resume returns to login
        self.root.bind("<Escape>", self.on_escape)
        self.root.bind("<Control-q>", lambda e: self.root.quit())

        self._build_header(); self._build_card_area(); self._build_footer()

        if self.cfg.get('last_username') and self.cfg.get('session_active'):
            self.show_resume_prompt()
        else:
            self.show_login_minimal()

    def on_escape(self, event=None):
        if getattr(self, 'in_resume', False):
            self.show_login_minimal(); return "break"
        if self.user_id:
            self.show_menu(); return "break"
        return "break"

    def _build_header(self):
        header = tk.Frame(self.container, bg=BG, height=90); header.pack(fill='x', pady=(14,0))
        title = tk.Label(header, text="CAR DODGER", bg=BG, fg=ACCENT, font=('Orbitron', 20, 'bold'))
        title.pack(anchor='center')

    def _build_card_area(self):
        self.card = tk.Frame(self.container, bg=PANEL, padx=20, pady=20); self.card.pack(padx=28, pady=18, fill='both', expand=True)

    def _build_footer(self):
        footer = tk.Frame(self.container, bg=BG, height=80); footer.pack(fill='x', pady=(0,12))
        self.btn_start = DarkButton(footer, text="START", width=14, command=self.launch_game, state='disabled'); self.btn_start.pack(side='left', padx=18)
        self.btn_scores = DarkButton(footer, text="High Scores", width=12, command=self.show_highscores); self.btn_scores.pack(side='left')
        self.btn_quit = DarkButton(footer, text="Quit", width=10, command=self.root.quit); self.btn_quit.pack(side='right', padx=18)

    def clear_card(self):
        for c in list(self.card.winfo_children()):
            try: c.destroy()
            except Exception: pass

    def enable_start_if_logged(self):
        state = 'normal' if self.user_id else 'disabled'
        self.btn_start.configure(state=state)

    def show_resume_prompt(self):
        self.clear_card(); self.in_resume = True
        tk.Label(self.card, text="Resume previous session?", bg=PANEL, fg=FG, font=('Helvetica', 16, 'bold')).pack(anchor='w', pady=(0,6))
        last = self.cfg.get('last_username')
        tk.Label(self.card, text=f"User: {last}", bg=PANEL, fg=MUTED).pack(anchor='w', pady=(0,8))
        tk.Label(self.card, text="Enter password to resume session:", bg=PANEL, fg=MUTED).pack(anchor='w')
        pwd = tk.Entry(self.card, show='*', bg="#070708", fg=FG, insertbackground=FG, relief='flat', font=('Arial', 12)); pwd.pack(fill='x', pady=(6,10))
        def do_resume():
            pw = pwd.get().strip()
            if not pw: messagebox.showerror("Error", "Enter password"); return
            row = db.verify_user(last, pw)
            if row:
                self.user_id, car = row; self.username = last; self.selected_car = car or self.selected_car
                self.cfg['session_active'] = True; self.cfg['last_username'] = last; save_config(self.cfg)
                self.in_resume = False; self.show_menu()
            else:
                messagebox.showerror("Error", "Wrong password")
        DarkButton(self.card, text="Resume", width=12, command=do_resume).pack(side='left')
        DarkButton(self.card, text="Back", width=12, command=self.show_login_minimal).pack(side='left', padx=8)

    def show_login_minimal(self):
        self.in_resume = False
        self.clear_card()
        tk.Label(self.card, text="Login", bg=PANEL, fg=FG, font=('Helvetica', 16, 'bold')).pack(anchor='w', pady=(0,6))
        frm = tk.Frame(self.card, bg=PANEL); frm.pack(fill='x')
        tk.Label(frm, text="Username", bg=PANEL, fg=MUTED, font=('Arial', 10)).pack(anchor='w')
        self.e_user = tk.Entry(frm, bg="#070708", fg=FG, insertbackground=FG, relief='flat', font=('Arial', 12)); self.e_user.pack(fill='x', pady=(4,10))
        tk.Label(frm, text="Password", bg=PANEL, fg=MUTED, font=('Arial', 10)).pack(anchor='w')
        self.e_pass = tk.Entry(frm, show='*', bg="#070708", fg=FG, insertbackground=FG, relief='flat', font=('Arial', 12)); self.e_pass.pack(fill='x', pady=(4,12))
        row = tk.Frame(self.card, bg=PANEL); row.pack(fill='x', pady=(6,0))
        DarkButton(row, text="Login", width=12, command=self.do_login).pack(side='left')
        DarkButton(row, text="Sign Up", width=12, command=self.show_signup_minimal).pack(side='left', padx=(10,0))
        tk.Label(self.card, text="Ctrl+Q to quit", bg=PANEL, fg=MUTED, font=('Arial', 9)).pack(side='bottom', anchor='w', pady=(12,0))
        self.e_pass.bind("<Return>", lambda e: self.do_login()); self.e_user.focus_set()

    def show_signup_minimal(self):
        self.in_resume = False
        self.clear_card()
        tk.Label(self.card, text="Create Account", bg=PANEL, fg=FG, font=('Helvetica', 16, 'bold')).pack(anchor='w', pady=(0,6))
        frm = tk.Frame(self.card, bg=PANEL); frm.pack(fill='x')
        tk.Label(frm, text="Username", bg=PANEL, fg=MUTED, font=('Arial', 10)).pack(anchor='w')
        self.s_user = tk.Entry(frm, bg="#070708", fg=FG, insertbackground=FG, relief='flat', font=('Arial', 12)); self.s_user.pack(fill='x', pady=(4,10))
        tk.Label(frm, text="Password", bg=PANEL, fg=MUTED, font=('Arial', 10)).pack(anchor='w')
        self.s_pass = tk.Entry(frm, show='*', bg="#070708", fg=FG, insertbackground=FG, relief='flat', font=('Arial', 12)); self.s_pass.pack(fill='x', pady=(4,12))
        row = tk.Frame(self.card, bg=PANEL); row.pack(fill='x', pady=(6,0))
        DarkButton(row, text="Create", width=12, command=self.create_account).pack(side='left')
        DarkButton(row, text="Back", width=12, command=self.show_login_minimal).pack(side='left', padx=(10,0))
        self.s_pass.bind("<Return>", lambda e: self.create_account()); self.s_user.focus_set()

    def show_menu(self):
        self.in_resume = False
        self.clear_card()
        tk.Label(self.card, text=f"Welcome {self.username}", bg=PANEL, fg=FG, font=('Helvetica', 16, 'bold')).pack(anchor='w', pady=(0,8))

        tk.Label(self.card, text="Difficulty", bg=PANEL, fg=MUTED, font=('Arial', 10)).pack(anchor='w')
        self.diff_var = tk.StringVar(master=self.root, value=self.difficulty)
        diff_frame = tk.Frame(self.card, bg=PANEL); diff_frame.pack(fill='x', pady=(6,10))
        for d in ("Casual", "Heroic", "Nightmare"):
            r = ttk.Radiobutton(diff_frame, text=d, value=d, variable=self.diff_var, style='Dark.TRadiobutton'); r.pack(side='left', padx=(0,8))

        tk.Label(self.card, text="Car", bg=PANEL, fg=MUTED, font=('Arial', 10)).pack(anchor='w')
        cs_frame = tk.Frame(self.card, bg=PANEL); cs_frame.pack(fill='x', pady=(6,10))
        DarkButton(cs_frame, text="Car 1", width=12, command=lambda: self.pick_car('player1.png')).pack(side='left')
        DarkButton(cs_frame, text="Car 2", width=12, command=lambda: self.pick_car('player2.png')).pack(side='left', padx=(8,0))

        preview_frame = tk.Frame(self.card, bg=PANEL); preview_frame.pack(fill='x', pady=(6,8))
        if self.selected_car == 'player1.png' and self.player1_img:
            lblp = tk.Label(preview_frame, image=self.player1_img, bg=PANEL); lblp.image = self.player1_img; lblp.pack(side='left')
        elif self.selected_car == 'player2.png' and self.player2_img:
            lblp = tk.Label(preview_frame, image=self.player2_img, bg=PANEL); lblp.image = self.player2_img; lblp.pack(side='left')
        else:
            ph = tk.Canvas(preview_frame, width=96, height=144, bg="#070708", bd=0, highlightthickness=0); ph.create_rectangle(6,6,90,138, outline=MUTED); ph.pack(side='left')

        act_row = tk.Frame(self.card, bg=PANEL); act_row.pack(fill='x', pady=(10,0))
        DarkButton(act_row, text="Logout", width=12, command=self.logout).pack(side='left')
        DarkButton(act_row, text="High Scores", width=12, command=self.show_highscores).pack(side='left', padx=(8,0))

        self.difficulty = self.diff_var.get(); self.cfg['difficulty'] = self.difficulty; save_config(self.cfg)
        self.enable_start_if_logged()

    def show_highscores(self):
        # fetch mode-specific leaderboards (distinct -> one best per user)
        rows_all = db.top_scores(limit=50, mode=None, distinct=True)
        rows_casual = db.top_scores(limit=50, mode='Casual', distinct=True)
        rows_heroic = db.top_scores(limit=50, mode='Heroic', distinct=True)
        rows_night = db.top_scores(limit=50, mode='Nightmare', distinct=True)

        w = tk.Toplevel(self.root); w.title("High Scores"); w.configure(bg=BG); w.geometry("560x460"); center_window(w, 560, 460)

        # create a dedicated style for black theme
        s = ttk.Style(w)
        s.theme_use('clam')
        s.configure("Black.Treeview", background=PANEL, fieldbackground=PANEL, foreground=FG, rowheight=22)
        s.configure("Black.Treeview.Heading", background=BTN_BG, foreground=FG)
        s.map("Black.Treeview", background=[('selected', BTN_ACTIVE)], foreground=[('selected', FG)])

        nb = ttk.Notebook(w)
        nb.pack(fill='both', expand=True, padx=10, pady=10)

        def make_tab(rows):
            frame = tk.Frame(nb, bg=PANEL)
            tree = ttk.Treeview(frame, columns=("rank","player","score","mode","date"), show='headings', height=18, style="Black.Treeview")
            tree.heading("rank", text="Rank"); tree.heading("player", text="Player"); tree.heading("score", text="Score"); tree.heading("mode", text="Mode"); tree.heading("date", text="Date")
            tree.column("rank", width=60, anchor='center'); tree.column("player", width=180, anchor='w'); tree.column("score", width=100, anchor='e'); tree.column("mode", width=90, anchor='center'); tree.column("date", width=120, anchor='center')
            tree.pack(fill='both', expand=True, padx=8, pady=8)
            if not rows:
                tree.insert('', 'end', values=(1, '---', 0, '---', '---'))
            else:
                rnk = 1
                for r in rows:
                    uname, sc, mode, created = r
                    # date-only (YYYY-MM-DD) — slice first 10 chars from ISO
                    created_date = (created or '')[:10]
                    tree.insert('', 'end', values=(rnk, uname, sc, mode or '-', created_date))
                    rnk += 1
            return frame

        nb.add(make_tab(rows_all), text="All")
        nb.add(make_tab(rows_casual), text="Casual")
        nb.add(make_tab(rows_heroic), text="Heroic")
        nb.add(make_tab(rows_night), text="Nightmare")

        btn = DarkButton(w, text="Close", width=10, command=w.destroy); btn.pack(pady=6)

    def create_account(self):
        u = getattr(self, 's_user', None) and self.s_user.get().strip()
        p = getattr(self, 's_pass', None) and self.s_pass.get().strip()
        if not u or not p: messagebox.showerror("Error", "Enter username and password"); return
        ok = db.add_user(u, p)
        if ok:
            messagebox.showinfo("Success", "Account created. Login now.")
            self.cfg['last_username'] = u; self.cfg['session_active'] = False; save_config(self.cfg); self.show_login_minimal()
        else:
            messagebox.showerror("Error", "Username exists")

    def do_login(self):
        u = getattr(self, 'e_user', None) and self.e_user.get().strip()
        p = getattr(self, 'e_pass', None) and self.e_pass.get().strip()
        if not u or not p: messagebox.showerror("Error", "Enter username and password"); return
        row = db.verify_user(u, p)
        if row:
            self.user_id, car = row; self.username = u; self.selected_car = car or self.selected_car
            self.cfg['last_username'] = u; self.cfg['session_active'] = True; self.cfg['selected_car'] = self.selected_car; save_config(self.cfg)
            self.show_menu()
        else:
            messagebox.showerror("Error", "Invalid credentials")

    def pick_car(self, filename):
        self.selected_car = filename
        if self.user_id: db.set_user_car(self.user_id, filename)
        self.cfg['selected_car'] = filename; save_config(self.cfg); self.show_menu()

    def logout(self):
        self.user_id = None; self.username = None
        self.cfg.pop('last_username', None); self.cfg['session_active'] = False; save_config(self.cfg)
        self.selected_car = self.cfg.get("selected_car", "player1.png")
        self.enable_start_if_logged(); self.show_login_minimal()

    def launch_game(self):
        if not self.user_id or not self.username:
            messagebox.showwarning("Login required", "Please login before starting the game."); return
        try:
            dv = getattr(self, 'diff_var', None)
            self.difficulty = dv.get() if dv else self.difficulty
        except Exception:
            self.difficulty = self.difficulty
        self.cfg['difficulty'] = self.difficulty; self.cfg['selected_car'] = self.selected_car; save_config(self.cfg)

        try:
            game = importlib.import_module('game')
        except Exception:
            import sys
            if 'game' in sys.modules: game = importlib.reload(sys.modules['game'])
            else: game = importlib.import_module('game')

        self.root.withdraw()
        try:
            game.run_game(self.username, self.user_id, self.selected_car, self.difficulty)
        except Exception as e:
            messagebox.showerror("Game error", f"Game crashed: {e}")
        finally:
            self.root.deiconify(); self.show_menu()

if __name__ == "__main__":
    BASE_DIR.mkdir(parents=True, exist_ok=True); ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    root = tk.Tk(); root.configure(bg=BG); center_window(root)
    # configure ttk style AFTER root exists
    style = ttk.Style(); style.theme_use('clam')
    style.configure('Dark.TRadiobutton', background=PANEL, foreground=FG, font=('Arial', 10))
    style.map('Dark.TRadiobutton', background=[('active', PANEL)], foreground=[('active', FG)])
    Launcher(root); root.mainloop()
