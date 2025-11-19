# game.py
import pygame as pg
import os, sys
import random as rnd
from db import save_score
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
sys.path.insert(0, BASE_DIR)

ASSETS = os.path.join(BASE_DIR, "assets")
print("WORKING DIRECTORY:", os.getcwd())
print("ASSETS PATH:", ASSETS)
print("ASSETS FOLDER EXISTS:", os.path.isdir(ASSETS))
print("FILES IN ASSETS:", os.listdir(ASSETS))
print("player1:", os.path.exists(os.path.join(ASSETS, "player1.png")))
print("player2:", os.path.exists(os.path.join(ASSETS, "player2.png")))
print("enemy:",   os.path.exists(os.path.join(ASSETS, "enemy.png")))
input("DEBUG: Press ENTER…")


ASSETS = 'assets'
FPS = 60

# Config
SCREEN_W, SCREEN_H = 480, 720
LANES = 3
LANE_X = [SCREEN_W//6 - 40, SCREEN_W//2 - 40, 5*SCREEN_W//6 - 120]
PLAYER_W, PLAYER_H = 80, 140
ENEMY_W, ENEMY_H = 80, 140
CLOSE_THRESH = 80

DIFF = {
    'Casual':    {'min': 4.0,  'max': 6.0,  'spawn_ms': 1200, 'scroll': 3},
    'Heroic':    {'min': 6.0,  'max': 9.0,  'spawn_ms': 900,  'scroll': 5},
    'Nightmare': {'min': 9.0,  'max': 13.0, 'spawn_ms': 550,  'scroll': 8}
}

def load_image(name, w=None, h=None):
    path = os.path.join(ASSETS, name)
    print("Loading:", path)  # debug

    if not os.path.exists(path):
        print("❌ Not found:", path)
        surf = pg.Surface((w or 80, h or 80), pg.SRCALPHA)
        surf.fill((200, 0, 0, 255))
        return surf

    img = pg.image.load(path).convert_alpha()

    if w and h:
        img = pg.transform.smoothscale(img, (w, h))

    return img


    # fallback
    surf = pg.Surface((w or 100, h or 100), pg.SRCALPHA)
    surf.fill((150,150,150,255))
    return surf


def run_game(username, user_id, selected_car, difficulty):
    pg.init()
    screen = pg.display.set_mode((SCREEN_W, SCREEN_H))
    pg.display.set_caption('Car Dodger')
    clock = pg.time.Clock()

    # load assets
    road = load_image("road.png", SCREEN_W, SCREEN_H//3)   # if assets/road.png exists
    grass = load_image("grass.png", SCREEN_W//6, SCREEN_H//3)
    player1 = load_image("player1.png", PLAYER_W, PLAYER_H)
    player2 = load_image("player2.png", PLAYER_W, PLAYER_H)
    enemy_img = load_image("enemy.png", ENEMY_W, ENEMY_H)

# correct car selection logic
    player_img = player1 if selected_car == "player1" else player2


    # game state
    score = 0
    enemies = []   # dicts {rect, lane, speed, passed}
    last_spawn = pg.time.get_ticks()
    spawn_ms = DIFF[difficulty]['spawn_ms']
    min_sp = DIFF[difficulty]['min']
    max_sp = DIFF[difficulty]['max']
    scroll = DIFF[difficulty]['scroll']

    # scrolling positions for road & grass
    road_h = road.get_height()
    grass_h = grass.get_height()
    offset = 0

    # player pos: start middle lane
    px = LANE_X[1]
    py = SCREEN_H - PLAYER_H - 20
    player_rect = pg.Rect(px, py, PLAYER_W, PLAYER_H)

    running = True

    font = pg.font.SysFont('Arial', 20)
    high_text = font.render('High Score: --', True, (255,255,0))  # updated in loop later

    # function to spawn
    def spawn():
        lane = rnd.randint(0, LANES-1)
        x = LANE_X[lane]
        y = -ENEMY_H - rnd.randint(0, 300)
        speed = rnd.uniform(min_sp, max_sp)
        rect = pg.Rect(x, y, ENEMY_W, ENEMY_H)
        enemies.append({'rect': rect, 'lane': lane, 'speed': speed, 'passed': False})

    # main loop
    while running:
        dt = clock.tick(FPS)
        for ev in pg.event.get():
            if ev.type == pg.QUIT:
                running = False
            if ev.type == pg.KEYDOWN:
                if ev.key == pg.K_ESCAPE:
                    running = False

        # input: lane-switch with left/right arrows
        keys = pg.key.get_pressed()
        if keys[pg.K_LEFT] or keys[pg.K_a]:
            # move to left lane
            cur_lane = min(range(LANES), key=lambda i: abs(LANE_X[i]-player_rect.x))
            new_lane = max(0, cur_lane-1)
            player_rect.x = LANE_X[new_lane]
        if keys[pg.K_RIGHT] or keys[pg.K_d]:
            cur_lane = min(range(LANES), key=lambda i: abs(LANE_X[i]-player_rect.x))
            new_lane = min(LANES-1, cur_lane+1)
            player_rect.x = LANE_X[new_lane]

        # spawning logic (uses time)
        now = pg.time.get_ticks()
        if now - last_spawn > spawn_ms:
            spawn()
            last_spawn = now
            # small random jitter to spawn_ms per spawn
            spawn_ms = max(200, DIFF[difficulty]['spawn_ms'] + rnd.randint(-200, 200))

        # update enemies
        rem = []
        for e in enemies:
            e['rect'].y += e['speed']
            # collision
            if e['rect'].colliderect(player_rect):
                running = False
            # scoring when passes player
            if not e['passed'] and e['rect'].y > player_rect.y + player_rect.height:
                e['passed'] = True
                ec = e['rect'].x + ENEMY_W/2
                pc = player_rect.x + PLAYER_W/2
                dist = abs(ec - pc)
                if dist <= CLOSE_THRESH:
                    score += 250
                else:
                    score += 150
            if e['rect'].y > SCREEN_H + 200:
                rem.append(e)
        for r in rem:
            enemies.remove(r)

        # scroll background
        offset = (offset + scroll) % max(1, road_h)

        # draw background: grass left/right, road tiled
        screen.fill((30,30,30))
        # left grass tiles
        gx = 0
        while gx < SCREEN_H + grass_h:
            screen.blit(grass, (0, gx - offset))
            screen.blit(grass, (SCREEN_W - grass.get_width(), gx - offset))
            gx += grass_h

        # road centered
        rx = (SCREEN_W - road.get_width())//2
        ry = -offset
        while ry < SCREEN_H:
            screen.blit(road, (rx, ry))
            ry += road_h

        # draw lane dividers on top of road (dashed)
        road_left = rx
        road_right = rx + road.get_width()
        lane_w = (road.get_width()) // 4
        for i in range(1, 4):
            x = road_left + i*lane_w
            for y in range(0, SCREEN_H, 40):
                pg.draw.line(screen, (200,200,200), (x, y+10), (x, y+20), 4)

        # draw enemies
        for e in enemies:
            screen.blit(enemy_img, (e['rect'].x, e['rect'].y))

        # draw player
        screen.blit(player_img, (player_rect.x, player_rect.y))

        # HUD
        scr = font.render(f"Score: {score}", True, (255,255,255))
        diff_txt = font.render(f"Mode: {difficulty}", True, (200,200,200))
        screen.blit(scr, (10,10))
        screen.blit(diff_txt, (SCREEN_W - 150, 10))

        pg.display.flip()

    # game over: save score
    if user_id:
        try:
            save_score(user_id, score, difficulty)
        except Exception:
            pass

    # small delay and quit to return to launcher
    time.sleep(0.5)
    pg.quit()
    return
