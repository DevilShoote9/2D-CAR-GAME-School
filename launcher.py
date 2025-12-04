"""
launcher.py — cleaned
Minimal, focused comments added to explain high-level structure and important behaviours.
Remaining code is functionally identical to your supplied launcher.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
from pathlib import Path
import json
import importlib
import db
import threading
import time
from pathlib import Path as _Path

# optional pygame mixer for background music; launcher works without it
try:
    import pygame as pg_mixer
    PYGAME_AVAILABLE = True
except Exception:
    pg_mixer = None
    PYGAME_AVAILABLE = False

# Paths and UI constants
BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
CFG_FILE = BASE_DIR / "config.json"
WIDTH, HEIGHT = 480, 720

# Theme colours
BG = "#000000"
PANEL = "#0b0b0c"
BTN_BG = "#111316"
BTN_ACTIVE = "#1b1f22"
FG = "#e6eef0"
MUTED = "#8f9699"
ACCENT = "#00c0d6"

# Default configuration persisted to config.json
DEFAULT_CONFIG = {
    "selected_car": "player1.png",
    "difficulty": "Casual",
    "music_on": True,
    "music_volume": 0.6,
    "last_username": None,
    "session_active": False
}

# simple scaling helper for fonts/layout
SCALE = WIDTH / 480.0

def scaled(v):
    return max(8, int(v * SCALE))

# ensure minimal filesystem setup and DB
BASE_DIR.mkdir(parents=True, exist_ok=True)
ASSETS_DIR.mkdir(parents=True, exist_ok=True)
db.init_db()

# --- config helpers ---
def load_config():
    try:
        if CFG_FILE.exists():
            return json.loads(CFG_FILE.read_text(encoding='utf-8'))
    except Exception:
        pass
    return DEFAULT_CONFIG.copy()


def save_config(cfg):
    try:
        CFG_FILE.write_text(json.dumps(cfg, indent=2), encoding='utf-8')
    except Exception:
        pass

# Load an image from assets; return PhotoImage or None
def safe_load_image(name, w=None, h=None):
    p = ASSETS_DIR / name
    if not p.exists():
        return None
    try:
        im = Image.open(p).convert("RGBA")
        if w and h:
            im = im.resize((w, h), Image.LANCZOS)
        return ImageTk.PhotoImage(im)
    except Exception:
        return None


class DarkButton(tk.Button):
    """Small styled button used through the launcher UI."""
    def __init__(self, master=None, **kw):
        kw.setdefault('bg', BTN_BG)
        kw.setdefault('activebackground', BTN_ACTIVE)
        kw.setdefault('fg', FG)
        kw.setdefault('bd', 0)
        kw.setdefault('relief', 'flat')
        kw.setdefault('font', ('Helvetica', scaled(11), 'bold'))
        super().__init__(master, **kw)
        self._normal_bg = kw.get('bg', BTN_BG)
        self._normal_fg = kw.get('fg', FG)
        self._hover_bg = kw.get('activebackground', BTN_ACTIVE)
        self._hover_fg = ACCENT
        self.bind("<Enter>", lambda e: self._on_enter())
        self.bind("<Leave>", lambda e: self._on_leave())

    def _on_enter(self):
        try:
            self.configure(bg=self._hover_bg, fg=self._hover_fg)
        except Exception:
            pass

    def _on_leave(self):
        try:
            self.configure(bg=self._normal_bg, fg=self._normal_fg)
        except Exception:
            pass


class Launcher:
    """Main launcher application. Handles UI, settings and launching the game.

    Important behaviours documented in-line where necessary.
    """

    def __init__(self, root):
        self.root = root
        # set app icon
        try:
            self.root.iconbitmap("assets/logo.ico")
        except Exception as e:
            print("Icon load failed:", e)
        self.root.title("Car Dodger — Launcher")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        self.center_window(self.root, WIDTH, HEIGHT)
        self.root.protocol('WM_DELETE_WINDOW', self._on_quit)

        # load configuration and initial state
        self.cfg = load_config()
        self.user_id = None
        self.username = None
        self.selected_car = self.cfg.get("selected_car", DEFAULT_CONFIG["selected_car"])
        self.difficulty = self.cfg.get("difficulty", DEFAULT_CONFIG["difficulty"])
        self.music_on = self.cfg.get("music_on", True)
        self.music_volume = float(self.cfg.get("music_volume", 0.6))

        # detect music file in assets (few sensible names)
        self.music_file = None
        for name in ('bgmusic.mp3', 'menu_music.mp3', 'bg_launcher.mp3', 'menu_music_launcher.mp3'):
            p = ASSETS_DIR / name
            if p.exists():
                self.music_file = str(p)
                break

        self.logo_img = safe_load_image("logo.png", 200, 48)

        # mixer flags
        self._mixer_ready = False
        self._mixer_initialized = False

        # start mixer initialisation on a worker thread (non-blocking)
        self._init_mixer_async()

        # Enter key handler tracking
        self._enter_handler = None

        # build UI
        self.container = tk.Frame(self.root, bg=BG)
        self.container.pack(fill='both', expand=True)
        self._build_ui()
        self._bind_keys()

        # resume modal if previous session exists
        if self.cfg.get('last_username') and self.cfg.get('session_active'):
            self.root.after(150, self._show_resume_modal)
        else:
            self.show_login_minimal()

    # --- window / key helpers ---
    def center_window(self, root, w=WIDTH, h=HEIGHT):
        root.update_idletasks()
        ws = root.winfo_screenwidth(); hs = root.winfo_screenheight()
        x = (ws // 2) - (w // 2); y = (hs // 2) - (h // 2)
        root.geometry(f"{w}x{h}+{x}+{y}")

    def _bind_keys(self):
        self.root.bind("<Escape>", lambda e: self.on_escape())
        self.root.bind("<Control-q>", lambda e: self._on_quit())

    def _set_enter_binding(self, handler):
        try:
            if self._enter_handler:
                self.root.unbind('<Return>')
        except Exception:
            pass
        self._enter_handler = handler
        if handler:
            self.root.bind('<Return>', lambda e: handler())
            self.root.bind('<KP_Enter>', lambda e: handler())

    def _clear_enter_binding(self):
        try:
            self.root.unbind('<Return>')
            self.root.unbind('<KP_Enter>')
        except Exception:
            pass
        self._enter_handler = None

    # --- music status & initialisation ---
    def _update_music_status_label(self):
        """Update textual music status in the footer (UI thread only)."""
        status = "Music: "
        if not PYGAME_AVAILABLE:
            status += "disabled (pygame missing)"
        elif not self.music_file:
            status += "no file (place bgmusic.mp3 or menu_music.mp3 in ./assets)"
        else:
            try:
                if not getattr(pg_mixer, 'mixer', None) or not getattr(pg_mixer.mixer, 'get_init', lambda: False)():
                    status += "unavailable (mixer not init)"
                else:
                    busy = False
                    try:
                        busy = pg_mixer.mixer.music.get_busy()
                    except Exception:
                        busy = False
                    if self.cfg.get('music_on', True) and busy:
                        status += "playing"
                    elif not self.cfg.get('music_on', True):
                        status += "muted/paused"
                    else:
                        status += "loaded (not playing)"
            except Exception:
                status += "unknown"
        try:
            self.music_status_label.config(text=status)
        except Exception:
            pass

    def _init_mixer_async(self):
        """Initialise pygame.mixer in a background thread and attempt to load/play music.
        Non-blocking to keep the UI responsive.
        """
        if not PYGAME_AVAILABLE or not self.music_file:
            self._mixer_ready = False
            try: self.root.after(0, self._update_music_status_label)
            except Exception: pass
            return

        def _init():
            try:
                if not getattr(pg_mixer.mixer, 'get_init', lambda: False)():
                    pg_mixer.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
                self._mixer_initialized = True
                try:
                    pg_mixer.mixer.music.load(self.music_file)
                    pg_mixer.mixer.music.set_volume(self.music_volume)
                    self._mixer_ready = True
                    if self.music_on:
                        try:
                            pg_mixer.mixer.music.play(-1)
                            time.sleep(0.05)  # brief grace so get_busy() is reliable on some platforms
                        except Exception:
                            pass
                except Exception:
                    self._mixer_ready = False
            except Exception:
                self._mixer_initialized = False
                self._mixer_ready = False
            try:
                self.root.after(0, self._update_music_status_label)
            except Exception:
                pass

        threading.Thread(target=_init, daemon=True).start()

    def _reinit_mixer_if_needed(self):
        """Ensure pygame.mixer is initialized and launcher music is loaded/playing."""
        if not PYGAME_AVAILABLE or not self.music_file:
            return

        try:
            # if mixer was quit by the game, re-init it
            if not getattr(pg_mixer.mixer, 'get_init', lambda: False)():
                pg_mixer.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)

            # try to (re)load the music file
            try:
                pg_mixer.mixer.music.load(self.music_file)
            except Exception:
                # if load fails, leave it (update label will reflect no file)
                pass

            # set volume and start playing if user wants music
            pg_mixer.mixer.music.set_volume(self.cfg.get('music_volume', self.music_volume))
            if self.cfg.get('music_on', True):
                try:
                    if not pg_mixer.mixer.music.get_busy():
                        pg_mixer.mixer.music.play(-1)
                except Exception:
                    pass

        except Exception:
            # be defensive: ignore errors but ensure UI label updates
            pass
        finally:
            try:
                self.root.after(0, self._update_music_status_label)
            except Exception:
                pass


    # --- UI build ---
    def _build_ui(self):
        # header
        header = tk.Frame(self.container, bg=BG, height=70)
        header.pack(fill='x', pady=(8,4))
        header.pack_propagate(False)
        if self.logo_img:
            tk.Label(header, image=self.logo_img, bg=BG).pack(side='left', padx=(12,6))
        tk.Label(header, text="CAR DODGER", bg=BG, fg=ACCENT, font=('Orbitron', scaled(18), 'bold')).pack()

        sep = tk.Frame(self.container, bg='#071214', height=4)
        sep.pack(fill='x')

        main = tk.Frame(self.container, bg=BG)
        main.pack(fill='both', expand=True, padx=8, pady=(6,8))

        nav_w = 120
        self.nav = tk.Frame(main, bg=PANEL, width=nav_w)
        self.nav.pack(side='left', fill='y', padx=(0,8))
        self.nav.pack_propagate(False)

        # profile block
        prof = tk.Frame(self.nav, bg=PANEL)
        prof.pack(fill='x', pady=(8,4), padx=6)
        self.lbl_profile = tk.Label(prof, text="Not logged in", bg=PANEL, fg=FG, font=('Helvetica', scaled(11), 'bold'))
        self.lbl_profile.pack(anchor='w')
        self.lbl_profile_sub = tk.Label(prof, text="Please login or sign up", bg=PANEL, fg=MUTED, font=('Arial', scaled(8)))
        self.lbl_profile_sub.pack(anchor='w')

        # navigation buttons
        nav_items = [
            ("Play", self.show_play),
            ("Garage", self.show_garage),
            ("High Scores", self.show_highscores),
            ("Settings", self.show_settings),
            ("Help", self.show_help),
            ("Logout", self.logout)
        ]
        for text, cmd in nav_items:
            b = DarkButton(self.nav, text=text, width=14, command=cmd)
            b.pack(fill='x', padx=6, pady=4)

        # content card
        self.card = tk.Frame(main, bg=PANEL, padx=10, pady=10)
        self.card.pack(side='left', fill='both', expand=True)

        # footer (music status + quit)
        footer = tk.Frame(self.container, bg=BG, height=44)
        footer.pack(fill='x')
        footer.pack_propagate(False)

        self.music_status_label = tk.Label(footer, text='', bg=BG, fg=MUTED, font=('Arial', scaled(9)))
        self.music_status_label.pack(side='left', padx=10, pady=6)

        DarkButton(footer, text="Quit", width=10, command=self._on_quit).pack(side='right', padx=10, pady=6)
        self._update_music_status_label()

        # auth frame (top-right)
        self.auth_frame = tk.Frame(self.card, bg=PANEL)
        self.auth_frame.pack(fill='x', anchor='ne')
        self._build_auth_widgets()

    def _build_auth_widgets(self):
        for c in self.auth_frame.winfo_children():
            c.destroy()
        if self.user_id:
            tk.Label(self.auth_frame, text=f"{self.username}", bg=PANEL, fg=FG, font=('Arial', scaled(9), 'bold')).pack(side='left', padx=(0,6))
            tk.Label(self.auth_frame, text="●", bg=PANEL, fg=ACCENT, font=('Arial', scaled(9))).pack(side='left')
        else:
            DarkButton(self.auth_frame, text="Login", width=9, command=self.show_login_minimal).pack(side='right', padx=(6,0))
            DarkButton(self.auth_frame, text="Sign Up", width=9, command=self.show_signup_minimal).pack(side='right', padx=(0,6))

    def clear_card(self):
        for c in list(self.card.winfo_children()):
            if c is self.auth_frame: continue
            try: c.destroy()
            except Exception: pass
        self.auth_frame.pack_forget(); self.auth_frame.pack(fill='x', anchor='ne')
        self._clear_enter_binding()

    # --- auth / resume modal ---
    def _show_resume_modal(self):
        user = self.cfg.get('last_username')
        if not user:
            return self.show_login_minimal()
        dlg = tk.Toplevel(self.root)
        dlg.title('Resume Session'); dlg.transient(self.root); dlg.grab_set(); dlg.resizable(False, False)
        self.center_window(dlg, 360, 190)

        top = tk.Frame(dlg, bg=PANEL, padx=12, pady=10)
        top.pack(fill='both', expand=True)
        tk.Label(top, text='Resume previous session?', bg=PANEL, fg=FG, font=('Helvetica', scaled(12), 'bold')).pack(anchor='w')
        tk.Label(top, text=f'User: {user}', bg=PANEL, fg=MUTED, font=('Arial', scaled(9))).pack(anchor='w', pady=(6,0))
        tk.Label(top, text='Enter password to resume:', bg=PANEL, fg=MUTED, font=('Arial', scaled(9))).pack(anchor='w', pady=(8,0))
        pwd = tk.Entry(top, show='*', bg="#070708", fg=FG, insertbackground=FG, relief='flat', font=('Arial', scaled(11)))
        pwd.pack(fill='x', pady=(6,8))

        def do_resume():
            pw = pwd.get().strip()
            if not pw:
                messagebox.showerror('Error', 'Enter password', parent=dlg); return
            row = db.verify_user(user, pw)
            if row:
                self.user_id, car = row; self.username = user; self.selected_car = car or self.selected_car
                self.cfg['session_active'] = True; self.cfg['last_username'] = user; save_config(self.cfg)
                dlg.destroy(); self._build_auth_widgets(); self.show_menu_view()
            else:
                messagebox.showerror('Error', 'Wrong password', parent=dlg)

        btns = tk.Frame(top, bg=PANEL); btns.pack(fill='x', pady=(6,0))
        DarkButton(btns, text='Resume', width=12, command=do_resume).pack(side='left')
        DarkButton(btns, text='Back', width=12, command=lambda: (dlg.destroy(), self.show_login_minimal())).pack(side='left', padx=8)

        dlg.bind('<Return>', lambda e: do_resume())
        dlg.bind('<Escape>', lambda e: (dlg.destroy(), self.show_login_minimal()))
        pwd.focus_set()

    # --- login / signup views ---
    def show_login_minimal(self):
        self.clear_card(); self._build_auth_widgets()
        tk.Label(self.card, text='Login', bg=PANEL, fg=FG, font=('Helvetica', scaled(13), 'bold')).pack(anchor='w', pady=(0,6))
        frm = tk.Frame(self.card, bg=PANEL); frm.pack(fill='x')
        tk.Label(frm, text='Username', bg=PANEL, fg=MUTED, font=('Arial', scaled(9))).pack(anchor='w')
        self.e_user = tk.Entry(frm, bg="#070708", fg=FG, insertbackground=FG, relief='flat', font=('Arial', scaled(11)))
        self.e_user.pack(fill='x', pady=(4,8))
        tk.Label(frm, text='Password', bg=PANEL, fg=MUTED, font=('Arial', scaled(9))).pack(anchor='w')
        self.e_pass = tk.Entry(frm, show='*', bg="#070708", fg=FG, insertbackground=FG, relief='flat', font=('Arial', scaled(11)))
        self.e_pass.pack(fill='x', pady=(4,10))
        row = tk.Frame(self.card, bg=PANEL); row.pack(fill='x', pady=(6,0))
        DarkButton(row, text='Login', width=12, command=self.do_login).pack(side='left')
        DarkButton(row, text='Sign Up', width=12, command=self.show_signup_minimal).pack(side='left', padx=(8,0))
        tk.Label(self.card, text='Ctrl+Q to quit', bg=PANEL, fg=MUTED, font=('Arial', scaled(8))).pack(side='bottom', anchor='w', pady=(12,0))

        self._set_enter_binding(self.do_login)
        self.e_pass.bind('<Return>', lambda e: self.do_login())
        self.e_user.focus_set()

    def show_signup_minimal(self):
        self.clear_card(); self._build_auth_widgets()
        tk.Label(self.card, text='Create Account', bg=PANEL, fg=FG, font=('Helvetica', scaled(13), 'bold')).pack(anchor='w', pady=(0,6))
        frm = tk.Frame(self.card, bg=PANEL); frm.pack(fill='x')
        tk.Label(frm, text='Username', bg=PANEL, fg=MUTED, font=('Arial', scaled(9))).pack(anchor='w')
        self.s_user = tk.Entry(frm, bg="#070708", fg=FG, insertbackground=FG, relief='flat', font=('Arial', scaled(11)))
        self.s_user.pack(fill='x', pady=(4,8))
        tk.Label(frm, text='Password', bg=PANEL, fg=MUTED, font=('Arial', scaled(9))).pack(anchor='w')
        self.s_pass = tk.Entry(frm, show='*', bg="#070708", fg=FG, insertbackground=FG, relief='flat', font=('Arial', scaled(11)))
        self.s_pass.pack(fill='x', pady=(4,10))
        row = tk.Frame(self.card, bg=PANEL); row.pack(fill='x', pady=(6,0))
        DarkButton(row, text='Create', width=12, command=self.create_account).pack(side='left')
        DarkButton(row, text='Back', width=12, command=self.show_login_minimal).pack(side='left', padx=(8,0))

        self._set_enter_binding(self.create_account)
        self.s_pass.bind('<Return>', lambda e: self.create_account())
        self.s_user.focus_set()

    # --- main menu / play flow ---
    def show_menu_view(self):
        self._build_auth_widgets()
        self.lbl_profile.config(text=f"Welcome, {self.username}" if self.username else 'Not logged in', fg=FG)
        self.lbl_profile_sub.config(text="", fg=MUTED)
        self.show_play()

    def show_play(self):
        self.clear_card(); self._build_auth_widgets()
        tk.Label(self.card, text='Play', bg=PANEL, fg=FG, font=('Helvetica', scaled(16), 'bold')).pack(anchor='w')
        start_btn = DarkButton(self.card, text='▶  START', width=20, font=('Helvetica', scaled(18), 'bold'), command=self._ask_difficulty_then_start)
        start_btn.pack(pady=(8,6))
        if not self.user_id:
            tk.Label(self.card, text='Tip: You can play as guest — scores will not be saved.', bg=PANEL, fg=MUTED, font=('Arial', scaled(9))).pack(anchor='w', pady=(10,0))
        self._set_enter_binding(self._ask_difficulty_then_start)

    def _ask_difficulty_then_start(self):
        dlg = tk.Toplevel(self.root); dlg.transient(self.root); dlg.grab_set(); dlg.resizable(False, False)
        dlg.title('Choose Difficulty')
        self.center_window(dlg, 360, 220)

        hdr = tk.Frame(dlg, bg=PANEL, padx=10, pady=8); hdr.pack(fill='x')
        tk.Label(hdr, text='Choose Difficulty', bg=PANEL, fg=ACCENT, font=('Helvetica', scaled(12), 'bold')).pack(side='left')
        DarkButton(hdr, text='Close', width=8, command=lambda: dlg.destroy()).pack(side='right')

        body = tk.Frame(dlg, bg=PANEL, padx=12, pady=10); body.pack(fill='both', expand=True)
        var = tk.StringVar(value=self.difficulty)
        for d in ('Casual','Heroic','Nightmare'):
            rb = ttk.Radiobutton(body, text=d, value=d, variable=var, style='Dark.TRadiobutton')
            rb.pack(anchor='w', pady=4)

        ftr = tk.Frame(dlg, bg=PANEL, pady=8); ftr.pack(fill='x')
        DarkButton(ftr, text='Start', width=10, command=lambda: self._on_start_from_dialog(var, dlg)).pack(side='left', padx=8)
        DarkButton(ftr, text='Cancel', width=10, command=dlg.destroy).pack(side='left')

        dlg.bind('<Return>', lambda e: self._on_start_from_dialog(var, dlg))
        dlg.bind('<Escape>', lambda e: dlg.destroy())

    def _on_start_from_dialog(self, var, dlg):
        self.difficulty = var.get(); self.cfg['difficulty'] = self.difficulty; self.cfg['selected_car'] = self.selected_car; save_config(self.cfg)
        try:
            dlg.destroy()
        except Exception:
            pass
        if not self.user_id:
            if not messagebox.askyesno('Play as Guest?', "You are not logged in. Scores won't be saved. Continue?"):
                return
        self._launch_game()

    def _launch_game(self):
        # pause launcher music (if busy) while the game runs
        did_pause = False
        if PYGAME_AVAILABLE and getattr(pg_mixer, 'mixer', None) and getattr(pg_mixer.mixer, 'get_init', lambda: None)():
            try:
                busy = False
                try:
                    busy = pg_mixer.mixer.music.get_busy()
                except Exception:
                    busy = False
                if busy:
                    try:
                        pg_mixer.mixer.music.pause()
                        did_pause = True
                    except Exception:
                        did_pause = False
            except Exception:
                did_pause = False

        try:
            game = importlib.import_module('game')
        except Exception:
            import sys
            if 'game' in sys.modules:
                game = importlib.reload(sys.modules['game'])
            else:
                game = importlib.import_module('game')
        self.root.withdraw()
        try:
            game.run_game(self.username or 'Guest', self.user_id, self.selected_car, self.difficulty)
        except Exception as e:
            messagebox.showerror('Game error', f'Game crashed: {e}')
        finally:
            self.root.deiconify()

            # re-init mixer if the game quit it
            try:
                self._reinit_mixer_if_needed()
            except Exception:
                pass

            # resume launcher music if it was paused and user setting allows
            if did_pause and PYGAME_AVAILABLE and getattr(pg_mixer, 'mixer', None) and getattr(pg_mixer.mixer, 'get_init', lambda: False)():
                try:
                    if self.cfg.get('music_on', True):
                        pg_mixer.mixer.music.unpause()
                except Exception:
                    pass

            self.show_menu_view()


    # --- garage ---
    def show_garage(self):
        self.clear_card(); self._build_auth_widgets()
        tk.Label(self.card, text='Garage', bg=PANEL, fg=FG, font=('Helvetica', scaled(14), 'bold')).pack(anchor='w')
        car_files = [p.name for p in ASSETS_DIR.glob('player*.png')]
        if not car_files:
            car_files = ['player1.png','player2.png','player3.png','player4.png']
        grid = tk.Frame(self.card, bg=PANEL); grid.pack(fill='both', expand=True, pady=(8,6))
        thumb_w,thumb_h = 80,120

        thumbs_container = tk.Frame(grid, bg=PANEL); thumbs_container.pack(side='left', fill='y', padx=(0,8))
        canvas = tk.Canvas(thumbs_container, bg=PANEL, bd=0, highlightthickness=0, width=120)
        scrollbar = ttk.Scrollbar(thumbs_container, orient='vertical', command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=PANEL)
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        def _on_mousewheel_windows(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        def _on_mousewheel_unix(event):
            if event.num == 4:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                canvas.yview_scroll(1, "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel_windows)
        canvas.bind_all("<Button-4>", _on_mousewheel_unix)
        canvas.bind_all("<Button-5>", _on_mousewheel_unix)

        for cf in car_files:
            fr = tk.Frame(scrollable_frame, bg=PANEL, pady=4); fr.pack()
            img = safe_load_image(cf, thumb_w, thumb_h)
            if img:
                lbl = tk.Label(fr, image=img, bg=PANEL); lbl.image = img; lbl.pack()
            else:
                c = tk.Canvas(fr, width=thumb_w, height=thumb_h, bg='#070708', bd=0, highlightthickness=0)
                c.create_rectangle(4,4,thumb_w-4,thumb_h-4, outline=MUTED); c.pack()
            DarkButton(fr, text='Select', width=10, command=lambda f=cf: self._select_car_from_garage(f)).pack(pady=4)
        preview = tk.Frame(grid, bg=PANEL); preview.pack(side='left', fill='both', expand=True)
        tk.Label(preview, text='Preview', bg=PANEL, fg=MUTED).pack(anchor='nw')
        self.preview_canvas = tk.Canvas(preview, width=160, height=240, bg='#070708', bd=0, highlightthickness=0)
        self.preview_canvas.pack(pady=8)
        self._render_preview(self.selected_car, w=160, h=240)
        btns = tk.Frame(preview, bg=PANEL); btns.pack(anchor='w', pady=(8,0))
        DarkButton(btns, text='Apply & Save', width=12, command=self._apply_garage_selection).pack(side='left')
        DarkButton(btns, text='Back', width=10, command=self.show_menu_view).pack(side='left', padx=8)

    def _select_car_from_garage(self, filename):
        self.selected_car = filename; self._render_preview(filename, w=160, h=240)

    def _render_preview(self, filename, w=160, h=240):
        try:
            self.preview_canvas.delete('all')
        except Exception:
            pass
        img = safe_load_image(filename, w, h)
        if img:
            self.preview_canvas.create_image(w//2, h//2, image=img); self.preview_canvas.image = img
        else:
            self.preview_canvas.create_rectangle(4,4,w-4,h-4, outline=MUTED)

    def _apply_garage_selection(self):
        # persist selection in config and DB (if logged in)
        self.cfg['selected_car'] = self.selected_car
        save_config(self.cfg)
        if self.user_id:
            try:
                db.set_user_car(self.user_id, self.selected_car)
            except Exception:
                pass

        # present a nicer label for the selected asset name
        stem = _Path(self.selected_car).stem
        nice = stem.replace('_', ' ').strip().title()
        import re
        nice = re.sub(r'([A-Za-z])([0-9])', r'\1 \2', nice)

        messagebox.showinfo('Garage', f'{nice} selected.')
        self.show_menu_view()

    # --- leaderboards / settings / help ---
    def show_highscores(self):
        rows_all = db.top_scores(limit=50, mode=None, distinct=True)
        rows_casual = db.top_scores(limit=50, mode='Casual', distinct=True)
        rows_heroic = db.top_scores(limit=50, mode='Heroic', distinct=True)
        rows_night = db.top_scores(limit=50, mode='Nightmare', distinct=True)
        w = tk.Toplevel(self.root); w.title('High Scores'); w.configure(bg=BG); w.transient(self.root); w.grab_set(); w.resizable(False, False)
        self.center_window(w, 560, 460)

        hdr = tk.Frame(w, bg=PANEL, pady=8, padx=10); hdr.pack(fill='x')
        tk.Label(hdr, text='Leaderboards', bg=PANEL, fg=ACCENT, font=('Helvetica', scaled(12), 'bold')).pack(side='left')

        s = ttk.Style(w); s.theme_use('clam')
        s.configure('Black.Treeview', background=PANEL, fieldbackground=PANEL, foreground=FG, rowheight=20)
        s.configure('Black.Treeview.Heading', background=BTN_BG, foreground=FG)

        nb = ttk.Notebook(w); nb.pack(fill='both', expand=True, padx=8, pady=8)

        def make_tab(rows):
            frame = tk.Frame(nb, bg=PANEL)
            tree = ttk.Treeview(frame, columns=('rank','player','score','mode','date'), show='headings', height=14, style='Black.Treeview')
            tree.heading('rank', text='Rank'); tree.heading('player', text='Player'); tree.heading('score', text='Score'); tree.heading('mode', text='Mode'); tree.heading('date', text='Date')
            tree.column('rank', width=50, anchor='center'); tree.column('player', width=160, anchor='w')
            tree.column('score', width=80, anchor='e'); tree.column('mode', width=90, anchor='center'); tree.column('date', width=100, anchor='center')
            tree.pack(fill='both', expand=True, padx=6, pady=6)
            if not rows:
                tree.insert('', 'end', values=(1, '---', 0, '---', '---'))
            else:
                rnk = 1
                for r in rows:
                    uname, sc, mode, created = r; created_date = (created or '')[:10]
                    uname_disp = uname if len(uname) <= 20 else uname[:17] + '...'
                    tree.insert('', 'end', values=(rnk, uname_disp, sc, mode or '-', created_date)); rnk += 1
            return frame

        nb.add(make_tab(rows_all), text='All')
        nb.add(make_tab(rows_casual), text='Casual')
        nb.add(make_tab(rows_heroic), text='Heroic')
        nb.add(make_tab(rows_night), text='Nightmare')

        ftr = tk.Frame(w, bg=BG, pady=6); ftr.pack(fill='x')
        DarkButton(ftr, text='Close', width=12, command=w.destroy).pack()
        w.bind('<Return>', lambda e: w.destroy()); w.bind('<Escape>', lambda e: w.destroy())

    def show_settings(self):
        self.clear_card(); self._build_auth_widgets()
        tk.Label(self.card, text='Settings', bg=PANEL, fg=FG, font=('Helvetica', scaled(14), 'bold')).pack(anchor='w')
        sp = tk.Frame(self.card, bg=PANEL); sp.pack(fill='x', pady=(8,6))
        music_frame = tk.Frame(sp, bg=PANEL); music_frame.pack(fill='x', pady=4)
        self.music_var = tk.BooleanVar(value=self.cfg.get('music_on', True))
        cb = ttk.Checkbutton(music_frame, text='Background music', variable=self.music_var, style='Dark.TCheckbutton')
        cb.pack(side='left')
        DarkButton(music_frame, text='Play/Pause', width=10, command=self._toggle_music).pack(side='left', padx=6)
        vol_frame = tk.Frame(sp, bg=PANEL); vol_frame.pack(fill='x', pady=4)
        tk.Label(vol_frame, text='Volume', bg=PANEL, fg=MUTED).pack(anchor='w')
        self.volume_var = tk.DoubleVar(value=self.cfg.get('music_volume', 0.6))
        vol = ttk.Scale(vol_frame, from_=0.0, to=1.0, orient='horizontal', variable=self.volume_var, command=self._on_volume_change)
        vol.pack(fill='x', padx=(0,8))
        row = tk.Frame(self.card, bg=PANEL); row.pack(fill='x', pady=(10,0))
        DarkButton(row, text='Save', width=10, command=self._save_settings).pack(side='left')
        DarkButton(row, text='Back', width=10, command=self.show_menu_view).pack(side='left', padx=8)

        self._set_enter_binding(self._save_settings)
        self.root.bind('<Escape>', lambda e: self.show_menu_view())

    def _toggle_music(self):
        self.music_on = not self.music_var.get(); self.music_var.set(self.music_on)
        self.cfg['music_on'] = self.music_on; save_config(self.cfg)
        if not PYGAME_AVAILABLE or not self.music_file:
            messagebox.showinfo('Music', 'pygame or music file not available; music control disabled.')
            self._update_music_status_label()
            return
        try:
            if not getattr(pg_mixer.mixer, 'get_init', lambda: False)():
                return
            if self.music_on:
                try:
                    busy = pg_mixer.mixer.music.get_busy()
                except Exception:
                    busy = False
                if not busy:
                    pg_mixer.mixer.music.play(-1)
                else:
                    pg_mixer.mixer.music.unpause()
                pg_mixer.mixer.music.set_volume(self.music_volume)
            else:
                pg_mixer.mixer.music.pause()
        except Exception:
            pass

        self._update_music_status_label()

    def _on_volume_change(self, _=None):
        v = float(self.volume_var.get()); self.music_volume = v; self.cfg['music_volume'] = v; save_config(self.cfg)
        if PYGAME_AVAILABLE and getattr(pg_mixer, 'mixer', None) and getattr(pg_mixer.mixer, 'get_init', lambda: False)():
            try: pg_mixer.mixer.music.set_volume(v)
            except Exception: pass

    def _save_settings(self):
        self.cfg['music_on'] = bool(self.music_var.get()); self.cfg['music_volume'] = float(self.volume_var.get()); save_config(self.cfg)
        if PYGAME_AVAILABLE and self.music_file:
            try:
                if not getattr(pg_mixer.mixer, 'get_init', lambda: False)():
                    pass
                else:
                    if self.cfg['music_on']:
                        try:
                            if not pg_mixer.mixer.music.get_busy():
                                pg_mixer.mixer.music.play(-1)
                            else:
                                pg_mixer.mixer.music.unpause()
                        except Exception:
                            try: pg_mixer.mixer.music.play(-1)
                            except Exception: pass
                    else:
                        pg_mixer.mixer.music.pause()
                    pg_mixer.mixer.music.set_volume(self.cfg['music_volume'])
            except Exception:
                pass
        messagebox.showinfo('Settings', 'Settings saved.')
        self._update_music_status_label()

    def show_help(self):
        w = tk.Toplevel(self.root); w.title('Help — Car Dodger'); w.configure(bg=BG); w.transient(self.root); w.grab_set(); w.resizable(False, False)
        self.center_window(w, 540, 420)
        hdr = tk.Frame(w, bg=PANEL, padx=10, pady=8); hdr.pack(fill='x')
        tk.Label(hdr, text='Help — Car Dodger', bg=PANEL, fg=ACCENT, font=('Helvetica', scaled(12), 'bold')).pack(side='left')
        DarkButton(hdr, text='Close', width=8, command=w.destroy).pack(side='right')

        txt = tk.Text(w, bg=PANEL, fg=FG, bd=0, wrap='word', font=('Arial', scaled(10)))
        txt.pack(fill='both', expand=True, padx=8, pady=(4,8))
        help_text = """Car Dodger — Help

Controls:
  - Left arrow / A : Move left one lane
  - Right arrow / D: Move right one lane
  - P              : Pause / Resume during gameplay
  - L              : Open in-game Leaderboards (pauses the game)
  - Esc            : Close menus / return to launcher menu
  - Mouse click    : Use buttons in menus

Gameplay:
  - Avoid enemy cars. If they collide with you (pixel-perfect or central hitbox), it's game over.
  - When an enemy passes your car, you get points:
      * Close pass (near center): +250
      * Regular pass: +150
  - Difficulty affects spawn speed, enemy speed, and max enemies.

Score & Leaderboards:
  - Leaderboards are per-mode and show the best score per player.
  - Dates shown are YYYY-MM-DD.
  - To post scores, be logged in before starting the game.
"""
        txt.insert('1.0', help_text); txt.configure(state='disabled')
        DarkButton(w, text='Close', width=10, command=w.destroy).pack(pady=6)
        w.bind('<Return>', lambda e: w.destroy()); w.bind('<Escape>', lambda e: w.destroy())

    # --- account management ---
    def create_account(self):
        u = getattr(self, 's_user', None) and self.s_user.get().strip()
        p = getattr(self, 's_pass', None) and self.s_pass.get().strip()
        if not u or not p: messagebox.showerror('Error', 'Enter username and password'); return
        ok = db.add_user(u, p)
        if ok:
            messagebox.showinfo('Success', 'Account created. Login now.')
            self.cfg['last_username'] = u; self.cfg['session_active'] = False; save_config(self.cfg); self.show_login_minimal()
        else:
            messagebox.showerror('Error', 'Username exists')

    def do_login(self):
        u = getattr(self, 'e_user', None) and self.e_user.get().strip()
        p = getattr(self, 'e_pass', None) and self.e_pass.get().strip()
        if not u or not p: messagebox.showerror('Error', 'Enter username and password'); return
        row = db.verify_user(u, p)
        if row:
            self.user_id, car = row; self.username = u; self.selected_car = car or self.selected_car
            self.cfg['last_username'] = u; self.cfg['session_active'] = True; self.cfg['selected_car'] = self.selected_car; save_config(self.cfg)
            self._build_auth_widgets(); self.show_menu_view()
        else:
            messagebox.showerror('Error', 'Invalid credentials')

    def pick_car(self, filename):
        self.selected_car = filename
        if self.user_id:
            try: db.set_user_car(self.user_id, filename)
            except Exception: pass
        self.cfg['selected_car'] = filename; save_config(self.cfg); self.show_menu_view()

    def logout(self):
        if not self.user_id: messagebox.showinfo('Logout', 'Not logged in.'); return
        self.user_id = None; self.username = None
        self.cfg.pop('last_username', None); self.cfg['session_active'] = False; save_config(self.cfg)
        self.selected_car = self.cfg.get('selected_car', DEFAULT_CONFIG['selected_car'])
        self._build_auth_widgets(); self.show_login_minimal()

    def _on_quit(self):
        # confirm then stop music and destroy window
        if messagebox.askokcancel("Quit", "Quit Car Dodger launcher?"):
            try:
                if PYGAME_AVAILABLE and getattr(pg_mixer, 'mixer', None):
                    try:
                        pg_mixer.mixer.music.stop()
                    except Exception:
                        pass
                    try:
                        pg_mixer.mixer.quit()
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                self.root.destroy()
            except Exception:
                pass


if __name__ == '__main__':
    root = tk.Tk()
    style = ttk.Style()
    try: style.theme_use('clam')
    except Exception: pass
    style.configure('Dark.TRadiobutton', background=PANEL, foreground=FG, font=('Arial', scaled(9)))
    style.configure('Dark.TCheckbutton', background=PANEL, foreground=FG, font=('Arial', scaled(9)))
    Launcher(root); root.mainloop()
