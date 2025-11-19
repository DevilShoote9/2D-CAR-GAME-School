# launcher.py
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import os
import db          # local module
import game        # local module (the pygame game)
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(BASE_DIR, "assets")
print("WORKING DIRECTORY:", os.getcwd())
print("FILES:", os.listdir())
print("BASE_DIR =", BASE_DIR)
print("ASSETS =", ASSETS)
print("assets folder exists?", os.path.exists(ASSETS))
print("player1=", os.path.exists(os.path.join(ASSETS, "player1.png")))
print("player2=", os.path.exists(os.path.join(ASSETS, "player2.png")))
print("enemy=", os.path.exists(os.path.join(ASSETS, "enemy.png")))
input("DEBUG: Press ENTER…")


ASSETS = 'assets'
WIDTH, HEIGHT = 480, 720

# ensure DB exists
db.init_db()

def load_tk_image(name, w=None, h=None):
    path = os.path.join(ASSETS, name)
    if os.path.exists(path):
        try:
            im = Image.open(path)
            if w and h:
                im = im.resize((w, h), Image.LANCZOS)
            return ImageTk.PhotoImage(im)
        except Exception:
            return None
    return None

class Launcher:
    def __init__(self, root):
        self.root = root
        self.root.title("Car Dodger Launcher")
        self.root.geometry(f"{WIDTH}x{HEIGHT}")
        self.root.resizable(False, False)

        # images (optional)
        self.intro_bg = load_tk_image('intro_bg.jpg', WIDTH, HEIGHT) or load_tk_image('intro_bg.png', WIDTH, HEIGHT)
        self.login_bg = load_tk_image('login_bg.jpg', WIDTH, HEIGHT) or load_tk_image('login_bg.png', WIDTH, HEIGHT)
        self.menu_bg  = load_tk_image('menu_bg.jpg', WIDTH, HEIGHT) or load_tk_image('menu_bg.png', WIDTH, HEIGHT)
        self.player1 = load_tk_image('player1.png', 120, 180)
        self.player2 = load_tk_image('player2.png', 120, 180)

        self.user_id = None
        self.username = None
        self.selected_car = 'player1.png'
        self.difficulty = 'Casual'

        self.main_frame = tk.Frame(root, width=WIDTH, height=HEIGHT)
        self.main_frame.pack(fill='both', expand=True)
        self.show_intro()

    def clear(self):
        for w in self.main_frame.winfo_children():
            w.destroy()

    def show_intro(self):
        self.clear()
        bg = tk.Label(self.main_frame, image=self.intro_bg) if self.intro_bg else tk.Label(self.main_frame, bg='#103040')
        bg.place(x=0,y=0, relwidth=1, relheight=1)
        tk.Label(self.main_frame, text="CAR DODGER", font=('Helvetica',32), fg='white', bg='#103040' if not self.intro_bg else None).place(relx=0.5, y=80, anchor='center')
        tk.Button(self.main_frame, text="Login / Play", width=16, command=self.show_login).place(relx=0.5, rely=0.75, anchor='center')
        tk.Button(self.main_frame, text="Quit", width=10, command=self.root.quit).place(relx=0.5, rely=0.85, anchor='center')

    def show_login(self):
        self.clear()
        bg = tk.Label(self.main_frame, image=self.login_bg) if self.login_bg else tk.Label(self.main_frame, bg='#223344')
        bg.place(x=0,y=0, relwidth=1, relheight=1)

        tk.Label(self.main_frame, text='Login', font=('Orbitron Black', 22), fg='white', bg='#223344' if not self.login_bg else None).place(relx=0.5, y=60, anchor='center')
        self.e_user = tk.Entry(self.main_frame, font=('Arial', 14))
        self.e_pass = tk.Entry(self.main_frame, show='*', font=('Arial', 14))
        self.e_user.place(relx=0.5, y=160, anchor='center', width=260)
        self.e_pass.place(relx=0.5, y=210, anchor='center', width=260)

        tk.Button(self.main_frame, text='Login', width=12, command=self.do_login).place(relx=0.39, y=270)
        tk.Button(self.main_frame, text='Sign Up', width=12, command=self.show_signup).place(relx=0.61, y=270)
        tk.Button(self.main_frame, text='Back', width=8, command=self.show_intro).place(x=10, y=10)

    def show_signup(self):
        self.clear()
        bg = tk.Label(self.main_frame, image=self.login_bg) if self.login_bg else tk.Label(self.main_frame, bg='#2b2b2b')
        bg.place(x=0,y=0, relwidth=1, relheight=1)

        tk.Label(self.main_frame, text='Sign Up', font=('Helvetica', 22), fg='white', bg='#2b2b2b' if not self.login_bg else None).place(relx=0.5, y=60, anchor='center')
        self.s_user = tk.Entry(self.main_frame, font=('Arial', 14))
        self.s_pass = tk.Entry(self.main_frame, show='*', font=('Arial', 14))
        self.s_user.place(relx=0.5, y=160, anchor='center', width=260)
        self.s_pass.place(relx=0.5, y=210, anchor='center', width=260)

        tk.Button(self.main_frame, text='Create Account', width=14, command=self.create_account).place(relx=0.5, y=270, anchor='center')
        tk.Button(self.main_frame, text='Back', width=8, command=self.show_login).place(x=10, y=10)

    def create_account(self):
        u = self.s_user.get().strip()
        p = self.s_pass.get().strip()
        if not u or not p:
            messagebox.showerror('Error', 'Enter username and password')
            return
        ok = db.add_user(u, p)
        if ok:
            messagebox.showinfo('Success', 'Account created. Login now.')
            self.show_login()
        else:
            messagebox.showerror('Error', 'Username exists')

    def do_login(self):
        u = self.e_user.get().strip()
        p = self.e_pass.get().strip()
        if not u or not p:
            messagebox.showerror('Error', 'Enter username/password')
            return
        row = db.verify_user(u, p)
        if row:
            self.user_id, car = row
            self.username = u
            self.selected_car = car or 'player1.png'
            self.show_menu()
        else:
            messagebox.showerror('Error', 'Invalid credentials')

    def show_menu(self):
        self.clear()
        bg = tk.Label(self.main_frame, image=self.menu_bg) if self.menu_bg else tk.Label(self.main_frame, bg='#123')
        bg.place(x=0,y=0, relwidth=1, relheight=1)

        tk.Label(self.main_frame, text=f'Welcome, {self.username}', font=('Helvetica', 18), fg='white').place(relx=0.5, y=60, anchor='center')

        y = 140
        for diff in ('Casual', 'Heroic', 'Nightmare'):
            tk.Button(self.main_frame, text=diff, width=18, command=lambda d=diff: self.select_diff(d)).place(relx=0.5, y=y, anchor='center')
            y += 60

        tk.Button(self.main_frame, text='High Scores', width=14, command=self.show_highscores).place(relx=0.5, y=y+20, anchor='center')
        tk.Button(self.main_frame, text='Select Car', width=14, command=self.show_car_select).place(relx=0.25, y=y+90, anchor='center')
        tk.Button(self.main_frame, text='Logout', width=14, command=self.logout).place(relx=0.75, y=y+90, anchor='center')

    def select_diff(self, d):
        self.difficulty = d
        self.show_car_select()

    def show_highscores(self):
        self.clear()
        rows = db.top_scores(10)
        tk.Label(self.main_frame, text='High Scores', font=('Helvetica', 20)).place(relx=0.5, y=40, anchor='center')
        y = 100
        for r in rows:
            txt = f'{r[0]} - {r[1]} ({r[2]})'
            tk.Label(self.main_frame, text=txt, font=('Arial', 12)).place(relx=0.5, y=y, anchor='center')
            y += 28
        tk.Button(self.main_frame, text='Back', width=10, command=self.show_menu).place(x=10, y=10)

    def show_car_select(self):
        self.clear()
        tk.Label(self.main_frame, text='Select Your Car', font=('Helvetica', 20)).place(relx=0.5, y=40, anchor='center')

        x1, x2 = 140, 340
        if self.player1:
            lbl1 = tk.Label(self.main_frame, image=self.player1)
            lbl1.place(x=x1-60, y=120)
        else:
            tk.Label(self.main_frame, bg='red', width=10, height=6).place(x=x1-60, y=120)
        if self.player2:
            lbl2 = tk.Label(self.main_frame, image=self.player2)
            lbl2.place(x=x2-60, y=120)
        else:
            tk.Label(self.main_frame, bg='green', width=10, height=6).place(x=x2-60, y=120)

        tk.Button(self.main_frame, text='Pick Car 1', command=lambda: self.pick_car('player1.png')).place(x=x1-40, y=330)
        tk.Button(self.main_frame, text='Pick Car 2', command=lambda: self.pick_car('player2.png')).place(x=x2-40, y=330)

        tk.Button(self.main_frame, text='Start Game', width=16, command=self.launch_game).place(relx=0.5, y=420, anchor='center')
        tk.Button(self.main_frame, text='Back', width=10, command=self.show_menu).place(x=10, y=10)

    def pick_car(self, filename):
        self.selected_car = filename
        if self.user_id:
            db.set_user_car(self.user_id, filename)
        messagebox.showinfo('Selected', f'{filename} selected')

    def launch_game(self):
        # close Tk window and start pygame game (in same process)
        self.root.withdraw()  # hide launcher
        try:
            game.run_game(self.username, self.user_id, self.selected_car, self.difficulty)
        except Exception as e:
            messagebox.showerror('Error', f'Game crashed: {e}')
        finally:
            self.root.deiconify()
            self.show_menu()

    def logout(self):
        self.user_id = None
        self.username = None
        self.selected_car = 'player1.png'
        self.show_intro()

if __name__ == '__main__':
    try:
        # create assets dir if not exists
        BASE = os.path.dirname(os.path.abspath(__file__))
        ASSETS = os.path.join(BASE, 'assets')

        if not os.path.exists(ASSETS):
            os.makedirs(ASSETS)

        root = tk.Tk()
        Launcher(root)
        root.mainloop()

    except Exception as e:
        print("ERROR:", e)
        input("Press ENTER to close...")



