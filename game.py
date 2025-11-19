# game.py
"""
Pygame: black + neon themed UI, improved in-game leaderboard with date-only.
Subtle animated particles in menus for a livelier feel.
"""

import pygame as pg
from pathlib import Path
import sys, random as rnd, time
import db
from db import save_score

BASE_DIR = Path(__file__).resolve().parent
ASSETS = BASE_DIR / "assets"

FPS = 60
SCREEN_W, SCREEN_H = 480, 720
LANES = 3
PLAYER_W, PLAYER_H = 80, 140
ENEMY_W, ENEMY_H = 80, 140
CLOSE_THRESH = 80

DIFF = {
    'Casual':    {'min': 3.0,  'max': 5.0,  'spawn_ms': 1200, 'scroll': 3, 'max_enemies': 5},
    'Heroic':    {'min': 5.0,  'max': 8.0,  'spawn_ms': 900,  'scroll': 5, 'max_enemies': 7},
    'Nightmare': {'min': 8.0,  'max': 12.0, 'spawn_ms': 550, 'scroll': 8, 'max_enemies': 10}
}

ACCENT = (0, 192, 214)
DARK_BG = (8, 8, 10)
DARK_PANEL = (16, 16, 18)

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

class Button:
    def __init__(self, rect, text, font, base_color=(30,30,34), hover_color=None):
        self.rect = pg.Rect(rect)
        self.text = text; self.font = font
        self.base_color = base_color
        self.hover_color = hover_color or (min(255, base_color[0]+40), min(255, base_color[1]+40), min(255, base_color[2]+60))
        self.hovering = False; self.pulse = 0.0

    def update(self, mouse_pos, dt):
        self.hovering = self.rect.collidepoint(mouse_pos)
        if self.hovering: self.pulse = min(1.0, self.pulse + dt*0.01)
        else: self.pulse = max(0.0, self.pulse - dt*0.02)

    def draw(self, surf):
        pulse_scale = 1.0 + 0.05 * (self.pulse**2)
        w, h = int(self.rect.w * pulse_scale), int(self.rect.h * pulse_scale)
        center = self.rect.center
        draw_rect = pg.Rect(0,0,w,h); draw_rect.center = center
        color = [int(self.base_color[i] + (self.hover_color[i]-self.base_color[i]) * self.pulse) for i in range(3)]
        pg.draw.rect(surf, color, draw_rect, border_radius=12)
        # neon outline when hovered
        if self.pulse > 0.01:
            outline = pg.Surface((draw_rect.w+8, draw_rect.h+8), pg.SRCALPHA)
            glow_col = (*ACCENT, int(80 * self.pulse))
            pg.draw.rect(outline, glow_col, outline.get_rect(), border_radius=14)
            surf.blit(outline, (draw_rect.x-4, draw_rect.y-4), special_flags=pg.BLEND_RGBA_ADD)
        txt_s = self.font.render(self.text, True, (230,230,230))
        surf.blit(txt_s, (center[0] - txt_s.get_width()//2, center[1] - txt_s.get_height()//2))

    def clicked(self, mouse_pos): return self.rect.collidepoint(mouse_pos)

def run_game(username, user_id, selected_car, difficulty):
    pg.init()
    screen = pg.display.set_mode((SCREEN_W, SCREEN_H))
    pg.display.set_caption('Car Dodger')
    clock = pg.time.Clock()

    road = load_image("road.png", SCREEN_W, SCREEN_H//2)
    grass = load_image("grass.png", 80, SCREEN_H//3)
    player1 = load_image("player1.png", PLAYER_W, PLAYER_H)
    player2 = load_image("player2.png", PLAYER_W, PLAYER_H)
    enemy_img = load_image("enemy.png", ENEMY_W, ENEMY_H)
    player_img = player1 if Path(selected_car).name == "player1.png" else player2

    road_w = road.get_width(); road_left = (SCREEN_W - road_w) // 2; lane_w = road_w // 4
    LANE_X = [road_left + 1*lane_w - PLAYER_W//2, road_left + 2*lane_w - PLAYER_W//2, road_left + 3*lane_w - PLAYER_W//2]

    cfg = DIFF.get(difficulty, DIFF['Casual'])
    spawn_ms_base = cfg['spawn_ms']; spawn_min = cfg['min']; spawn_max = cfg['max']; scroll = cfg['scroll']; MAX_ENEMIES = cfg['max_enemies']

    font = pg.font.SysFont('Segoe UI', 18)
    big_font = pg.font.SysFont('Segoe UI', 40, bold=True)

    # particles for menu (subtle)
    particles = []
    def spawn_particle():
        x = rnd.randint(10, SCREEN_W-10); y = -10
        vx = rnd.uniform(-0.2, 0.2); vy = rnd.uniform(0.6, 1.6)
        size = rnd.randint(1,3)
        life = rnd.uniform(2.0, 4.0)
        particles.append([x,y,vx,vy,size,life])

    def update_particles(dt, surf):
        for p in particles[:]:
            p[1] += p[4]*p[3]  # basic movement (adjusted)
            p[0] += p[2]*dt*0.5
            p[5] -= dt*0.001
            a = max(0, min(180, int(180 * (p[5]/4.0))))
            pg.draw.circle(surf, (*ACCENT, a), (int(p[0]), int(p[1])), p[4])
            if p[1] > SCREEN_H + 20 or p[5] <= 0:
                particles.remove(p)

    menu_buttons = []
    btn_w, btn_h = 260, 52
    cx = SCREEN_W // 2
    menu_font = pg.font.SysFont('Segoe UI', 22, bold=True)
    menu_buttons.append(Button((cx - btn_w//2, 260, btn_w, btn_h), "Start Game", menu_font))
    menu_buttons.append(Button((cx - btn_w//2, 330, btn_w, btn_h), "Leaderboards", menu_font))
    menu_buttons.append(Button((cx - btn_w//2, 400, btn_w, btn_h), "Quit", menu_font))

    def draw_menu(dt):
        mouse_pos = pg.mouse.get_pos()
        screen.fill(DARK_BG)
        # soft vignette
        vign = pg.Surface((SCREEN_W, SCREEN_H), pg.SRCALPHA)
        pg.draw.rect(vign, (0,0,0,120), vign.get_rect())
        # title with neon shadow
        title_s = big_font.render("CAR DODGER", True, (240,240,240))
        # glow
        glow = big_font.render("CAR DODGER", True, ACCENT)
        for i in range(6):
            screen.blit(pg.transform.smoothscale(glow, (int(glow.get_width()*1.02), int(glow.get_height()*1.02))), (SCREEN_W//2 - glow.get_width()//2 - 1, 108 - 1))
        screen.blit(title_s, (SCREEN_W//2 - title_s.get_width()//2, 110))
        sub = font.render(f"Player: {username}    Mode: {difficulty}", True, (180,180,180))
        screen.blit(sub, (SCREEN_W//2 - sub.get_width()//2, 165))

        # animated road preview
        screen.blit(road, ((SCREEN_W - road.get_width())//2, 200))

        # spawn some particles occasionally
        if rnd.random() < 0.08:
            spawn_particle()
        update_particles(dt, screen)

        for b in menu_buttons:
            b.update(mouse_pos, dt)
            b.draw(screen)

        # bottom accent bar
        pg.draw.rect(screen, ACCENT, (0, SCREEN_H-6, SCREEN_W, 6))
        pg.display.flip()

    def show_leaderboard_screen():
        modes = [("All", None), ("Casual", "Casual"), ("Heroic", "Heroic"), ("Nightmare", "Nightmare")]
        selected = 0
        rows = db.top_scores(limit=15, mode=None, distinct=True)
        btn_w = 110; btn_h = 34; margin = 12
        start_x = (SCREEN_W - (btn_w * len(modes) + margin*(len(modes)-1))) // 2
        btn_rects = [pg.Rect(start_x + i*(btn_w+margin), 70, btn_w, btn_h) for i in range(len(modes))]
        back_rect = pg.Rect(SCREEN_W - 110, 16, 92, 32)

        running_lb = True
        while running_lb:
            dt = clock.tick(FPS)
            for ev in pg.event.get():
                if ev.type == pg.QUIT: return 'quit'
                if ev.type == pg.KEYDOWN:
                    if ev.key == pg.K_ESCAPE: running_lb = False
                if ev.type == pg.MOUSEBUTTONDOWN and ev.button == 1:
                    mx, my = ev.pos
                    for i, r in enumerate(btn_rects):
                        if r.collidepoint(mx, my):
                            if i != selected:
                                selected = i
                                mode_name = modes[selected][1]
                                rows = db.top_scores(limit=15, mode=mode_name, distinct=True)
                            break
                    if back_rect.collidepoint(mx, my): running_lb = False

            # draw
            screen.fill((0,0,0))
            # title
            title = big_font.render("Leaderboards", True, (250,200,70))
            screen.blit(title, (SCREEN_W//2 - title.get_width()//2, 16))

            # mode buttons (neon when active)
            for i, r in enumerate(btn_rects):
                is_sel = (i == selected)
                col = DARK_PANEL if not is_sel else (12,50,56)
                pg.draw.rect(screen, col, r, border_radius=8)
                txt = font.render(modes[i][0], True, (255,255,255))
                screen.blit(txt, (r.centerx - txt.get_width()//2, r.centery - txt.get_height()//2))
                if is_sel:
                    pg.draw.rect(screen, ACCENT, (r.x-2, r.y-2, r.w+4, r.h+4), 2, border_radius=10)

            # back
            pg.draw.rect(screen, (40,40,40), back_rect, border_radius=6)
            btxt = font.render("Back", True, (255,255,255)); screen.blit(btxt, (back_rect.centerx - btxt.get_width()//2, back_rect.centery - btxt.get_height()//2))

            # rows
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
                    line = font.render(f"{rank:<6}{uname:<18}{sc:>8}{(mode or '-'):>10}{date_only:>12}", True, (220,220,220))
                    screen.blit(line, (28, y)); y += 26; rank += 1

            hint = font.render("Esc to close | Click mode buttons to switch", True, (150,150,150))
            screen.blit(hint, (SCREEN_W//2 - hint.get_width()//2, SCREEN_H - 40))
            pg.display.flip()
        return 'back'

    # --- gameplay variables ---
    score = 0; enemies = []; last_spawn = pg.time.get_ticks(); spawn_ms = spawn_ms_base; offset = 0; road_h = road.get_height()
    cur_lane = 1; target_x = LANE_X[cur_lane]; player_rect = pg.Rect(target_x, SCREEN_H - PLAYER_H - 20, PLAYER_W, PLAYER_H)
    lane_change_speed = 10.0; paused = False

    def spawn():
        if len(enemies) >= MAX_ENEMIES: return
        min_gap = 140
        candidate_lanes = list(range(LANES)); rnd.shuffle(candidate_lanes)
        for lane in candidate_lanes:
            conflict = any(e['lane'] == lane and e['rect'].y < min_gap for e in enemies)
            if not conflict:
                x = LANE_X[lane]; y = -ENEMY_H - rnd.randint(0, 180); speed = rnd.uniform(spawn_min, spawn_max)
                rect = pg.Rect(x, y, ENEMY_W, ENEMY_H); enemies.append({'rect': rect, 'lane': lane, 'speed': speed, 'passed': False}); return

    def draw_hud():
        scr = font.render(f"Score: {score}", True, ACCENT); mode = font.render(f"Mode: {difficulty}", True, (200,200,200))
        screen.blit(scr, (10,10)); screen.blit(mode, (SCREEN_W - mode.get_width() - 10, 10))

    # --- main menu loop ---
    in_menu = True
    while in_menu:
        dt = clock.tick(FPS)
        for ev in pg.event.get():
            if ev.type == pg.QUIT: pg.quit(); return
            if ev.type == pg.MOUSEBUTTONDOWN and ev.button == 1:
                mpos = pg.mouse.get_pos()
                if menu_buttons[0].clicked(mpos): in_menu = False
                elif menu_buttons[1].clicked(mpos):
                    res = show_leaderboard_screen()
                    if res == 'quit': pg.quit(); return
                elif menu_buttons[2].clicked(mpos): pg.quit(); return
        draw_menu(dt)

    # --- gameplay loop ---
    running = True
    while running:
        dt = clock.tick(FPS)
        for ev in pg.event.get():
            if ev.type == pg.QUIT: running = False
            if ev.type == pg.KEYDOWN:
                if ev.key == pg.K_ESCAPE: running = False
                if ev.key == pg.K_p: paused = not paused
                if ev.key in (pg.K_LEFT, pg.K_a): cur_lane = max(0, cur_lane-1); target_x = LANE_X[cur_lane]
                if ev.key in (pg.K_RIGHT, pg.K_d): cur_lane = min(LANES-1, cur_lane+1); target_x = LANE_X[cur_lane]
                if ev.key == pg.K_l:
                    paused_before = paused; paused = True
                    res = show_leaderboard_screen(); paused = paused_before

        if paused:
            screen.fill((6,6,6))
            pause_txt = big_font.render("PAUSED", True, (230,230,230)); hint = font.render("Press P to resume. Press Esc to quit.", True, (200,200,200))
            screen.blit(pause_txt, (SCREEN_W//2 - pause_txt.get_width()//2, SCREEN_H//2 - 40)); screen.blit(hint, (SCREEN_W//2 - hint.get_width()//2, SCREEN_H//2 + 10))
            pg.display.flip(); continue

        now = pg.time.get_ticks()
        if now - last_spawn > spawn_ms:
            spawn(); last_spawn = now; spawn_ms = max(200, spawn_ms_base + rnd.randint(-200, 200))

        rem = []
        for e in enemies:
            e['rect'].y += e['speed']
            if e['rect'].colliderect(player_rect): running = False
            if not e['passed'] and e['rect'].y > player_rect.y + player_rect.height:
                e['passed'] = True; ec = e['rect'].x + ENEMY_W/2; pc = player_rect.x + PLAYER_W/2; dist = abs(ec - pc)
                score += 250 if dist <= CLOSE_THRESH else 150
            if e['rect'].y > SCREEN_H + 200: rem.append(e)
        for r in rem: enemies.remove(r)

        if abs(player_rect.x - target_x) > 1:
            if player_rect.x < target_x: player_rect.x = min(target_x, player_rect.x + lane_change_speed)
            else: player_rect.x = max(target_x, player_rect.x - lane_change_speed)

        offset = (offset + scroll) % max(1, road_h)
        screen.fill(DARK_BG)
        gx = -offset
        while gx < SCREEN_H:
            screen.blit(grass, (0, gx)); screen.blit(grass, (SCREEN_W - grass.get_width(), gx)); gx += grass.get_height()
        rx = (SCREEN_W - road.get_width())//2; ry = -offset
        while ry < SCREEN_H:
            screen.blit(road, (rx, ry)); ry += road_h

        for i in range(1, 4):
            x = rx + i*(road.get_width()//4)
            for y in range(0, SCREEN_H, 40): pg.draw.line(screen, (180,180,180), (x, y+10), (x, y+20), 3)

        for e in enemies: screen.blit(enemy_img, (e['rect'].x, e['rect'].y))
        screen.blit(player_img, (player_rect.x, player_rect.y))
        draw_hud()
        pg.display.flip()

    # Game over UI
    def show_game_over_screen():
        show = True
        gb_w, gb_h = 180, 48
        b_view = Button((SCREEN_W//2 - gb_w - 10, SCREEN_H//2 + 40, gb_w, gb_h), "View Leaderboard", font)
        b_menu = Button((SCREEN_W//2 + 10, SCREEN_H//2 + 40, gb_w, gb_h), "Back to Menu", font)
        while show:
            dt = clock.tick(FPS)
            for ev in pg.event.get():
                if ev.type == pg.QUIT: return 'quit'
                if ev.type == pg.KEYDOWN:
                    if ev.key == pg.K_ESCAPE: return 'menu'
                if ev.type == pg.MOUSEBUTTONDOWN and ev.button == 1:
                    if b_view.clicked(pg.mouse.get_pos()): return 'leaderboard'
                    if b_menu.clicked(pg.mouse.get_pos()): return 'menu'
            screen.fill((6,6,6))
            go = big_font.render("GAME OVER", True, (255,80,80)); sc_txt = font.render(f"Score: {score}", True, (230,230,230))
            screen.blit(go, (SCREEN_W//2 - go.get_width()//2, SCREEN_H//2 - 60)); screen.blit(sc_txt, (SCREEN_W//2 - sc_txt.get_width()//2, SCREEN_H//2))
            b_view.update(pg.mouse.get_pos(), dt); b_menu.update(pg.mouse.get_pos(), dt)
            b_view.draw(screen); b_menu.draw(screen)
            pg.display.flip()
        return 'menu'

    if user_id:
        try: save_score(user_id, score, difficulty)
        except Exception: pass

    res = show_game_over_screen()
    if res == 'leaderboard': show_leaderboard_screen()

    pg.quit(); return
