import socket, threading, json, random, os, sys
from typing import Dict, Set, List, Optional, Any

HOST: str = "0.0.0.0"
PORT: int = 5555

lock: threading.Lock = threading.Lock()
clients: Dict[socket.socket, str] = {}
client_ids: Dict[socket.socket, int] = {}
roles_by_id: Dict[int, str] = {}
names_by_id: Dict[int, str] = {}
next_client_id: int = 0
votes_by_index: Dict[int, Set[int]] = {}
WORDS: List[str] = []
game: Optional[Dict[str, Any]] = None


def load_words() -> List[str]:
    path: str = os.path.join(os.path.dirname(__file__), "words.txt")
    try:
        with open(path, encoding="utf-8") as f:
            words: List[str] = [line.strip().upper() for line in f if line.strip()]
    except Exception:
        print("cant read file")
        sys.exit(1)
    if len(words) < 25:
        print("words.txt must have at least 25 words")
        sys.exit(1)
    return words


def new_game() -> Dict[str, Any]:
    global votes_by_index
    first_turn: str = random.choice(["red", "blue"])
    board_words: List[str] = random.sample(WORDS, 25)

    card_roles: List[str] = (
        (["red"] * 9 if first_turn == "red" else ["red"] * 8) +
        (["blue"] * 8 if first_turn == "red" else ["blue"] * 9) +
        ["neutral"] * 7 + ["bomb"]
    )
    random.shuffle(card_roles)

    votes_by_index = {}
    return {
        "cards": [{"word": word, "role": role, "revealed": False} for word, role in zip(board_words, card_roles)],
        "turn": first_turn,
        "phase": "hint",
        "hint": {"word": "", "count": 0},
        "guesses": 0,
        "votes": {},
        "game_over": False,
        "winner": None,
        "chat": []
    }

def build_votes_for_broadcast() -> Dict[str, List[str]]:
    return {str(card_index): [roles_by_id.get(cid, "?") for cid in voter_ids]
            for card_index, voter_ids in votes_by_index.items() if voter_ids}

def build_teams_for_broadcast() -> Dict[str, List[Dict[str, Any]]]:
    red: List[Dict[str, Any]] = [{"name": names_by_id.get(cid, role), "is_spymaster": role.endswith("spymaster")}
           for cid, role in roles_by_id.items() if role.startswith("red")]
    blue: List[Dict[str, Any]] = [{"name": names_by_id.get(cid, role), "is_spymaster": role.endswith("spymaster")}
            for cid, role in roles_by_id.items() if role.startswith("blue")]
    return {"red": red, "blue": blue}

def broadcast() -> None:
    game["votes"] = build_votes_for_broadcast()
    game["teams"] = build_teams_for_broadcast()
    payload: bytes = (json.dumps(game) + "\n").encode()
    for connection in list(clients):
        try:
            connection.sendall(payload)
        except Exception:
            clients.pop(connection, None)
            client_ids.pop(connection, None)

def end_turn() -> None:
    global votes_by_index
    game["turn"] = "blue" if game["turn"]=="red" else "red"
    game["phase"] = "hint"
    game["votes"] = {}
    votes_by_index = {}
    game["hint"] = {"word":"","count":0}

def handle(connection: socket.socket) -> None:
    global next_client_id, votes_by_index
    buf: bytes = b""
    while buf.count(b"\n") < 2:
        buf += connection.recv(256)
    parts: List[str] = buf.decode().split("\n", 2)
    role: str = parts[0].strip()
    name: str = (parts[1].strip() if len(parts) > 1 else "") or role
    with lock:
        cid: int = next_client_id
        next_client_id += 1
        clients[connection] = role
        client_ids[connection] = cid
        roles_by_id[cid] = role
        names_by_id[cid] = name
        connection.sendall((str(cid) + "\n").encode())
        broadcast()

    try:
        while True:
            data: bytes = connection.recv(4096)
            if not data:
                break

            for line in data.decode().split("\n"):
                if not line:
                    continue
                message: Dict[str, Any] = json.loads(line)

                with lock:
                    if game["game_over"] and message.get("type") != "restart":
                        continue

                    cid: int = message.get("client_id", -1)
                    role: str = roles_by_id.get(cid, "")

                    if message["type"] == "hint" and role.endswith("spymaster"):
                        if role.startswith(game["turn"]):
                            game["hint"] = {"word": message["word"], "count": message["count"]}
                            game["guesses"] = message["count"] + 1
                            game["phase"] = "guessing"
                            votes_by_index = {}

                    elif message["type"] == "vote" and role.endswith("agent"):
                        if not role.startswith(game["turn"]):
                            continue
                        if game["phase"] != "guessing":
                            continue

                        card_index: int = message["index"]
                        votes_by_index.setdefault(card_index, set())
                        if cid in votes_by_index[card_index]:
                            broadcast()
                            continue
                        votes_by_index[card_index].add(cid)

                        if len(votes_by_index[card_index]) >= 2:
                            card: Dict[str, Any] = game["cards"][card_index]
                            if card["revealed"]:
                                broadcast()
                                continue
                            card["revealed"] = True
                            votes_by_index = {}

                            if card["role"] == "bomb":
                                game["game_over"] = True
                                game["winner"] = "blue" if game["turn"] == "red" else "red"
                            elif card["role"] == game["turn"]:
                                game["guesses"] -= 1
                                if game["guesses"] <= 0:
                                    end_turn()
                            else:
                                end_turn()

                    elif message["type"] == "restart":
                        game.clear()
                        game.update(new_game())

                    elif message["type"] == "chat":
                        display_name: str = names_by_id.get(cid, role)
                        game["chat"].append(f"{display_name}: {message['text']}")
                        game["chat"] = game["chat"][-30:]

                    broadcast()
    finally:
        with lock:
            cid = client_ids.pop(connection, None)
            if cid is not None:
                roles_by_id.pop(cid, None)
                names_by_id.pop(cid, None)
            clients.pop(connection, None)
            connection.close()


if __name__ == "__main__":
    WORDS = load_words()
    game = new_game()
    server_socket: socket.socket = socket.socket()
    server_socket.bind((HOST, PORT))
    server_socket.listen()
    print("Server running")
    while True:
        client_connection, _ = server_socket.accept()
        threading.Thread(target=handle, args=(client_connection,), daemon=True).start()
