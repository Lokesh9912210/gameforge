import asyncio, pygame, math, random, sys

async def main():
    pygame.init()
    screen = pygame.display.set_mode((800, 600))
    clock = pygame.time.Clock()
    font = pygame.font.Font(None, 36)
    font_large = pygame.font.Font(None, 72)

    # Game States
    MENU = 0
    PLAYING = 1
    ROUND_END = 2
    MATCH_END = 3
    state = MENU

    # Constants
    PLAYER_SIZE = 30
    PLAYER_SPEED = 300
    BULLET_RADIUS = 5
    BULLET_SPEED = 600
    BULLET_LIFETIME = 1.5
    SHOOT_COOLDOWN = 0.3
    MAX_HP = 5
    ROUNDS_TO_WIN = 2

    # Colors
    BG_COLOR = (34, 34, 34)
    P1_COLOR = (0, 102, 255)
    P2_COLOR = (255, 51, 51)
    BULLET_COLOR = (255, 255, 0)
    WHITE = (255, 255, 255)
    GREEN = (0, 255, 0)
    RED = (255, 0, 0)

    # Player Class
    class Player:
        def __init__(self, x, y, color, move_keys, shoot_key):
            self.x = x
            self.y = y
            self.start_x = x
            self.start_y = y
            self.color = color
            self.move_keys = move_keys
            self.shoot_key = shoot_key
            self.hp = MAX_HP
            self.facing = (1, 0)  # Default facing right
            self.last_shot_time = 0
            self.wins = 0

        def reset(self):
            self.x = self.start_x
            self.y = self.start_y
            self.hp = MAX_HP
            self.facing = (1, 0) if self.start_x < 400 else (-1, 0)
            self.last_shot_time = 0

    # Initialize Players
    p1 = Player(100, 300, P1_COLOR, {'up': pygame.K_w, 'down': pygame.K_s, 'left': pygame.K_a, 'right': pygame.K_d}, pygame.K_f)
    p2 = Player(700, 300, P2_COLOR, {'up': pygame.K_UP, 'down': pygame.K_DOWN, 'left': pygame.K_LEFT, 'right': pygame.K_RIGHT}, pygame.K_RETURN)

    bullets = []
    round_end_timer = 0
    match_winner = None

    def reset_match():
        nonlocal p1, p2, bullets, state, match_winner
        p1 = Player(100, 300, P1_COLOR, {'up': pygame.K_w, 'down': pygame.K_s, 'left': pygame.K_a, 'right': pygame.K_d}, pygame.K_f)
        p2 = Player(700, 300, P2_COLOR, {'up': pygame.K_UP, 'down': pygame.K_DOWN, 'left': pygame.K_LEFT, 'right': pygame.K_RIGHT}, pygame.K_RETURN)
        bullets = []
        state = PLAYING
        match_winner = None

    def reset_round():
        nonlocal p1, p2, bullets
        p1.reset()
        p2.reset()
        bullets = []

    def update_facing(player, dx, dy):
        if dx != 0 or dy != 0:
            length = math.hypot(dx, dy)
            player.facing = (dx / length, dy / length)

    def shoot(player, current_time):
        if current_time - player.last_shot_time >= SHOOT_COOLDOWN:
            bullets.append({
                'x': player.x,
                'y': player.y,
                'dx': player.facing[0],
                'dy': player.facing[1],
                'owner': player,
                'life': BULLET_LIFETIME
            })
            player.last_shot_time = current_time

    def check_bullet_collision(bullet, player):
        # Simple circle-rect collision approximation
        px, py = player.x, player.y
        bx, by = bullet['x'], bullet['y']
        # Check if bullet center is within player bounds (expanded by radius)
        if (px - PLAYER_SIZE/2 - BULLET_RADIUS <= bx <= px + PLAYER_SIZE/2 + BULLET_RADIUS and
            py - PLAYER_SIZE/2 - BULLET_RADIUS <= by <= py + PLAYER_SIZE/2 + BULLET_RADIUS):
            return True
        return False

    def resolve_player_collision(p1, p2):
        # Simple push-back if overlapping
        dx = p2.x - p1.x
        dy = p2.y - p1.y
        dist = math.hypot(dx, dy)
        min_dist = PLAYER_SIZE
        if dist < min_dist and dist > 0:
            overlap = min_dist - dist
            nx = dx / dist
            ny = dy / dist
            p1.x -= nx * overlap / 2
            p1.y -= ny * overlap / 2
            p2.x += nx * overlap / 2
            p2.y += ny * overlap / 2

    while True:
        dt = clock.tick(60) / 1000.0
        current_time = pygame.time.get_ticks() / 1000.0

        # Event Handling
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if state == PLAYING:
                        state = MENU
                    elif state == MATCH_END:
                        reset_match()
                    elif state == ROUND_END:
                        pass # Ignore pause during round end transition

        # State Logic
        if state == MENU:
            # Draw Menu
            screen.fill(BG_COLOR)
            title = font_large.render("NEON DUEL", True, WHITE)
            screen.blit(title, (400 - title.get_width()//2, 200))
            info1 = font.render("P1: WASD + F", True, P1_COLOR)
            info2 = font.render("P2: Arrows + Enter", True, P2_COLOR)
            info3 = font.render("Press ESC to Quit", True, WHITE)
            screen.blit(info1, (400 - info1.get_width()//2, 300))
            screen.blit(info2, (400 - info2.get_width()//2, 340))
            screen.blit(info3, (400 - info3.get_width()//2, 400))
            pygame.display.flip()
            await asyncio.sleep(0)
            continue

        if state == MATCH_END:
            screen.fill(BG_COLOR)
            win_text = font_large.render(f"Player {match_winner} Wins!", True, WHITE)
            screen.blit(win_text, (400 - win_text.get_width()//2, 250))
            restart_text = font.render("Press ESC to Restart", True, WHITE)
            screen.blit(restart_text, (400 - restart_text.get_width()//2, 350))
            pygame.display.flip()
            await asyncio.sleep(0)
            continue

        if state == ROUND_END:
            round_end_timer -= dt
            if round_end_timer <= 0:
                if p1.wins >= ROUNDS_TO_WIN or p2.wins >= ROUNDS_TO_WIN:
                    match_winner = 1 if p1.wins >= ROUNDS_TO_WIN else 2
                    state = MATCH_END
                else:
                    reset_round()
                    state = PLAYING
            else:
                screen.fill(BG_COLOR)
                # Draw players in frozen state
                pygame.draw.rect(screen, p1.color, (p1.x - PLAYER_SIZE/2, p1.y - PLAYER_SIZE/2, PLAYER_SIZE, PLAYER_SIZE))
                pygame.draw.rect(screen, p2.color, (p2.x - PLAYER_SIZE/2, p2.y - PLAYER_SIZE/2, PLAYER_SIZE, PLAYER_SIZE))
                
                round_text = font_large.render("Round Over!", True, WHITE)
                screen.blit(round_text, (400 - round_text.get_width()//2, 200))
                count_text = font_large.render(f"{math.ceil(round_end_timer)}", True, WHITE)
                screen.blit(count_text, (400 - count_text.get_width()//2, 300))
                score_text = font.render(f"P1: {p1.wins} - P2: {p2.wins}", True, WHITE)
                screen.blit(score_text, (400 - score_text.get_width()//2, 50))
                pygame.display.flip()
                await asyncio.sleep(0)
                continue

        # PLAYING STATE
        # Update Players
        keys = pygame.key.get_pressed()
        
        # P1 Movement
        dx1, dy1 = 0, 0
        if keys[p1.move_keys['up']]: dy1 -= 1
        if keys[p1.move_keys['down']]: dy1 += 1
        if keys[p1.move_keys['left']]: dx1 -= 1
        if keys[p1.move_keys['right']]: dx1 += 1
        if dx1 != 0 or dy1 != 0:
            length = math.hypot(dx1, dy1)
            dx1 /= length
            dy1 /= length
            p1.x += dx1 * PLAYER_SPEED * dt
            p1.y += dy1 * PLAYER_SPEED * dt
            update_facing(p1, dx1, dy1)
        
        # P2 Movement
        dx2, dy2 = 0, 0
        if keys[p2.move_keys['up']]: dy2 -= 1
        if keys[p2.move_keys['down']]: dy2 += 1
        if keys[p2.move_keys['left']]: dx2 -= 1
        if keys[p2.move_keys['right']]: dx2 += 1
        if dx2 != 0 or dy2 != 0:
            length = math.hypot(dx2, dy2)
            dx2 /= length
            dy2 /= length
            p2.x += dx2 * PLAYER_SPEED * dt
            p2.y += dy2 * PLAYER_SPEED * dt
            update_facing(p2, dx2, dy2)

        # Clamp Players to Arena
        p1.x = max(PLAYER_SIZE/2, min(800 - PLAYER_SIZE/2, p1.x))
        p1.y = max(PLAYER_SIZE/2, min(600 - PLAYER_SIZE/2, p1.y))
        p2.x = max(PLAYER_SIZE/2, min(800 - PLAYER_SIZE/2, p2.x))
        p2.y = max(PLAYER_SIZE/2, min(600 - PLAYER_SIZE/2, p2.y))

        # Resolve Player Collision
        resolve_player_collision(p1, p2)

        # Shooting
        if keys[p1.shoot_key]:
            shoot(p1, current_time)
        if keys[p2.shoot_key]:
            shoot(p2, current_time)

        # Update Bullets
        new_bullets = []
        for b in bullets:
            b['x'] += b['dx'] * BULLET_SPEED * dt
            b['y'] += b['dy'] * BULLET_SPEED * dt
            b['life'] -= dt

            # Check Wall Collision
            if b['x'] < BULLET_RADIUS or b['x'] > 800 - BULLET_RADIUS or \
               b['y'] < BULLET_RADIUS or b['y'] > 600 - BULLET_RADIUS:
                continue # Destroy bullet

            # Check Player Collision
            hit = False
            if b['owner'] == p1 and check_bullet_collision(b, p2):
                p2.hp -= 1
                hit = True
            elif b['owner'] == p2 and check_bullet_collision(b, p1):
                p1.hp -= 1
                hit = True
            
            if hit or b['life'] <= 0:
                continue # Destroy bullet
            
            new_bullets.append(b)
        bullets = new_bullets

        # Check Round End
        if p1.hp <= 0 or p2.hp <= 0:
            if p1.hp <= 0:
                p2.wins += 1
            else:
                p1.wins += 1
            state = ROUND_END
            round_end_timer = 3.0

        # Draw
        screen.fill(BG_COLOR)
        
        # Draw Score
        score_text = font.render(f"P1: {p1.wins} - P2: {p2.wins}", True, WHITE)
        screen.blit(score_text, (400 - score_text.get_width()//2, 10))

        # Draw Players
        pygame.draw.rect(screen, p1.color, (p1.x - PLAYER_SIZE/2, p1.y - PLAYER_SIZE/2, PLAYER_SIZE, PLAYER_SIZE))
        pygame.draw.rect(screen, p2.color, (p2.x - PLAYER_SIZE/2, p2.y - PLAYER_SIZE/2, PLAYER_SIZE, PLAYER_SIZE))

        # Draw HP Bars
        # P1 HP Bar
        hp_width = PLAYER_SIZE
        hp_height = 5
        hp_x = p1.x - hp_width/2
        hp_y = p1.y - PLAYER_SIZE/2 - 10
        # Background
        pygame.draw.rect(screen, (50, 50, 50), (hp_x, hp_y, hp_width, hp_height))
        # Fill
        fill_width = (p1.hp / MAX_HP) * hp_width
        # Color gradient: Green to Red
        r = int(255 * (1 - p1.hp / MAX_HP))
        g = int(255 * (p1.hp / MAX_HP))
        pygame.draw.rect(screen, (r, g, 0), (hp_x, hp_y, fill_width, hp_height))

        # P2 HP Bar
        hp_x = p2.x - hp_width/2
        hp_y = p2.y - PLAYER_SIZE/2 - 10
        pygame.draw.rect(screen, (50, 50, 50), (hp_x, hp_y, hp_width, hp_height))
        fill_width = (p2.hp / MAX_HP) * hp_width
        r = int(255 * (1 - p2.hp / MAX_HP))
        g = int(255 * (p2.hp / MAX_HP))
        pygame.draw.rect(screen, (r, g, 0), (hp_x, hp_y, fill_width, hp_height))

        # Draw Bullets
        for b in bullets:
            pygame.draw.circle(screen, BULLET_COLOR, (int(b['x']), int(b['y'])), BULLET_RADIUS)

        pygame.display.flip()
        await asyncio.sleep(0)

    pygame.quit()

asyncio.run(main())
