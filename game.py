# game.py
import pygame as pg
from pathlib import Path
import random as rnd
import db
from db import save_score
import time
import json

# --- Paths & constants ---
BASE_DIR = Path(__file__).resolve().parent
ASSETS = BASE_DIR / "assets"
CFG_FILE = BASE_DIR / "config.json"

FPS = 60
SCREEN_W, SCREEN_H = 480, 720
LANES = 3
PLAYER_W, PLAYER_H = 80, 140
ENEMY_W, ENEMY_H = 80, 140
CLOSE_THRESH = 80

DIFF = {
    'Casual':    {'min': 4.0,  'max': 6.0,  'spawn_ms': 1200, 'scroll': 4, 'max_enemies': 5},
    'Heroic':    {'min': 6.0,  'max': 8.0,  'spawn_ms': 900,  'scroll': 5, 'max_enemies': 7},
    'Nightmare': {'min': 8.0,  'max': 12.0, 'spawn_ms': 550, 'scroll': 8, 'max_enemies': 10}
}

# Theme colors
ACCENT = (0, 192, 214)
DARK_BG = (8, 8, 10)
DARK_PANEL = (16, 16, 18)
WHITE = (255, 255, 255)
MUTED = (180, 180, 180)

# Default config used when file missing
DEFAULT_CFG = {
    "music_on": True,
    "music_volume": 0.6,
    "selected_car": "player1.png",
    "difficulty": "Casual"
}

# --- Config helpers ---
def load_config():
    try:
        if CFG_FILE.exists():
            return json.loads(CFG_FILE.read_text(encoding='utf-8'))
    except Exception:
        pass
    return DEFAULT_CFG.copy()

def save_config(cfg):
    try:
        CFG_FILE.write_text(json.dumps(cfg, indent=2), encoding='utf-8')
    except Exception:
        pass

# Safe color helper for alpha
def rgba(col, a):
    try:
        r, g, b = int(col[0]), int(col[1]), int(col[2])
    except Exception:
        r, g, b = 0, 0, 0
    return (r, g, b, int(a))

# Safe image loader: returns Surface (or placeholder surface) scaled if requested
def load_image(name, w=None, h=None):
    path = ASSETS / name
    if not path.exists():
        surf = pg.Surface((w or 80, h or 80), pg.SRCALPHA)
        surf.fill((120, 0, 0, 255))
        return surf
    img = pg.image.load(str(path)).convert_alpha()
    if w and h:
        img = pg.transform.smoothscale(img, (w, h))
    return img

# --- UI widgets (minimal) ---
class Button:
    """Simple rectangular button with hover pulse."""
    def __init__(self, rect, text, font, base_color=(30,30,34), hover_color=None):
        self.rect = pg.Rect(rect)
        self.text = text
        self.font = font
        self.base_color = base_color
        if hover_color is None:
            hover_color = (
                min(255, base_color[0] + 30),
                min(255, base_color[1] + 30),
                min(255, base_color[2] + 30)
            )
        self.hover_color = hover_color
        self.hovering = False
        self.pulse = 0.0

    def update(self, mouse_pos, dt):
        self.hovering = self.rect.collidepoint(mouse_pos)
        if self.hovering:
            self.pulse = min(1.0, self.pulse + dt * 0.008)
        else:
            self.pulse = max(0.0, self.pulse - dt * 0.015)

    def draw(self, surf):
        w, h = self.rect.w, self.rect.h
        center = self.rect.center
        draw_rect = pg.Rect(0, 0, w, h); draw_rect.center = center

        color = (
            int(self.base_color[0] + (self.hover_color[0] - self.base_color[0]) * (self.pulse * 0.5)),
            int(self.base_color[1] + (self.hover_color[1] - self.base_color[1]) * (self.pulse * 0.5)),
            int(self.base_color[2] + (self.hover_color[2] - self.base_color[2]) * (self.pulse * 0.5))
        )

        pg.draw.rect(surf, (20,20,20), draw_rect, border_radius=10)
        pg.draw.rect(surf, color, draw_rect.inflate(-2, -2), border_radius=9)

        shadow = self.font.render(self.text, True, (0,0,0))
        txt_color = ACCENT if self.hovering else WHITE
        txt = self.font.render(self.text, True, txt_color)
        surf.blit(shadow, (center[0] - shadow.get_width()//2 + 1, center[1] - shadow.get_height()//2 + 1))
        surf.blit(txt, (center[0] - txt.get_width()//2, center[1] - txt.get_height()//2))

    def clicked(self, mouse_pos):
        return self.rect.collidepoint(mouse_pos)

class IconButton:
    """Small centered icon glyph used for pause/close buttons."""
    def __init__(self, rect, kind, base_color=(30,30,34), draw_bg=True):
        self.rect = pg.Rect(rect)
        self.kind = kind
        self.base_color = base_color
        self.draw_bg = draw_bg
        self.hovering = False
        self.pulse = 0.0

    def update(self, mouse_pos, dt):
        self.hovering = self.rect.collidepoint(mouse_pos)
        if self.hovering:
            self.pulse = min(1.0, self.pulse + dt * 0.012)
        else:
            self.pulse = max(0.0, self.pulse - dt * 0.02)

    def draw(self, surf):
        cx, cy = self.rect.center
        r = max(6, min(self.rect.w, self.rect.h) // 2 - 2)

        if self.draw_bg:
            bg_col = (
                int(self.base_color[0] + (ACCENT[0] - self.base_color[0]) * (self.pulse * 0.5)),
                int(self.base_color[1] + (ACCENT[1] - self.base_color[1]) * (self.pulse * 0.5)),
                int(self.base_color[2] + (ACCENT[2] - self.base_color[2]) * (self.pulse * 0.5))
            ) if self.hovering else (30,30,34)
            pg.draw.circle(surf, (15,15,15), (cx, cy), r+2)
            pg.draw.circle(surf, bg_col, (cx, cy), r)

        if self.kind == 'pause':
            bw = max(2, r//3)
            ph = int(r * 1.0)
            x1 = cx - bw - 4; x2 = cx + 4
            pg.draw.rect(surf, (230,230,230), (x1 - bw//2, cy - ph//2, bw, ph), border_radius=2)
            pg.draw.rect(surf, (230,230,230), (x2 - bw//2, cy - ph//2, bw, ph), border_radius=2)
        elif self.kind == 'close':
            thickness = max(2, r//3)
            pg.draw.line(surf, (230,230,230), (cx - r//2, cy - r//2), (cx + r//2, cy + r//2), thickness)
            pg.draw.line(surf, (230,230,230), (cx - r//2, cy + r//2), (cx + r//2, cy - r//2), thickness)

    def clicked(self, mouse_pos):
        return self.rect.colliderect(pg.Rect(mouse_pos[0]-1, mouse_pos[1]-1, 2, 2))

# --- Main game function (entry point) ---
def run_game(username, user_id, selected_car, difficulty):
    pg.init()
    cfg = load_config()
    music_on = bool(cfg.get("music_on", True))
    music_volume = float(cfg.get("music_volume", 0.6))

    # Try to initialize mixer; if it fails we continue without audio.
    mixer_ok = False
    try:
        pg.mixer.init()
        mixer_ok = True
    except Exception:
        mixer_ok = False

    # Load and play music if available
    music_loaded = False
    if mixer_ok:
        for candidate in ("bgmusicgame.mp3", "bg_game.mp3", "bgmusic.mp3", "menu_music.mp3"):
            mpath = ASSETS / candidate
            if mpath.exists():
                try:
                    pg.mixer.music.load(str(mpath))
                    pg.mixer.music.set_volume(music_volume)
                    music_loaded = True
                    if music_on:
                        try:
                            pg.mixer.music.play(-1)
                        except Exception:
                            pass
                    break
                except Exception:
                    music_loaded = False

    screen = pg.display.set_mode((SCREEN_W, SCREEN_H))
    pg.display.set_caption('Car Dodger')
    clock = pg.time.Clock()

    # Load assets (use placeholders when missing)
    road = load_image("road.png", SCREEN_W, SCREEN_H//2)
    player_imgs = {
        'player1.png': load_image("player1.png", PLAYER_W, PLAYER_H),
        'player2.png': load_image("player2.png", PLAYER_W, PLAYER_H),
        'player3.png': load_image("player3.png", PLAYER_W, PLAYER_H),
        'player4.png': load_image("player4.png", PLAYER_W, PLAYER_H),
        'player5.png': load_image("player5.png", PLAYER_W, PLAYER_H)
    }
    enemy_img = load_image("enemy.png", ENEMY_W, ENEMY_H)

    # Select player image, fallback to player1 if unknown
    sel_name = Path(selected_car).name if selected_car else 'player1.png'
    player_img = player_imgs.get(sel_name) or player_imgs.get('player1.png')

    # Build masks when possible
    try:
        player_mask = pg.mask.from_surface(player_img)
    except Exception:
        player_mask = None
    try:
        enemy_mask = pg.mask.from_surface(enemy_img)
    except Exception:
        enemy_mask = None

    # Lane layout
    road_w = road.get_width()
    road_h = road.get_height()
    road_left = (SCREEN_W - road_w) // 2
    LANE_X = []
    for i in range(LANES):
        frac = (i * 2 + 1) / (LANES * 2)
        center_x = road_left + int(frac * road_w)
        LANE_X.append(center_x - PLAYER_W // 2)

    cfg_diff = DIFF.get(difficulty, DIFF['Casual'])
    spawn_ms_base = cfg_diff['spawn_ms']
    spawn_min = cfg_diff['min']
    spawn_max = cfg_diff['max']
    base_scroll = cfg_diff['scroll']
    MAX_ENEMIES = cfg_diff['max_enemies']

    font = pg.font.SysFont('Segoe UI', 18)
    big_font = pg.font.SysFont('Segoe UI', 40, bold=True)

    particles = []
    floating = []

    def spawn_particle():
        x = rnd.randint(10, SCREEN_W-10)
        y = -10
        vx = rnd.uniform(-0.2, 0.2)
        vy = rnd.uniform(0.6, 1.6)
        size = rnd.randint(1, 3)
        life = rnd.uniform(2.0, 4.0)
        particles.append([x, y, vx, vy, size, life])

    def spawn_popup(text, x, y):
        f = pg.font.SysFont('Segoe UI', 20, bold=True)
        floating.append({'txt': text, 'x': x, 'y': y, 'vy': -0.3, 'life': 900, 'alpha': 255, 'font': f})

    def update_particles_and_floating(dt, surf, scroll_effect=0.0):
        for p in particles[:]:
            p[1] += p[4] * (p[3] + scroll_effect)
            p[0] += p[2] * dt * 0.05
            p[5] -= dt * 0.001
            alpha = max(0, min(180, int(180 * (p[5] / 4.0))))
            color = rgba(ACCENT, alpha)
            pg.draw.circle(surf, color, (int(p[0]), int(p[1])), p[4])
            if p[1] > SCREEN_H + 20 or p[5] <= 0:
                try: particles.remove(p)
                except ValueError: pass

        for f in floating[:]:
            f['y'] += f['vy'] * (dt * 0.06)
            f['life'] -= dt
            if f['life'] < 0:
                try: floating.remove(f)
                except ValueError: pass
                continue
            surf_txt = f['font'].render(f['txt'], True, ACCENT)
            surf.blit(pg.transform.smoothscale(surf_txt, surf_txt.get_size()), (f['x'] - surf_txt.get_width()//2 + 1, int(f['y']) + 1))
            surf.blit(surf_txt, (f['x'] - surf_txt.get_width()//2, int(f['y'])))

    # Menu buttons
    menu_labels = ["Start Game", "Leaderboards", "Help", "Quit"]
    menu_buttons = []
    btn_w, btn_h = 260, 48
    cx = SCREEN_W // 2
    menu_font = pg.font.SysFont('Segoe UI', 22, bold=True)
    for i, lbl in enumerate(menu_labels):
        y = 260 + i * 64
        menu_buttons.append(Button((cx - btn_w//2, y, btn_w, btn_h), lbl, menu_font))

    icon_w = 36
    left_x = SCREEN_W // 2 - icon_w // 2
    icon_y = 10
    pause_btn = IconButton((left_x, icon_y, icon_w, icon_w), 'pause', draw_bg=False)

    def draw_menu(dt):
        mouse_pos = pg.mouse.get_pos()
        screen.fill(DARK_BG)
        title_s = big_font.render("CAR DODGER", True, (240,240,240))
        glow = big_font.render("CAR DODGER", True, ACCENT)
        for i in range(3):
            scale_w = int(glow.get_width() * (1.0 + 0.01 * (i+1)))
            scale_h = int(glow.get_height() * (1.0 + 0.01 * (i+1)))
            try:
                glow_s = pg.transform.smoothscale(glow, (scale_w, scale_h))
                screen.blit(glow_s, (SCREEN_W//2 - glow_s.get_width()//2 - 1, 108 - 1))
            except Exception:
                screen.blit(glow, (SCREEN_W//2 - glow.get_width()//2 - 1, 108 - 1))

        screen.blit(title_s, (SCREEN_W//2 - title_s.get_width()//2, 110))
        sub = font.render(f"Player: {username}", True, MUTED)
        screen.blit(sub, (SCREEN_W//2 - sub.get_width()//2, 165))

        if rnd.random() < 0.08:
            spawn_particle()
        update_particles_and_floating(dt, screen, scroll_effect=0.0)

        for b in menu_buttons:
            b.update(mouse_pos, dt)
            b.draw(screen)

        pg.draw.rect(screen, ACCENT, (0, SCREEN_H-6, SCREEN_W, 6))
        pg.display.flip()

    def wrap_text(text, font, max_width):
        words = text.split(' ')
        lines = []
        cur = ""
        for w in words:
            test = (cur + " " + w).strip()
            if font.size(test)[0] <= max_width:
                cur = test
            else:
                if cur: lines.append(cur)
                cur = w
        if cur: lines.append(cur)
        return lines

    def show_help_screen():
        # Simple overlay help screen
        running_help = True
        sections = [
            ("Controls:", ["- Left / A  : Move left", "- Right / D : Move right", "- P or Pause: Pause / Resume", "- L         : Leaderboards (in-game)", "- Esc       : Close overlays / Menu",]),
            ("Gameplay:", ["Avoid enemy cars. Collisions cause Game Over.", "Points: Close pass +250, Regular pass +150",]),
            ("Tips:", ["Stay centered to give yourself escape lanes.", "Use short quick lane changes rather than holding.",])
        ]

        title_f = pg.font.SysFont('Segoe UI', 32, bold=True)
        body_f = pg.font.SysFont('Segoe UI', 18)

        box_w = 440
        inner_w = box_w - 44

        wrapped = []
        for hdr, lines in sections:
            wrapped.append((True, hdr))
            for ln in lines:
                for sub_ln in wrap_text(ln, body_f, inner_w):
                    wrapped.append((False, sub_ln))
            wrapped.append((False, ""))

        line_h = body_f.get_linesize()
        title_h = title_f.get_linesize()
        padding = 22
        content_h = title_h + 10 + len(wrapped) * line_h
        box_h = min(520, content_h + padding * 2)
        bx = SCREEN_W // 2 - box_w // 2
        by = SCREEN_H // 2 - box_h // 2

        close_btn = IconButton((bx + box_w - 36 - 12, by + 12, 36, 36), 'close', draw_bg=False)
        hint_text = body_f.render("Press Esc or Close to dismiss", True, (200,200,200))

        while running_help:
            dt = clock.tick(FPS)
            mouse_pos = pg.mouse.get_pos()
            for ev in pg.event.get():
                if ev.type == pg.QUIT:
                    return 'quit'
                if ev.type == pg.KEYDOWN and ev.key in (pg.K_ESCAPE, pg.K_RETURN):
                    running_help = False
                if ev.type == pg.MOUSEBUTTONDOWN and ev.button == 1:
                    mx, my = ev.pos
                    if close_btn.clicked((mx, my)):
                        running_help = False
                    elif not (bx <= mx <= bx + box_w and by <= my <= by + box_h):
                        running_help = False

            overlay = pg.Surface((SCREEN_W, SCREEN_H), pg.SRCALPHA)
            overlay.fill((0,0,0,160))
            screen.blit(overlay, (0, 0))

            pg.draw.rect(screen, DARK_PANEL, (bx, by, box_w, box_h), border_radius=12)
            pg.draw.rect(screen, (30,30,30), (bx+8, by+8, box_w-16, box_h-16), border_radius=10)

            title_s = title_f.render("Help & Controls", True, ACCENT)
            screen.blit(title_s, (bx + 22, by + 18))

            hy = by + 18 + title_s.get_height() + 10
            for is_header, txt in wrapped:
                if is_header:
                    hdr_s = body_f.render(txt, True, (220,220,220))
                    screen.blit(hdr_s, (bx + 22, hy))
                    hy += line_h
                else:
                    ln_s = body_f.render(txt, True, (200,200,200))
                    screen.blit(ln_s, (bx + 28, hy))
                    hy += line_h

            close_btn.update(mouse_pos, dt)
            close_btn.draw(screen)

            screen.blit(hint_text, (SCREEN_W // 2 - hint_text.get_width() // 2, by + box_h + 14))
            pg.display.flip()

        return 'back'

    def show_leaderboard_screen():
        modes = [("All", None), ("Casual", "Casual"), ("Heroic", "Heroic"), ("Nightmare", "Nightmare")]
        selected = 0
        rows = db.top_scores(limit=15, mode=None, distinct=True)
        btn_w = 110; btn_h = 34; margin = 12
        start_x = (SCREEN_W - (btn_w * len(modes) + margin*(len(modes)-1))) // 2
        btn_rects = [pg.Rect(start_x + i*(btn_w+margin), 70, btn_w, btn_h) for i in range(len(modes))]
        back_btn = Button((SCREEN_W - 110, 16, 92, 32), "Back", font)

        running_lb = True
        while running_lb:
            dt = clock.tick(FPS)
            mouse_pos = pg.mouse.get_pos()
            for ev in pg.event.get():
                if ev.type == pg.QUIT:
                    return 'quit'
                if ev.type == pg.KEYDOWN:
                    if ev.key == pg.K_ESCAPE or ev.key == pg.K_RETURN:
                        running_lb = False
                if ev.type == pg.MOUSEBUTTONDOWN and ev.button == 1:
                    mx, my = ev.pos
                    for i, r in enumerate(btn_rects):
                        if r.collidepoint(mx, my):
                            if i != selected:
                                selected = i
                                mode_name = modes[selected][1]
                                rows = db.top_scores(limit=15, mode=mode_name, distinct=True)
                            break
                    if back_btn.clicked((mx, my)):
                        running_lb = False

            screen.fill((0,0,0))
            title = big_font.render("Leaderboards", True, (250,200,70))
            screen.blit(title, (SCREEN_W//2 - title.get_width()//2, 16))

            for i, r in enumerate(btn_rects):
                is_sel = (i == selected)
                col = DARK_PANEL if not is_sel else (12,50,56)
                pg.draw.rect(screen, col, r, border_radius=8)
                txt = font.render(modes[i][0], True, WHITE)
                screen.blit(txt, (r.centerx - txt.get_width()//2, r.centery - txt.get_height()//2))
                if is_sel:
                    pg.draw.rect(screen, ACCENT, (r.x-2, r.y-2, r.w+4, r.h+4), 2, border_radius=10)

            back_btn.update(mouse_pos, dt)
            back_btn.draw(screen)

            y = 130
            if not rows:
                txt = font.render("No scores yet. Play to create high scores!", True, (200,200,200))
                screen.blit(txt, (SCREEN_W//2 - txt.get_width()//2, y))
            else:
                header = font.render(f"{'Rank':<6}{'Player':<18}{'Score':>8}{'Mode':>10}{'Date':>12}", True, (200,200,200))
                screen.blit(header, (28, y)); y += 28
                rank = 1
                for r in rows:
                    uname, sc, mode, created = r
                    date_only = (created or '')[:10]
                    mode_text = mode if mode else '-'
                    uname_disp = uname if len(uname) <= 16 else uname[:13] + '...'
                    line_text = f"{rank:<6}{uname_disp:<18}{sc:>8}{mode_text:>10}{date_only:>12}"
                    line = font.render(line_text, True, (220,220,220))
                    screen.blit(line, (28, y)); y += 26; rank += 1

            hint = font.render("Esc/Enter to close | Click mode buttons to switch", True, (150,150,150))
            screen.blit(hint, (SCREEN_W//2 - hint.get_width()//2, SCREEN_H - 40))
            pg.display.flip()
        return 'back'

    # Gameplay state
    score = 0
    enemies = []
    last_spawn = pg.time.get_ticks()
    spawn_ms = spawn_ms_base
    offset = 0.0

    cur_lane = 1
    target_x = LANE_X[cur_lane]
    player_rect = pg.Rect(target_x, SCREEN_H - PLAYER_H - 20, PLAYER_W, PLAYER_H)
    lane_change_speed = 12.0
    paused = False

    def spawn():
        if len(enemies) >= MAX_ENEMIES:
            return
        min_gap = 140
        candidate_lanes = list(range(LANES))
        rnd.shuffle(candidate_lanes)
        for lane in candidate_lanes:
            conflict = any(e['lane'] == lane and e['rect'].y < min_gap for e in enemies)
            if not conflict:
                x = LANE_X[lane]
                y = -ENEMY_H - rnd.randint(0, 180)
                speed = rnd.uniform(spawn_min, spawn_max)
                rect = pg.Rect(x, y, ENEMY_W, ENEMY_H)
                enemies.append({'rect': rect, 'lane': lane, 'speed': speed, 'passed': False})
                return

    def draw_hud(dt):
        scr = font.render(f"Score: {score}", True, ACCENT)
        screen.blit(scr, (10,10))
        mode = font.render(f"Mode: {difficulty}", True, (200,200,200))
        screen.blit(mode, (SCREEN_W - mode.get_width() - 10, 10))
        mouse_pos = pg.mouse.get_pos()
        pause_btn.update(mouse_pos, dt)
        pause_btn.draw(screen)

    # --- Main menu loop ---
    in_menu = True
    while in_menu:
        dt = clock.tick(FPS)
        for ev in pg.event.get():
            if ev.type == pg.QUIT:
                if mixer_ok:
                    try: pg.mixer.music.stop(); pg.mixer.quit()
                    except Exception: pass
                pg.quit(); return
            if ev.type == pg.MOUSEBUTTONDOWN and ev.button == 1:
                mpos = pg.mouse.get_pos()
                for b in menu_buttons:
                    if b.clicked(mpos):
                        lbl = b.text
                        if lbl == "Start Game":
                            in_menu = False; break
                        elif lbl == "Leaderboards":
                            res = show_leaderboard_screen()
                            if res == 'quit':
                                if mixer_ok:
                                    try: pg.mixer.music.stop(); pg.mixer.quit()
                                    except Exception: pass
                                pg.quit(); return
                        elif lbl == "Help":
                            show_help_screen()
                        elif lbl == "Quit":
                            if mixer_ok:
                                try: pg.mixer.music.stop(); pg.mixer.quit()
                                except Exception: pass
                            pg.quit(); return
            if ev.type == pg.KEYDOWN:
                if ev.key in (pg.K_RETURN,):
                    in_menu = False

        draw_menu(dt)

    # --- Main gameplay loop ---
    running = True
    while running:
        dt = clock.tick(FPS)
        for ev in pg.event.get():
            if ev.type == pg.QUIT:
                running = False
            if ev.type == pg.KEYDOWN:
                if ev.key == pg.K_ESCAPE:
                    running = False
                if ev.key == pg.K_p:
                    paused = not paused
                if ev.key in (pg.K_LEFT, pg.K_a):
                    cur_lane = max(0, cur_lane-1)
                    target_x = LANE_X[cur_lane]
                if ev.key in (pg.K_RIGHT, pg.K_d):
                    cur_lane = min(LANES-1, cur_lane+1)
                    target_x = LANE_X[cur_lane]
                if ev.key == pg.K_l:
                    paused_before = paused
                    paused = True
                    res = show_leaderboard_screen()
                    paused = paused_before
            if ev.type == pg.MOUSEBUTTONDOWN and ev.button == 1:
                mx, my = ev.pos
                if pause_btn.clicked((mx, my)):
                    paused = not paused

        # --- Pause overlay ---
        if paused:
            slider_drag = False
            vol = cfg.get('music_volume', music_volume)
            music_enabled = cfg.get('music_on', True)

            bw = 200; bh = 48
            left_x = SCREEN_W//2 - bw - 12
            resume_b = Button((left_x, SCREEN_H//2 - 64, bw, bh), "Resume", font)
            lb_b     = Button((left_x, SCREEN_H//2 - 6,  bw, bh), "Leaderboards", font)
            help_b   = Button((left_x, SCREEN_H//2 + 52, bw, bh), "Help", font)
            quit_b   = Button((left_x, SCREEN_H//2 + 110,bw, bh), "Quit", font)

            panel_x = SCREEN_W//2 + 8
            panel_w = SCREEN_W - panel_x - 16
            panel_y = SCREEN_H//2 - 120
            s_x = panel_x + 18
            s_y = panel_y + 163
            s_w = panel_w - 36
            s_h = 12

            while paused:
                dt_p = clock.tick(FPS)
                mx, my = pg.mouse.get_pos()

                for ev2 in pg.event.get():
                    if ev2.type == pg.QUIT:
                        if mixer_ok:
                            try: pg.mixer.music.stop(); pg.mixer.quit()
                            except Exception: pass
                        pg.quit(); return
                    if ev2.type == pg.KEYDOWN:
                        if ev2.key in (pg.K_RETURN, pg.K_p):
                            paused = False; break
                        if ev2.key == pg.K_ESCAPE:
                            paused = False; running = False; break
                        if ev2.key == pg.K_LEFT:
                            vol = max(0.0, vol - 0.05)
                            cfg['music_volume'] = vol
                            cfg['music_on'] = vol > 0.001
                            if mixer_ok and music_loaded:
                                try: pg.mixer.music.set_volume(vol if cfg.get('music_on', True) else 0.0)
                                except Exception: pass
                            save_config(cfg)
                        if ev2.key == pg.K_RIGHT:
                            vol = min(1.0, vol + 0.05)
                            cfg['music_volume'] = vol
                            cfg['music_on'] = vol > 0.001
                            if mixer_ok and music_loaded:
                                try: pg.mixer.music.set_volume(vol if cfg.get('music_on', True) else 0.0)
                                except Exception: pass
                            save_config(cfg)

                    if ev2.type == pg.MOUSEBUTTONDOWN and ev2.button == 1:
                        if resume_b.clicked((mx, my)):
                            paused = False; break
                        if lb_b.clicked((mx, my)):
                            show_leaderboard_screen()
                        if help_b.clicked((mx, my)):
                            show_help_screen()
                        if quit_b.clicked((mx, my)):
                            paused = False; running = False; break

                        if s_x <= mx <= s_x + s_w and s_y - 8 <= my <= s_y + s_h + 8:
                            slider_drag = True
                            rel = (mx - s_x) / s_w
                            vol = max(0.0, min(1.0, rel))
                            cfg['music_volume'] = vol
                            cfg['music_on'] = vol > 0.001
                            if mixer_ok and music_loaded:
                                try: pg.mixer.music.set_volume(vol if cfg.get('music_on', True) else 0.0)
                                except Exception: pass
                            save_config(cfg)

                        toggle_rect = pg.Rect(panel_x + 18, panel_y + 105, 120, 28)
                        if toggle_rect.collidepoint(mx, my):
                            music_enabled = not music_enabled
                            cfg['music_on'] = music_enabled
                            if mixer_ok and music_loaded:
                                try:
                                    if music_enabled:
                                        pg.mixer.music.set_volume(cfg.get('music_volume', 0.6))
                                        if not pg.mixer.music.get_busy():
                                            pg.mixer.music.play(-1)
                                    else:
                                        pg.mixer.music.set_volume(0.0)
                                except Exception:
                                    pass
                            save_config(cfg)

                    if ev2.type == pg.MOUSEBUTTONUP and ev2.button == 1:
                        slider_drag = False

                    if ev2.type == pg.MOUSEMOTION and slider_drag:
                        rel = (mx - s_x) / s_w
                        vol = max(0.0, min(1.0, rel))
                        cfg['music_volume'] = vol
                        cfg['music_on'] = vol > 0.001
                        if mixer_ok and music_loaded:
                            try: pg.mixer.music.set_volume(vol if cfg.get('music_on', True) else 0.0)
                            except Exception: pass
                        save_config(cfg)

                # Draw overlay and UI
                overlay = pg.Surface((SCREEN_W, SCREEN_H), pg.SRCALPHA)
                overlay.fill((0,0,0,200))
                screen.blit(overlay, (0,0))

                mouse_pos = (mx, my)
                for b in (resume_b, lb_b, help_b, quit_b):
                    b.update(mouse_pos, dt_p)
                    b.draw(screen)

                pg.draw.rect(screen, DARK_PANEL, (panel_x, panel_y + 56, panel_w, 165), border_radius=12)
                pg.draw.rect(screen, (30,30,30), (panel_x+8, panel_y+64, panel_w-16, 149), border_radius=10)
                title = font.render("Settings", True, ACCENT)
                screen.blit(title, (panel_x + 18, panel_y + 68))

                toggle_rect = pg.Rect(panel_x + 18, panel_y + 105, 120, 28)
                pg.draw.rect(screen, (40,40,40), toggle_rect, border_radius=8)
                ttxt = font.render("Music ON" if cfg.get('music_on', True) else "Music OFF", True, (230,230,230))
                screen.blit(ttxt, (toggle_rect.x + 20, toggle_rect.y + 1))

                vlbl = font.render("Volume", True, (200,200,200))
                screen.blit(vlbl, (panel_x + 18, panel_y + 135))
                pg.draw.rect(screen, (60,60,60), (s_x, s_y, s_w, s_h), border_radius=6)
                fill_w = int(s_w * vol)
                pg.draw.rect(screen, ACCENT, (s_x, s_y, fill_w, s_h), border_radius=6)
                knob_x = s_x + fill_w
                pg.draw.circle(screen, (220,220,220), (knob_x, s_y + s_h//2), 8)
                vol_pct = int(vol * 100)
                vol_txt = font.render(f"{vol_pct}%", True, (200,200,200))
                screen.blit(vol_txt, (panel_x + 18, panel_y + 180))

                hint = font.render("Enter = Resume | Esc = Quit to menu | ←/→ adjust vol", True, (160,160,160))
                screen.blit(hint, (SCREEN_W//2 - hint.get_width()//2, panel_y + 320))
                pause_title = big_font.render("PAUSED", True, (230,230,230))
                screen.blit(pause_title, (SCREEN_W//2 - pause_title.get_width()//2, SCREEN_H//2 - 180))

                pause_btn.update(mouse_pos, dt_p)
                pause_btn.draw(screen)

                pg.display.flip()

            # Persist final config after unpausing
            cfg['music_volume'] = vol
            cfg['music_on'] = cfg.get('music_on', True) and (cfg.get('music_volume', vol) > 0.001)
            save_config(cfg)

        # spawn timing
        now = pg.time.get_ticks()
        if now - last_spawn > spawn_ms:
            spawn()
            last_spawn = now
            spawn_ms = max(200, spawn_ms_base + rnd.randint(-200, 200))

        rem = []
        for e in enemies:
            e['rect'].y += e['speed'] + (base_scroll * 0.15)
            collided = False
            if player_mask is not None and enemy_mask is not None:
                off = (int(e['rect'].x - player_rect.x), int(e['rect'].y - player_rect.y))
                if player_mask.overlap(enemy_mask, off) is not None:
                    collided = True
            else:
                SHRINK_FRACTION = 0.35
                pw = max(1, int(player_rect.w * (1.0 - SHRINK_FRACTION)))
                ph = max(1, int(player_rect.h * (1.0 - SHRINK_FRACTION)))
                ew = max(1, int(e['rect'].w * (1.0 - SHRINK_FRACTION)))
                eh = max(1, int(e['rect'].h * (1.0 - SHRINK_FRACTION)))
                p_hit = pg.Rect(player_rect.centerx - pw//2, player_rect.centery - ph//2, pw, ph)
                e_hit = pg.Rect(e['rect'].centerx - ew//2, e['rect'].centery - eh//2, ew, eh)
                if p_hit.colliderect(e_hit):
                    collided = True

            if collided:
                running = False
                break

            if not e['passed'] and e['rect'].y > player_rect.y + player_rect.height:
                e['passed'] = True
                ec = e['rect'].x + ENEMY_W/2
                pc = player_rect.x + PLAYER_W/2
                dist = abs(ec - pc)
                if dist <= CLOSE_THRESH:
                    score += 250
                    spawn_popup("+250", pc, player_rect.y - 20)
                else:
                    score += 150
                    spawn_popup("+150", pc, player_rect.y - 20)

            if e['rect'].y > SCREEN_H + 200:
                rem.append(e)

        for r in rem:
            try: enemies.remove(r)
            except ValueError: pass

        # smooth lane interpolation
        if abs(player_rect.x - target_x) > 1:
            step = lane_change_speed * (dt * 0.06)
            if player_rect.x < target_x:
                player_rect.x = min(target_x, player_rect.x + step)
            else:
                player_rect.x = max(target_x, player_rect.x - step)

        # background scroll
        scroll = base_scroll * (dt / 16.67)
        offset = (offset + scroll) % max(1, road_h)

        screen.fill(DARK_BG)

        rx = (SCREEN_W - road.get_width()) // 2
        ry = offset - road_h
        while ry < SCREEN_H:
            screen.blit(road, (rx, ry))
            ry += road_h

        update_particles_and_floating(dt, screen, scroll_effect=(base_scroll * 0.02))

        for e in enemies:
            screen.blit(enemy_img, (e['rect'].x, e['rect'].y))
        shadow = pg.Surface((player_rect.w, 10), pg.SRCALPHA)
        shadow.fill((0,0,0,80))
        screen.blit(shadow, (player_rect.x, player_rect.y + player_rect.h - 8))
        screen.blit(player_img, (player_rect.x, player_rect.y))

        draw_hud(dt)

        pg.display.flip()

    # --- Game over ---
    def show_game_over_screen():
        bw = 180; bh = 48
        b_restart = Button((SCREEN_W//2 - bw//2, SCREEN_H//2 + 20, bw, bh), "Restart", font)
        b_view = Button((SCREEN_W//2 - bw - 10, SCREEN_H//2 + 80, bw, bh), "Leaderboard", font)
        b_menu = Button((SCREEN_W//2 + 10, SCREEN_H//2 + 80, bw, bh), "Menu", font)

        while True:
            dt = clock.tick(FPS)
            mouse_pos = pg.mouse.get_pos()
            for ev in pg.event.get():
                if ev.type == pg.QUIT: return "quit"
                if ev.type == pg.KEYDOWN:
                    if ev.key == pg.K_ESCAPE: return "menu"
                    if ev.key == pg.K_RETURN: return "restart"
                if ev.type == pg.MOUSEBUTTONDOWN and ev.button == 1:
                    mpos = pg.mouse.get_pos()
                    if b_restart.clicked(mpos): return "restart"
                    if b_view.clicked(mpos): return "leaderboard"
                    if b_menu.clicked(mpos): return "menu"

            screen.fill((6,6,6))
            go = big_font.render("GAME OVER", True, (255,80,80))
            sc_txt = font.render(f"Score: {score}", True, (230,230,230))
            screen.blit(go, (SCREEN_W//2 - go.get_width()//2, SCREEN_H//2 - 80))
            screen.blit(sc_txt, (SCREEN_W//2 - sc_txt.get_width()//2, SCREEN_H//2 - 20))

            for b in (b_restart, b_view, b_menu):
                b.update(pg.mouse.get_pos(), dt)
                b.draw(screen)

            pg.display.flip()

    # Save score if user logged in
    if user_id:
        try:
            save_score(user_id, score, difficulty)
        except Exception:
            pass

    res = show_game_over_screen()

    if res == "leaderboard":
        show_leaderboard_screen()
    elif res == "restart":
        if mixer_ok:
            try: pg.mixer.music.stop(); pg.mixer.quit()
            except Exception: pass
        pg.quit()
        time.sleep(0.08)
        return run_game(username, user_id, selected_car, difficulty)

    if mixer_ok:
        try: pg.mixer.music.stop(); pg.mixer.quit()
        except Exception: pass

    pg.quit()
    return
