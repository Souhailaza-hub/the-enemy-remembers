import json
import math
import random
import sys
from pathlib import Path

import pygame

pygame.init()
pygame.display.set_caption("The Enemy Remembers")
WIDTH, HEIGHT = 1100, 720
screen = pygame.display.set_mode((WIDTH, HEIGHT))
clock = pygame.time.Clock()
FONT = pygame.font.SysFont("trebuchetms", 23, bold=True)
SMALL = pygame.font.SysFont("trebuchetms", 17)
CONTROL = pygame.font.SysFont("trebuchetms", 14)
MED = pygame.font.SysFont("trebuchetms", 31, bold=True)
BIG = pygame.font.SysFont("trebuchetms", 53, bold=True)
TITLE = pygame.font.SysFont("trebuchetms", 72, bold=True)

# A compact, sunny arcade palette: ink, paper, cobalt, tomato and marigold.
BG = (249, 242, 222)
PANEL = (255, 250, 235)
WHITE = (255, 250, 235)
INK = (34, 47, 65)
MUTED = (105, 115, 122)
BLUE = (37, 112, 226)
BLUE_LIGHT = (114, 190, 255)
RED = (229, 70, 56)
RED_LIGHT = (255, 164, 132)
GOLD = (241, 177, 44)
GREEN = (34, 153, 112)
PURPLE = (126, 83, 193)
ARENA = pygame.Rect(22, 102, WIDTH - 44, HEIGHT - 124)
BEST_FILE = Path(__file__).with_name("best_run.json")
PLAYER_R = 14
DIFFICULTY_NAMES = ("Easy", "Medium", "Hard")
DIFFICULTIES = {
    "Easy": {"accent": GREEN, "description": "room to learn", "lives": 4,
             "spawn_start": 3.7, "spawn_floor": 1.7, "spawn_decay": 0.0055,
             "enemy_cap": 10, "enemy_base_cap": 2, "cap_period": 30,
             "wave_seconds": 32, "speed_base": 48, "speed_ramp": 0.30,
             "speed_ramp_cap": 34, "speed_adaptation": 10, "wave_speed": 1,
             "dodger_wave": 5, "dodger_chance": 0.08, "dodger_step": 0.035,
             "dodger_cap": 0.24, "dodger_speed": 1.06, "dodge_bonus": 0.2,
             "pack_after": 75, "pack_chance": 0.06, "pack_three_after": 999,
             "hunter_hp": 1, "still_speed": 5},
    "Medium": {"accent": GOLD, "description": "a fair fight", "lives": 3,
               "spawn_start": 3.2, "spawn_floor": 1.2, "spawn_decay": 0.008,
               "enemy_cap": 16, "enemy_base_cap": 3, "cap_period": 18,
               "wave_seconds": 24, "speed_base": 60, "speed_ramp": 0.45,
               "speed_ramp_cap": 45, "speed_adaptation": 18, "wave_speed": 2,
               "dodger_wave": 3, "dodger_chance": 0.10, "dodger_step": 0.035,
               "dodger_cap": 0.35, "dodger_speed": 1.08, "dodge_bonus": 0.45,
               "pack_after": 60, "pack_chance": 0.14, "pack_three_after": 999,
               "hunter_hp": 2, "still_speed": 9},
    "Hard": {"accent": RED, "description": "no room to breathe", "lives": 3,
             "spawn_start": 1.55, "spawn_floor": 0.42, "spawn_decay": 0.012,
             "enemy_cap": 32, "enemy_base_cap": 6, "cap_period": 8,
             "wave_seconds": 16, "speed_base": 105, "speed_ramp": 0.90,
             "speed_ramp_cap": 110, "speed_adaptation": 48, "wave_speed": 4,
             "dodger_wave": 2, "dodger_chance": 0.38, "dodger_step": 0.08,
             "dodger_cap": 0.78, "dodger_speed": 1.30, "dodge_bonus": 0.95,
             "pack_after": 22, "pack_chance": 0.38, "pack_three_after": 55,
             "hunter_hp": 2, "still_speed": 20},
}


def load_bests():
    try:
        data = json.loads(BEST_FILE.read_text())
        stored = data.get("best_by_difficulty", {})
        legacy_medium = float(data.get("best_seconds", 0))
        return {name: max(0.0, float(stored.get(name, legacy_medium if name == "Medium" else 0)))
                for name in DIFFICULTY_NAMES}
    except (OSError, ValueError, TypeError):
        return {name: 0.0 for name in DIFFICULTY_NAMES}


def save_best(difficulty, value):
    try:
        bests = load_bests()
        bests[difficulty] = max(bests[difficulty], value)
        BEST_FILE.write_text(json.dumps({
            "best_seconds": round(max(bests.values()), 2),
            "best_by_difficulty": {name: round(score, 2) for name, score in bests.items()},
        }, indent=2))
    except OSError:
        pass


def text(dst, value, font, color, pos, anchor="topleft"):
    image = font.render(value, True, color)
    rect = image.get_rect()
    setattr(rect, anchor, pos)
    dst.blit(image, rect)


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def safe_normalize(v, fallback=None):
    if v.length_squared() < 0.0001:
        return fallback.copy() if fallback is not None else pygame.Vector2(1, 0)
    return v.normalize()


def format_time(sec):
    total = int(sec)
    return f"{total // 60:02d}:{total % 60:02d}"


def move_in_arena(pos, vel, radius, dt):
    pos += vel * dt
    pos.x = clamp(pos.x, ARENA.left + radius, ARENA.right - radius)
    pos.y = clamp(pos.y, ARENA.top + radius, ARENA.bottom - radius)


def segment_distance(point, start, end):
    line = end - start
    if line.length_squared() == 0:
        return point.distance_to(start)
    t = clamp((point - start).dot(line) / line.length_squared(), 0, 1)
    return point.distance_to(start + line * t)


def draw_background():
    screen.fill(BG)
    pygame.draw.rect(screen, (255, 250, 235), ARENA)
    # Small floor marks and corner ticks give the open field a deliberate print-like finish.
    for x in range(ARENA.left + 28, ARENA.right, 54):
        for y in range(ARENA.top + 28, ARENA.bottom, 54):
            pygame.draw.circle(screen, (239, 230, 207), (x, y), 1)
    pygame.draw.rect(screen, (204, 191, 161), ARENA, 2)
    tick = (181, 163, 126)
    for x, sx in ((ARENA.left, 1), (ARENA.right, -1)):
        for y, sy in ((ARENA.top, 1), (ARENA.bottom, -1)):
            pygame.draw.line(screen, tick, (x, y), (x + 15 * sx, y), 3)
            pygame.draw.line(screen, tick, (x, y), (x, y + 15 * sy), 3)


def draw_modal(title, subtitle, lines, action, accent=BLUE):
    shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    shade.fill((34, 47, 65, 105))
    screen.blit(shade, (0, 0))
    card = pygame.Rect(250, 170, 600, 390)
    pygame.draw.rect(screen, (224, 213, 189), card.move(0, 7), border_radius=18)
    pygame.draw.rect(screen, PANEL, card, border_radius=18)
    pygame.draw.rect(screen, (225, 216, 195), card, 2, border_radius=18)
    pygame.draw.rect(screen, accent, (card.left, card.top, card.width, 9), border_radius=5)
    text(screen, title, TITLE, INK, (WIDTH // 2, 205), "midtop")
    text(screen, subtitle, MED, accent, (WIDTH // 2, 288), "midtop")
    for i, line in enumerate(lines):
        text(screen, line, FONT if i == 0 else SMALL, MUTED if i else INK,
             (WIDTH // 2, 354 + i * 30), "midtop")
    pygame.draw.rect(screen, accent, (WIDTH // 2 - 190, 490, 380, 46), border_radius=10)
    text(screen, action, FONT, WHITE, (WIDTH // 2, 513), "center")


def draw_title_menu(selected):
    shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    shade.fill((34, 47, 65, 105))
    screen.blit(shade, (0, 0))
    card = pygame.Rect(230, 102, 640, 510)
    pygame.draw.rect(screen, (224, 213, 189), card.move(0, 7), border_radius=18)
    pygame.draw.rect(screen, PANEL, card, border_radius=18)
    pygame.draw.rect(screen, (225, 216, 195), card, 2, border_radius=18)
    pygame.draw.rect(screen, DIFFICULTIES[DIFFICULTY_NAMES[selected]]["accent"],
                     (card.left, card.top, card.width, 9), border_radius=5)
    text(screen, "REMEMBER THIS", TITLE, INK, (WIDTH // 2, 130), "midtop")
    text(screen, "SHOOT  ·  SURVIVE  ·  SWITCH IT UP", MED, BLUE,
         (WIDTH // 2, 211), "midtop")
    text(screen, "The pack studies your favorite escape route.", FONT, INK,
         (WIDTH // 2, 274), "midtop")
    text(screen, "Aim with the mouse. Change your pattern to break its read.", SMALL, MUTED,
         (WIDTH // 2, 304), "midtop")
    text(screen, "CHOOSE YOUR CHALLENGE", SMALL, MUTED, (WIDTH // 2, 349), "midtop")
    tile_w, tile_h, gap = 158, 84, 12
    left = (WIDTH - (tile_w * 3 + gap * 2)) // 2
    for i, name in enumerate(DIFFICULTY_NAMES):
        settings = DIFFICULTIES[name]
        rect = pygame.Rect(left + i * (tile_w + gap), 376, tile_w, tile_h)
        selected_tile = i == selected
        fill = settings["accent"] if selected_tile else (247, 241, 225)
        title_color = WHITE if selected_tile else INK
        desc_color = WHITE if selected_tile else MUTED
        pygame.draw.rect(screen, fill, rect, border_radius=11)
        pygame.draw.rect(screen, settings["accent"], rect, 3 if selected_tile else 1, border_radius=11)
        text(screen, name.upper(), FONT, title_color, (rect.centerx, rect.top + 17), "midtop")
        text(screen, settings["description"], SMALL, desc_color,
             (rect.centerx, rect.top + 49), "midtop")
    text(screen, "CLICK A CARD  ·  OR PRESS 1 / 2 / 3", SMALL, MUTED,
         (WIDTH // 2, 466), "midtop")
    start = pygame.Rect(WIDTH // 2 - 190, 490, 380, 48)
    pygame.draw.rect(screen, DIFFICULTIES[DIFFICULTY_NAMES[selected]]["accent"], start, border_radius=10)
    text(screen, "PRESS SPACE TO START", FONT, WHITE, start.center, "center")


def draw_gameover_menu(selected, run_difficulty, survived, kills, run_best, style, switches):
    shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    shade.fill((34, 47, 65, 105))
    screen.blit(shade, (0, 0))
    card = pygame.Rect(230, 102, 640, 510)
    pygame.draw.rect(screen, (224, 213, 189), card.move(0, 7), border_radius=18)
    pygame.draw.rect(screen, PANEL, card, border_radius=18)
    pygame.draw.rect(screen, (225, 216, 195), card, 2, border_radius=18)
    accent = DIFFICULTIES[DIFFICULTY_NAMES[selected]]["accent"]
    pygame.draw.rect(screen, accent, (card.left, card.top, card.width, 9), border_radius=5)
    text(screen, "RUN OVER", TITLE, INK, (WIDTH // 2, 126), "midtop")
    text(screen, f"{run_difficulty.upper()}  ·  {format_time(survived)}  ·  {kills} KILLS",
         MED, DIFFICULTIES[run_difficulty]["accent"], (WIDTH // 2, 204), "midtop")
    text(screen, f"Pack read: {style}  ·  Route changes: {switches}", FONT, INK,
         (WIDTH // 2, 267), "midtop")
    text(screen, f"Best on {run_difficulty}: {format_time(run_best)}", SMALL, MUTED,
         (WIDTH // 2, 296), "midtop")
    text(screen, "CHOOSE YOUR NEXT RUN", SMALL, MUTED, (WIDTH // 2, 343), "midtop")
    tile_w, tile_h, gap = 158, 84, 12
    left = (WIDTH - (tile_w * 3 + gap * 2)) // 2
    for i, name in enumerate(DIFFICULTY_NAMES):
        settings = DIFFICULTIES[name]
        rect = pygame.Rect(left + i * (tile_w + gap), 370, tile_w, tile_h)
        selected_tile = i == selected
        fill = settings["accent"] if selected_tile else (247, 241, 225)
        title_color = WHITE if selected_tile else INK
        desc_color = WHITE if selected_tile else MUTED
        pygame.draw.rect(screen, fill, rect, border_radius=11)
        pygame.draw.rect(screen, settings["accent"], rect, 3 if selected_tile else 1, border_radius=11)
        text(screen, name.upper(), FONT, title_color, (rect.centerx, rect.top + 17), "midtop")
        text(screen, settings["description"], SMALL, desc_color,
             (rect.centerx, rect.top + 49), "midtop")
    text(screen, "CLICK A CARD  ·  OR PRESS 1 / 2 / 3", SMALL, MUTED,
         (WIDTH // 2, 460), "midtop")
    start = pygame.Rect(WIDTH // 2 - 190, 484, 380, 48)
    pygame.draw.rect(screen, accent, start, border_radius=10)
    text(screen, f"PLAY {DIFFICULTY_NAMES[selected].upper()} AGAIN", FONT, WHITE,
         start.center, "center")


def new_enemy(elapsed, learned, player_pos, target_history, settings):
    side = random.randrange(4)
    if side == 0:
        pos = pygame.Vector2(random.uniform(ARENA.left + 25, ARENA.right - 25), ARENA.top + 23)
    elif side == 1:
        pos = pygame.Vector2(ARENA.right - 23, random.uniform(ARENA.top + 25, ARENA.bottom - 25))
    elif side == 2:
        pos = pygame.Vector2(random.uniform(ARENA.left + 25, ARENA.right - 25), ARENA.bottom - 23)
    else:
        pos = pygame.Vector2(ARENA.left + 23, random.uniform(ARENA.top + 25, ARENA.bottom - 25))
    kind = "hunter"
    wave = 1 + int(elapsed / settings["wave_seconds"])
    if wave >= settings["dodger_wave"]:
        wave_offset = wave - settings["dodger_wave"]
        dodger_chance = min(settings["dodger_cap"], settings["dodger_chance"] + wave_offset * settings["dodger_step"])
    else:
        dodger_chance = 0.0
    if random.random() < dodger_chance:
        kind = "dodger"
    # New enemies inherit a little more knowledge each wave.
    return {
        "pos": pos,
        "vel": pygame.Vector2(0, 0),
        "r": 15 if kind == "hunter" else 13,
        "hp": settings["hunter_hp"] if kind == "hunter" else 1,
        "kind": kind,
        "phase": random.random() * math.tau,
        "hit_flash": 0,
    }


def  main():
    best_by_difficulty = load_bests()
    selected_difficulty = 1
    difficulty = DIFFICULTY_NAMES[selected_difficulty]
    settings = DIFFICULTIES[difficulty]
    best = best_by_difficulty[difficulty]
    run_difficulty = difficulty
    player = pygame.Vector2(ARENA.centerx, ARENA.centery)
    player_vel = pygame.Vector2(0, 0)
    bullets = []
    enemies = []
    particles = []
    # A lightweight movement trail teaches the director how the player tends to move.
    trail = []
    direction_counts = {"left": 0.0, "right": 0.0, "up": 0.0, "down": 0.0}
    style_window = []
    heading_window = []
    style_sample_clock = 0.0
    total_style_samples = 0
    recognized_style = "finding your pattern"
    current_style = "finding your pattern"
    style_confidence = 0.0
    adaptation = 0.0
    style_switches = 0
    confusion = 0.0
    last_switch_time = -99.0
    last_recognition_time = -1.0
    run_seconds = 0.0
    survived = 0.0
    kills = 0
    shots = 0
    hits = 0
    spawn_clock = 0.0
    shot_cooldown = 0.0
    invulnerable = 0.0
    health = settings["lives"]
    dead = False
    paused = False
    game_started = False
    last_aim = pygame.Vector2(1, 0)
    learned = 0.0
    display_note = ""
    note_timer = 0.0
    shot_threats = False
    running = True

    def start_run():
        nonlocal player, player_vel, best, health, dead, paused, game_started
        nonlocal style_sample_clock, total_style_samples, recognized_style, current_style
        nonlocal style_confidence, adaptation, style_switches, confusion
        nonlocal last_switch_time, last_recognition_time, run_seconds, survived
        nonlocal kills, shots, hits, spawn_clock, shot_cooldown, invulnerable, learned
        nonlocal last_aim, display_note, note_timer, run_difficulty
        player = pygame.Vector2(ARENA.centerx, ARENA.centery)
        player_vel = pygame.Vector2(0, 0)
        bullets.clear()
        enemies.clear()
        particles.clear()
        trail.clear()
        direction_counts.update({key: 0.0 for key in direction_counts})
        style_window.clear()
        heading_window.clear()
        style_sample_clock = total_style_samples = 0
        recognized_style = current_style = "finding your pattern"
        style_confidence = adaptation = confusion = 0.0
        style_switches = 0
        last_switch_time = -99.0
        last_recognition_time = -1.0
        run_seconds = survived = 0.0
        kills = shots = hits = spawn_clock = 0
        shot_cooldown = 0.0
        learned = 0.0
        health = settings["lives"]
        best = best_by_difficulty[difficulty]
        invulnerable = 1.0
        dead = paused = False
        game_started = True
        last_aim = pygame.Vector2(1, 0)
        display_note = ""
        note_timer = 0.0
        run_difficulty = difficulty

    while running:
        dt = min(clock.tick(60) / 1000.0, 0.035)
        now = pygame.time.get_ticks() / 1000.0
        mouse = pygame.Vector2(pygame.mouse.get_pos())

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if game_started and not dead:
                        paused = not paused
                    else:
                        running = False
                if event.key == pygame.K_p and game_started and not dead:
                    paused = not paused
                if (not game_started or dead) and event.key in (pygame.K_LEFT, pygame.K_a):
                    selected_difficulty = (selected_difficulty - 1) % len(DIFFICULTY_NAMES)
                    difficulty = DIFFICULTY_NAMES[selected_difficulty]
                    settings = DIFFICULTIES[difficulty]
                    best = best_by_difficulty[difficulty]
                if (not game_started or dead) and event.key in (pygame.K_RIGHT, pygame.K_d):
                    selected_difficulty = (selected_difficulty + 1) % len(DIFFICULTY_NAMES)
                    difficulty = DIFFICULTY_NAMES[selected_difficulty]
                    settings = DIFFICULTIES[difficulty]
                    best = best_by_difficulty[difficulty]
                if (not game_started or dead) and event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                    selected_difficulty = event.key - pygame.K_1
                    difficulty = DIFFICULTY_NAMES[selected_difficulty]
                    settings = DIFFICULTIES[difficulty]
                    best = best_by_difficulty[difficulty]
                if (not game_started or dead) and event.key in (pygame.K_SPACE, pygame.K_RETURN):
                    start_run()
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and not paused:
                if not game_started or dead:
                    tile_y = 370 if dead else 376
                    start_y = 484 if dead else 490
                    start_rect = pygame.Rect(WIDTH // 2 - 190, start_y, 380, 48)
                    tile_w, gap = 158, 12
                    left = (WIDTH - (tile_w * 3 + gap * 2)) // 2
                    for i in range(3):
                        tile_rect = pygame.Rect(left + i * (tile_w + gap), tile_y, tile_w, 84)
                        if tile_rect.collidepoint(event.pos):
                            selected_difficulty = i
                            difficulty = DIFFICULTY_NAMES[i]
                            settings = DIFFICULTIES[difficulty]
                            best = best_by_difficulty[difficulty]
                            break
                    else:
                        if start_rect.collidepoint(event.pos):
                            start_run()

        shot_threats = False
        if game_started and not dead and not paused:
            survived += dt
            run_seconds += dt
            shot_cooldown = max(0, shot_cooldown - dt)
            invulnerable = max(0, invulnerable - dt)
            note_timer = max(0, note_timer - dt)
            keys = pygame.key.get_pressed()
            movement = pygame.Vector2(
                int(keys[pygame.K_d] or keys[pygame.K_RIGHT]) - int(keys[pygame.K_a] or keys[pygame.K_LEFT]),
                int(keys[pygame.K_s] or keys[pygame.K_DOWN]) - int(keys[pygame.K_w] or keys[pygame.K_UP]),
            )
            if movement.length_squared() > 0:
                movement = movement.normalize()
                player_vel = movement * 290
                move_in_arena(player, player_vel, PLAYER_R, dt)
                if abs(movement.x) > 0.2:
                    direction_counts["right" if movement.x > 0 else "left"] += dt * abs(movement.x)
                if abs(movement.y) > 0.2:
                    direction_counts["down" if movement.y > 0 else "up"] += dt * abs(movement.y)
            else:
                player_vel *= max(0, 1 - 9 * dt)

            trail.append((now, player.copy()))
            trail = [(t, p) for t, p in trail if now - t < 2.4]
            # Build a rolling behavior profile. Recent behavior detects a change;
            # the longer window is the style the pack has actually learned.
            style_sample_clock += dt
            if style_sample_clock >= 0.15:
                style_sample_clock = 0.0
                label = "still"
                if movement.length_squared() > 0:
                    angle = math.atan2(movement.y, movement.x)
                    octant = int(round(angle / (math.pi / 4))) % 8
                    label = ("right", "down-right", "down", "down-left", "left", "up-left", "up", "up-right")[octant]
                    if abs(movement.x) > 0.2:
                        direction_counts["right" if movement.x > 0 else "left"] += 0.15 * abs(movement.x)
                    if abs(movement.y) > 0.2:
                        direction_counts["down" if movement.y > 0 else "up"] += 0.15 * abs(movement.y)
                style_window.append((now, label))
                total_style_samples += 1
                heading_window.append((now, movement.copy() if movement.length_squared() else pygame.Vector2()))
            style_window = [(t, s) for t, s in style_window if now - t < 7.0]
            heading_window = [(t, v) for t, v in heading_window if now - t < 3.2 and v.length_squared() > 0]
            recent = [s for t, s in style_window if now - t < 1.5]
            counts = {s: sum(1 for _, sample in style_window if sample == s)
                      for s in {sample for _, sample in style_window}}
            recent_counts = {s: recent.count(s) for s in set(recent)}
            if counts:
                candidate_style = max(counts, key=counts.get)
                style_confidence = counts[candidate_style] / max(1, len(style_window))
                # A sustained turn in the movement vector identifies circling,
                # even when its compass direction changes constantly.
                turn_total = 0.0
                turn_signed = 0.0
                for (_, first), (_, second) in zip(heading_window, heading_window[1:]):
                    a, b = safe_normalize(first), safe_normalize(second)
                    turn = math.atan2(a.x * b.y - a.y * b.x, a.dot(b))
                    turn_total += abs(turn)
                    turn_signed += turn
                turn_consistency = abs(turn_signed) / max(0.01, turn_total)
                if turn_total > 2.8 and turn_consistency > 0.66:
                    candidate_style = "clockwise circles" if turn_signed > 0 else "counterclockwise circles"
                    style_confidence = min(1.0, turn_consistency * 0.9)
                current_style = candidate_style
                if len(style_window) >= 25 and candidate_style != recognized_style:
                    if last_recognition_time < 0 or now - last_recognition_time > 5.5:
                        recognized_style = candidate_style
                        last_recognition_time = now
                        display_note = f"PACK ADAPTED: {recognized_style.upper()}"
                        note_timer = 2.6
                recent_style = max(recent_counts, key=recent_counts.get) if recent_counts else candidate_style
                recent_strength = recent_counts.get(recent_style, 0) / max(1, len(recent))
                if (recognized_style != "finding your pattern" and len(recent) >= 7 and recent_strength >= 0.68 and
                        recent_style != recognized_style and now - last_switch_time > 2.5):
                    confusion = 1.0
                    style_switches += 1
                    last_switch_time = now
                    display_note = "YOU BROKE ITS READ  ·  PREDICTION WEAKENED"
                    note_timer = 2.0
            confusion = max(0.0, confusion - dt * 0.22)
            learned = min(1.0, total_style_samples / 100.0 + max(0, kills - 7) * 0.012)
            adaptation = learned * style_confidence * (1.0 - confusion)

            # Left click or hold fires precise blue bolts toward the cursor.
            mouse_buttons = pygame.mouse.get_pressed()
            if (mouse_buttons[0] or keys[pygame.K_SPACE]) and shot_cooldown <= 0:
                aim = safe_normalize(mouse - player, last_aim)
                last_aim = aim
                muzzle = player + aim * (PLAYER_R + 8)
                bullets.append({"pos": muzzle, "vel": aim * 650, "life": 1.35, "r": 5})
                shots += 1
                shot_cooldown = 0.15

            # Continuous enemy arrivals. The interval shrinks and the group cap rises.
            spawn_clock += dt
            spawn_interval = max(settings["spawn_floor"],
                                 settings["spawn_start"] - survived * settings["spawn_decay"])
            enemy_cap = min(settings["enemy_cap"],
                            settings["enemy_base_cap"] + int(survived / settings["cap_period"]))
            if spawn_clock >= spawn_interval and len(enemies) < enemy_cap:
                spawn_clock = 0
                pack_size = 1
                if survived > settings["pack_after"] and random.random() < settings["pack_chance"]:
                    pack_size = 2
                    if survived > settings["pack_three_after"] and random.random() < settings["pack_chance"] * 0.4:
                        pack_size = 3
                for _ in range(pack_size):
                    enemies.append(new_enemy(survived, learned, player, trail, settings))

            # Dodge lanes: enemies see shots and choose an evasive side. Prediction
            # uses recent player travel, including turns, instead of only chasing current position.
            for enemy in enemies:
                pos = enemy["pos"]
                direct = safe_normalize(player - pos)
                lead = player + player_vel * (0.18 + adaptation * 0.42)
                if len(trail) >= 2:
                    past_pos = trail[max(0, len(trail) - 9)][1]
                    recent_velocity = safe_normalize(player - past_pos, direct)
                    lead += recent_velocity * (18 + adaptation * 62)
                chase = safe_normalize(lead - pos, direct)

                # Once the movement pattern is clear, bias interception toward the
                # player's preferred side, while leaving a visible counterplay gap.
                style_vectors = {"left": pygame.Vector2(-1, 0), "right": pygame.Vector2(1, 0),
                                 "up": pygame.Vector2(0, -1), "down": pygame.Vector2(0, 1),
                                 "down-right": pygame.Vector2(1, 1), "down-left": pygame.Vector2(-1, 1),
                                 "up-right": pygame.Vector2(1, -1), "up-left": pygame.Vector2(-1, -1)}
                if adaptation > 0.18 and recognized_style in style_vectors:
                    favored = safe_normalize(style_vectors[recognized_style])
                    intercept = player + favored * (60 + adaptation * 115)
                    toward_intercept = safe_normalize(intercept - pos, chase)
                    chase = safe_normalize(chase * (1 - adaptation * 0.5) + toward_intercept * adaptation * 0.5, chase)
                elif adaptation > 0.3 and "circles" in recognized_style:
                    turn = 1 if recognized_style == "clockwise circles" else -1
                    tangent = pygame.Vector2(-(player.y - pos.y), player.x - pos.x) * turn
                    intercept = player + safe_normalize(tangent, chase) * (70 + adaptation * 80)
                    chase = safe_normalize(chase * (1 - adaptation * 0.38) + safe_normalize(intercept - pos) * adaptation * 0.38, chase)

                # Evade only shots whose projected path actually crosses the enemy.
                dodge = pygame.Vector2(0, 0)
                for bullet in bullets:
                    shot_dir = safe_normalize(bullet["vel"])
                    to_enemy = pos - bullet["pos"]
                    along = to_enemy.dot(shot_dir)
                    lateral = abs(shot_dir.x * to_enemy.y - shot_dir.y * to_enemy.x)
                    if 0 < along < 190 and lateral < enemy["r"] + 13:
                        shot_threats = True
                        cross = shot_dir.x * to_enemy.y - shot_dir.y * to_enemy.x
                        side = 1 if cross >= 0 else -1
                        perpendicular = pygame.Vector2(-shot_dir.y, shot_dir.x) * side
                        urgency = (1 - along / 190) * (0.2 + adaptation * (1.0 + settings["dodge_bonus"]))
                        dodge += perpendicular * urgency
                if enemy["kind"] == "dodger":
                    # Dodger enemies strafe and fake-turn more often, especially later.
                    side = 1 if math.sin(now * 2.1 + enemy["phase"]) > 0 else -1
                    dodge += pygame.Vector2(-chase.y, chase.x) * side * (0.22 + adaptation * 0.8)
                desired = safe_normalize(chase + dodge, chase)
                wave = 1 + int(survived / settings["wave_seconds"])
                base_speed = (settings["speed_base"] +
                              min(settings["speed_ramp_cap"], survived * settings["speed_ramp"]) +
                              adaptation * settings["speed_adaptation"] +
                              min(36, (wave - 1) * settings["wave_speed"]))
                if recognized_style == "still" and adaptation > 0.2:
                    base_speed += settings["still_speed"] * adaptation
                if enemy["kind"] == "dodger":
                    base_speed *= settings["dodger_speed"]
                enemy["vel"] = enemy["vel"].lerp(desired * base_speed, min(1, dt * (2.1 + learned * 2.2)))
                move_in_arena(pos, enemy["vel"], enemy["r"], dt)
                enemy["hit_flash"] = max(0, enemy["hit_flash"] - dt)

            for bullet in bullets[:]:
                bullet["pos"] += bullet["vel"] * dt
                bullet["life"] -= dt
                if bullet["life"] <= 0 or not ARENA.collidepoint(bullet["pos"].x, bullet["pos"].y):
                    bullets.remove(bullet)
                    continue
                for enemy in enemies[:]:
                    if bullet["pos"].distance_to(enemy["pos"]) < enemy["r"] + bullet["r"]:
                        enemy["hp"] -= 1
                        enemy["hit_flash"] = 0.09
                        if bullet in bullets:
                            bullets.remove(bullet)
                        if enemy["hp"] <= 0:
                            enemies.remove(enemy)
                            kills += 1
                            for _ in range(12):
                                angle = random.random() * math.tau
                                speed = random.uniform(45, 170)
                                particles.append({"pos": enemy["pos"].copy(), "vel": pygame.Vector2(math.cos(angle), math.sin(angle)) * speed,
                                                  "life": random.uniform(0.22, 0.5), "max": 0.5, "color": GOLD if _ % 3 == 0 else RED})
                            # Learning accelerates with combat: surviving and shooting
                            # gives the enemy more examples of how the player dodges.
                            learned = min(1.0, learned + 0.006)
                        else:
                            hits += 1
                        break

            hit_enemy = next((e for e in enemies
                              if player.distance_to(e["pos"]) < PLAYER_R + e["r"]), None)
            if invulnerable <= 0 and hit_enemy is not None:
                health -= 1
                invulnerable = 1.1
                player += safe_normalize(player - hit_enemy["pos"]) * 48
                move_in_arena(player, pygame.Vector2(), PLAYER_R, dt)
                for _ in range(9):
                    angle = random.random() * math.tau
                    particles.append({"pos": player.copy(),
                                      "vel": pygame.Vector2(math.cos(angle), math.sin(angle)) * random.uniform(60, 180),
                                      "life": random.uniform(0.2, 0.42), "max": 0.42, "color": BLUE_LIGHT})
                if health <= 0:
                    dead = True
                    if survived > best:
                        best = survived
                        best_by_difficulty[difficulty] = best
                        save_best(difficulty, best)

        # Particle updates are harmless after death and add impact feedback.
        for particle in particles[:]:
            particle["pos"] += particle["vel"] * dt
            particle["vel"] *= max(0, 1 - dt * 3)
            particle["life"] -= dt
            if particle["life"] <= 0:
                particles.remove(particle)

        draw_background()
        # Player aim line, bullets and actors
        aim = safe_normalize(mouse - player, last_aim)
        pygame.draw.line(screen, (185, 174, 147), player, player + aim * 30, 2)
        for bullet in bullets:
            pygame.draw.circle(screen, GOLD, (round(bullet["pos"].x), round(bullet["pos"].y)), 7)
            pygame.draw.circle(screen, (255, 231, 154), (round(bullet["pos"].x), round(bullet["pos"].y)), 3)
        for particle in particles:
            alpha = clamp(particle["life"] / particle["max"], 0, 1)
            radius = max(1, int(4 * alpha))
            pygame.draw.circle(screen, particle["color"], (round(particle["pos"].x), round(particle["pos"].y)), radius)
        for enemy in enemies:
            ep = enemy["pos"]
            color = WHITE if enemy["hit_flash"] else (RED if enemy["kind"] == "hunter" else PURPLE)
            if enemy["kind"] == "hunter":
                points = [(ep.x, ep.y - 19), (ep.x + 17, ep.y - 5), (ep.x + 13, ep.y + 14),
                          (ep.x, ep.y + 19), (ep.x - 13, ep.y + 14), (ep.x - 17, ep.y - 5)]
                pygame.draw.polygon(screen, (157, 57, 51), points)
                pygame.draw.polygon(screen, color, [(ep.x, ep.y - 14), (ep.x + 12, ep.y - 4),
                                                    (ep.x + 9, ep.y + 10), (ep.x, ep.y + 14),
                                                    (ep.x - 9, ep.y + 10), (ep.x - 12, ep.y - 4)])
            else:
                pygame.draw.polygon(screen, (81, 53, 133), [(ep.x, ep.y - 19), (ep.x + 18, ep.y),
                                                           (ep.x, ep.y + 19), (ep.x - 18, ep.y)])
                pygame.draw.polygon(screen, color, [(ep.x, ep.y - 14), (ep.x + 13, ep.y),
                                                    (ep.x, ep.y + 14), (ep.x - 13, ep.y)])
            pygame.draw.circle(screen, RED_LIGHT if enemy["kind"] == "hunter" else (218, 193, 255),
                               (round(ep.x - 4), round(ep.y - 5)), 3)
            if enemy["hp"] > 1:
                pygame.draw.circle(screen, (255, 197, 78), (round(ep.x + 5), round(ep.y - 5)), 3)
        if invulnerable <= 0 or int(now * 14) % 2 == 0:
            nose = player + aim * 20
            side = pygame.Vector2(-aim.y, aim.x) * 13
            tail = player - aim * 14
            ship_points = [nose, player + side, tail, player - side]
            pygame.draw.polygon(screen, (24, 69, 133), [(p.x, p.y + 3) for p in ship_points])
            pygame.draw.polygon(screen, BLUE, ship_points)
            pygame.draw.circle(screen, BLUE_LIGHT, (round(player.x), round(player.y)), 5)

        # HUD: five aligned blocks with consistent labels and separators.
        pygame.draw.rect(screen, PANEL, (0, 0, WIDTH, 92))
        pygame.draw.line(screen, (222, 211, 187), (0, 91), (WIDTH, 91), 2)
        for divider_x in (286, 488, 650, 817):
            pygame.draw.line(screen, (228, 218, 197), (divider_x, 15), (divider_x, 77), 1)

        text(screen, "THE ENEMY REMEMBERS", FONT, INK, (24, 13))
        text(screen, "WASD MOVE  ·  MOUSE AIM  ·  CLICK FIRE", CONTROL, MUTED, (24, 48))

        text(screen, "SURVIVAL", SMALL, MUTED, (310, 8))
        text(screen, format_time(survived), BIG, INK, (310, 23))
        text(screen, "BEST  " + format_time(best), SMALL, GOLD, (312, 72))

        text(screen, "KILLS", SMALL, MUTED, (510, 8))
        text(screen, f"{kills:02d}", MED, INK, (510, 29))
        text(screen, f"WAVE  {1 + int(survived / settings['wave_seconds'])}", SMALL, MUTED, (510, 69))
        text(screen, difficulty.upper(), SMALL, settings["accent"], (579, 8))

        text(screen, "HEALTH", SMALL, MUTED, (673, 14))
        for i in range(settings["lives"]):
            pygame.draw.circle(screen, RED if i < health else (218, 207, 183), (686 + i * 19, 48), 7)

        text(screen, "ENEMY READ", SMALL, MUTED, (835, 8))
        pygame.draw.rect(screen, (231, 222, 201), (835, 31, 230, 13), border_radius=6)
        pygame.draw.rect(screen, GREEN if learned < 0.6 else GOLD,
                         (835, 35, int(230 * learned), 14), border_radius=7)
        if confusion > 0.45:
            learned_text = "Read broken · recalibrating"
        elif learned < 0.28:
            learned_text = "Studying your movement"
        else:
            style_short = {"clockwise circles": "CW circling",
                           "counterclockwise circles": "CCW circling"}.get(recognized_style, recognized_style)
            learned_text = f"Read: {style_short}"
        if adaptation > 0.52 and game_started and not dead and shot_threats:
            learned_text = "Dodging an incoming shot"
        text(screen, learned_text, SMALL, GREEN if confusion > 0.45 else GOLD, (835, 54))
        if note_timer > 0:
            note_box = pygame.Rect(ARENA.centerx - 250, ARENA.top + 13, 500, 34)
            pygame.draw.rect(screen, (255, 235, 190), note_box, border_radius=8)
            pygame.draw.rect(screen, GOLD, note_box, 2, border_radius=8)
            text(screen, display_note, SMALL, INK, note_box.center, "center")

        if not game_started:
            draw_title_menu(selected_difficulty)
        elif dead:
            draw_gameover_menu(selected_difficulty, run_difficulty, survived, kills,
                               best_by_difficulty[run_difficulty], recognized_style, style_switches)
        elif paused:
            draw_modal("TAKE A BREATHER", "THE PACK IS WAITING",
                       [f"Run time  {format_time(survived)}     ·     Hunters  {kills}",
                       f"{difficulty} mode  ·  Your movement pattern is still in its memory."],
                       "PRESS ESC OR P TO RESUME", GOLD)
        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
