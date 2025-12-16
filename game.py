# FIXED + CLEANED VERSION
# Major fixes:
# - indentation errors
# - spawn() scope / nonlocal bugs
# - smooth lane movement
# - fair enemy spawning
# - difficulty ramp
# - screen shake
# - black screen issues

import pygame as pg
from pathlib import Path
import random as rnd
import time
import json
import db
from db import save_score

# ================= PATHS & CONSTANTS =================
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
    'Nightmare': {'min': 8.0,  'max': 12.0, 'spawn_ms': 550,  'scroll': 8, 'max_enemies': 10}
}

ACCENT = (0, 192, 214)
DARK_BG = (8, 8, 10)
WHITE = (255, 255, 255)

# ================= HELPERS =================
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

# ================= GAME =================
def run_game(username, user_id, selected_car, difficulty):
    pg.init()
    screen = pg.display.set_mode((SCREEN_W, SCREEN_H))
    pg.display.set_caption("Car Dodger")
    clock = pg.time.Clock()

    road = load_image("road.png", SCREEN_W, SCREEN_H // 2)
    enemy_img = load_image("enemy.png", ENEMY_W, ENEMY_H)
    player_img = load_image(selected_car or "player1.png", PLAYER_W, PLAYER_H)

    road_h = road.get_height()
    road_left = (SCREEN_W - road.get_width()) // 2
    LANE_X = [road_left + int((i * 2 + 1) / (LANES * 2) * road.get_width()) - PLAYER_W // 2 for i in range(LANES)]

    cfg = DIFF.get(difficulty, DIFF['Casual'])
    spawn_min, spawn_max = cfg['min'], cfg['max']
    spawn_ms = cfg['spawn_ms']
    base_scroll = cfg['scroll']
    MAX_ENEMIES = cfg['max_enemies']

    font = pg.font.SysFont("Segoe UI", 18)
    big_font = pg.font.SysFont("Segoe UI", 40, bold=True)

    # ================= STATE =================
    enemies = []
    last_spawned_lanes = []
    lane_cooldown = [0] * LANES
    last_spawn = pg.time.get_ticks()

    score = 0
    offset = 0.0

    cur_lane = 1
    target_x = LANE_X[cur_lane]
    player_rect = pg.Rect(target_x, SCREEN_H - PLAYER_H - 20, PLAYER_W, PLAYER_H)

    lane_speed = 0.0

    shake_timer = 0
    shake_strength = 0

    # ================= SPAWN =================
    def spawn_enemy():
        nonlocal last_spawned_lanes
        if len(enemies) >= MAX_ENEMIES:
            return

        available = []
        for lane in range(LANES):
            if lane_cooldown[lane] > 0:
                continue
            if not any(e['lane'] == lane and e['rect'].y < 160 for e in enemies):
                available.append(lane)

        if not available:
            return

        if last_spawned_lanes and len(available) > 1:
            avoid = last_spawned_lanes[-1]
            if avoid in available:
                available.remove(avoid)

        lane = rnd.choice(available)
        last_spawned_lanes = (last_spawned_lanes + [lane])[-3:]
        lane_cooldown[lane] = 30

        rect = pg.Rect(LANE_X[lane], -ENEMY_H - rnd.randint(40, 200), ENEMY_W, ENEMY_H)
        speed = rnd.uniform(spawn_min, spawn_max)
        enemies.append({'rect': rect, 'lane': lane, 'speed': speed, 'passed': False})

    # ================= LOOP =================
    running = True
    while running:
        dt = clock.tick(FPS)
        now = pg.time.get_ticks()

        for ev in pg.event.get():
            if ev.type == pg.QUIT:
                running = False
            if ev.type == pg.KEYDOWN:
                if ev.key in (pg.K_LEFT, pg.K_a):
                    cur_lane = max(0, cur_lane - 1)
                    target_x = LANE_X[cur_lane]
                if ev.key in (pg.K_RIGHT, pg.K_d):
                    cur_lane = min(LANES - 1, cur_lane + 1)
                    target_x = LANE_X[cur_lane]

        lane_cooldown = [max(0, c - 1) for c in lane_cooldown]

        # Difficulty ramp
        difficulty_scale = 1.0 + min(score / 3000, 2.5)
        spawn_ms = max(350, int(cfg['spawn_ms'] / difficulty_scale))
        spawn_min = cfg['min'] * difficulty_scale
        spawn_max = cfg['max'] * difficulty_scale

        if now - last_spawn > spawn_ms:
            spawn_enemy()
            last_spawn = now

        # Move enemies
        for e in enemies[:]:
            e['rect'].y += e['speed'] + base_scroll * 0.15
            if e['rect'].colliderect(player_rect):
                running = False
            if not e['passed'] and e['rect'].y > player_rect.bottom:
                e['passed'] = True
                score += 150
            if e['rect'].y > SCREEN_H + 200:
                enemies.remove(e)

        # Smooth lane movement
        dx = target_x - player_rect.x
        lane_speed += dx * 0.18
        lane_speed *= 0.78
        player_rect.x += lane_speed

        # Screen shake
        shake_x = shake_y = 0
        if shake_timer > 0:
            shake_x = rnd.randint(-shake_strength, shake_strength)
            shake_y = rnd.randint(-shake_strength, shake_strength)
            shake_timer -= 1

        # Draw
        screen.fill(DARK_BG)
        offset = (offset + base_scroll) % road_h
        ry = offset - road_h
        while ry < SCREEN_H:
            screen.blit(road, (road_left + shake_x, ry + shake_y))
            ry += road_h

        for e in enemies:
            screen.blit(enemy_img, e['rect'])

        screen.blit(player_img, player_rect)
        screen.blit(font.render(f"Score: {score}", True, ACCENT), (10, 10))
        pg.display.flip()

    # Save score
    if user_id:
        save_score(user_id, score, difficulty)

    pg.quit()
    return
