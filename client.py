import pygame, socket, threading, json, sys

HOST = "127.0.0.1"
PORT = 5555

if len(sys.argv) >= 2:
    ROLE = sys.argv[1].strip()
else:
    ROLE = input("role (red_agent / red_spymaster / blue_agent / blue_spymaster): ").strip()
if len(sys.argv) >= 3:
    NAME = sys.argv[2].strip()
else:
    NAME = input("Your name: ").strip() or ROLE

pygame.init()
screen = pygame.display.set_mode((800, 700))
pygame.display.set_caption(f"Codenames – {NAME}")
font = pygame.font.SysFont(None, 24)
clock = pygame.time.Clock()

game = {}
chat = ""
active = False
client_id = None
sock = None
CARD_START_Y = 130
RESET_BUTTON_RECT = pygame.Rect(0, 0, 0, 0)

# not the prettiest vodoo magic down below
def connect_and_recv():
    global game, client_id, sock
    try:
        s = socket.socket()
        s.settimeout(10.0)
        s.connect((HOST, PORT))
        s.settimeout(None)
        sock = s
        sock.sendall((ROLE + "\n").encode())
        sock.sendall((NAME + "\n").encode())
        buf = b""
        while b"\n" not in buf:
            buf += sock.recv(256)
        first_line, buf = buf.split(b"\n", 1)
        client_id = int(first_line.decode().strip())
    except Exception as err:
        game = {"error": str(err), "turn": "", "cards": [], "chat": []}
        return
    while True:
        try:
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                if line:
                    game = json.loads(line.decode())
            data = sock.recv(4096)
            if not data:
                break
            buf += data
        except Exception:
            break

def send(message):
    if sock is None:
        return
    if client_id is not None:
        message["client_id"] = client_id
    sock.sendall((json.dumps(message) + "\n").encode())

threading.Thread(target=connect_and_recv, daemon=True).start()

def draw():
    screen.fill((0, 0, 50))

    if client_id is None and game.get("error"):
        screen.blit(font.render("Connection failed: " + game["error"], 1, (255, 100, 100)), (50, 50))
        screen.blit(font.render("Close and try again.", 1, (255, 255, 255)), (50, 80))
        return
    if client_id is None:
        screen.blit(font.render("Connecting...", 1, (255, 255, 200)), (50, 50))
        return

    # draw team members
    teams = game.get("teams", {})
    y_top = 8
    for team_name, color in [("red", (255, 120, 120)), ("blue", (100, 120, 255))]:
        members = teams.get(team_name, [])
        parts = [m.get("name", "?") + (" (spymaster)" if m.get("is_spymaster") else "") for m in members]
        line = team_name.capitalize() + ": " + (", ".join(parts) if parts else "—")
        screen.blit(font.render(line, 1, color), (10, y_top))
        y_top += 22

    if "turn" in game:
        screen.blit(font.render(f"TURN: {game['turn']}", 1, (255, 255, 255)), (10, y_top))
    y_top += 24
    phase = game.get("phase", "hint")
    phase_text = "Guessing" if phase == "guessing" else "Waiting for hint"
    screen.blit(font.render(f"Phase: {phase_text}", 1, (200, 200, 200)), (10, y_top))

    if game.get("hint", {}).get("word"):
        hint = game["hint"]
        screen.blit(font.render(f"HINT: {hint['word']} ({hint['count']})", 1, (255, 255, 0)), (10, y_top + 22))

    # reset game
    global RESET_BUTTON_RECT
    RESET_BUTTON_RECT = pygame.Rect(600, 8, 180, 26)
    if ROLE.endswith("spymaster"):
        pygame.draw.rect(screen, (80, 80, 120), RESET_BUTTON_RECT)
        pygame.draw.rect(screen, (150, 150, 200), RESET_BUTTON_RECT, 1)
        screen.blit(font.render("Reset game", 1, (255, 255, 255)), (RESET_BUTTON_RECT.x + 50, RESET_BUTTON_RECT.y + 4))

    # voting
    votes = game.get("votes", {})
    for card_index, card in enumerate(game.get("cards", [])):
        x = 50 + (card_index % 5) * 140
        y = CARD_START_Y + (card_index // 5) * 80
        card_rect = pygame.Rect(x, y, 120, 60)

        col = (50, 50, 50)
        if card["revealed"] or ROLE.endswith("spymaster"):
            col = {"red": (255, 100, 100), "blue": (100, 100, 255),
                   "neutral": (200, 200, 200), "bomb": (0, 0, 0)}[card["role"]]

        pygame.draw.rect(screen, col, card_rect)
        screen.blit(font.render(card["word"], 1, (0, 0, 0)), (x + 10, y + 20))

        # dot for votes
        key = str(card_index)
        if key in votes and votes[key]:
            if ROLE.startswith(game.get("turn", "")) or ROLE.endswith("spymaster"):
                turn = game.get("turn", "red")
                dot_col = (255, 100, 100) if turn == "red" else (100, 100, 255)
                screen.blit(font.render("•", 1, dot_col), (x + 100, y + 5))

    # chat
    chat_y = 520
    for chat_message in game.get("chat", [])[-6:]:
        screen.blit(font.render(chat_message, 1, (255, 255, 255)), (50, chat_y))
        chat_y += 20

    pygame.draw.rect(screen, (255, 255, 255), (50, 660, 500, 30))
    screen.blit(font.render(chat, 1, (0, 0, 0)), (55, 665))

while True:
    draw()
    pygame.display.flip()
    clock.tick(30)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass
            pygame.quit()
            exit()

        if event.type == pygame.MOUSEBUTTONDOWN:
            mouse_x, mouse_y = event.pos
            active = 660 <= mouse_y <= 690

            if client_id is not None and ROLE.endswith("spymaster"):
                if RESET_BUTTON_RECT.collidepoint(mouse_x, mouse_y):
                    send({"type": "restart"})

            if client_id is not None and ROLE.endswith("agent") and game.get("phase") == "guessing":
                for card_index in range(25):
                    x = 50 + (card_index % 5) * 140
                    y = CARD_START_Y + (card_index // 5) * 80
                    if pygame.Rect(x, y, 120, 60).collidepoint(mouse_x, mouse_y):
                        send({"type": "vote", "index": card_index})
                        break

        if event.type == pygame.KEYDOWN and active:
            if event.key == pygame.K_RETURN:
                if chat.startswith("/hint") and ROLE.endswith("spymaster"):
                    parts = chat.split()
                    if len(parts) >= 3:
                        hint_word, hint_count = parts[1], int(parts[2])
                        send({"type": "hint", "word": hint_word, "count": hint_count})
                else:
                    send({"type": "chat", "text": chat})
                chat = ""
            elif event.key == pygame.K_BACKSPACE:
                chat = chat[:-1]
            else:
                chat += event.unicode
