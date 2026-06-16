import json, os, random, time, sqlite3
from dataclasses import dataclass

COLS = list("ABCDEFGHIJ")
ROWS = list("0123456789")
GRID = 10
LETTERS = "ABCDEFGHIJ"
SHIP_SIZES = [5, 4, 3, 3, 2]
WATER = "~"; MISS = "o"; HIT = "X"; SHIP = "#"
HIT_EMOJI = ":fire:"; MISS_EMOJI = ":droplet:"; SUNK_EMOJI = ":skull:"
DB_PATH = os.path.join("data", "battleship.db")


def _idx(x, y): return y * 10 + x
def _xy(i): return i % 10, i // 10
def _inb(x, y): return 0 <= x < 10 and 0 <= y < 10
def _now(): return int(time.time())


def _ensure_db():
    os.makedirs("data", exist_ok=True)
    con = sqlite3.connect(DB_PATH); cur = con.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS games (channel_id TEXT PRIMARY KEY, state_json TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS stats (user_id TEXT PRIMARY KEY, wins INTEGER NOT NULL DEFAULT 0, losses INTEGER NOT NULL DEFAULT 0, elo REAL NOT NULL DEFAULT 1000)")
    cur.execute("CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, channel_id TEXT, p1_id TEXT, p2_id TEXT, winner_id TEXT, ts INTEGER)")
    con.commit(); con.close()


def _db(query, params=(), fetch=False, one=False):
    con = sqlite3.connect(DB_PATH); cur = con.cursor(); cur.execute(query, params); out = None
    if fetch: out = cur.fetchone() if one else cur.fetchall()
    con.commit(); con.close(); return out


def _expected(ra, rb): return 1.0 / (1.0 + 10 ** ((rb - ra) / 400.0))
def _elo_update(r, opp, score, k=32): return r + k * (score - _expected(r, opp))


@dataclass
class Slot:
    user_id: str
    is_ai: bool = False
    ai_diff: str = "normal"


class Board:
    def __init__(self, grid=None, ships=None, sunk=None):
        self.grid = grid[:] if grid else [0] * 100
        self.ships = [s[:] for s in ships] if ships else []
        self.sunk = sunk[:] if sunk else [False] * len(self.ships if ships else [])

    def render(self, reveal=False):
        out = ["   " + " ".join(COLS)]
        for y in range(GRID):
            row = [f"{ROWS[y]} "]
            for x in range(GRID):
                v = self.grid[_idx(x, y)]
                if v == 0: cell = WATER
                elif v == 1: cell = MISS
                elif v == 2: cell = HIT
                elif v == 3 and reveal: cell = SHIP
                else: cell = WATER
                row.append(cell)
            out.append(" ".join(row))
        return "```" + "\n".join(out) + "```"

    def can_place(self, x, y, d, length):
        if d == "r" and x + length > 10: return False
        if d == "d" and y + length > 10: return False
        for i in range(length):
            c = _idx(x + i, y) if d == "r" else _idx(x, y + i)
            if self.grid[c] != 0: return False
        return True

    def place(self, x, y, d, length):
        if not self.can_place(x, y, d, length): return False
        cells = []
        for i in range(length):
            c = _idx(x + i, y) if d == "r" else _idx(x, y + i)
            self.grid[c] = 3; cells.append(c)
        self.ships.append(cells); self.sunk.append(False); return True

    def apply_shot(self, x, y):
        i = _idx(x, y); v = self.grid[i]
        if v in (1, 2): return "repeat", None
        if v == 0: self.grid[i] = 1; return "miss", None
        if v == 3:
            self.grid[i] = 2; sunk_len = None
            for si, ship in enumerate(self.ships):
                if self.sunk[si]: continue
                if i in ship and all(self.grid[c] == 2 for c in ship):
                    self.sunk[si] = True; sunk_len = len(ship)
            return "hit", sunk_len
        self.grid[i] = 1; return "miss", None

    def all_destroyed(self): return 3 not in self.grid
    def public_grid(self): return [0 if v == 3 else v for v in self.grid]


class SmartAI:
    def __init__(self, diff="normal"):
        self.diff = diff; self.display_name = f"[AI:{diff}]"

    def place_ship(self, board: Board, length: int):
        opts = [(x, y, d) for y in range(10) for x in range(10) for d in ("r", "d") if board.can_place(x, y, d, length)]
        if not opts: return None
        if self.diff == "easy": return random.choice(opts)
        if self.diff in ("hard", "god"):
            best = []; best_score = -1
            for x, y, d in opts:
                score = sum(1 for i in range(length) if ((x + i + y) % 2 == 0 if d == "r" else (x + y + i) % 2 == 0))
                if score > best_score: best_score = score; best = [(x, y, d)]
                elif score == best_score: best.append((x, y, d))
            return random.choice(best)
        return random.choice(opts)

    def shoot(self, enemy_public, remaining_sizes):
        if self.diff == "easy":
            u = [i for i, v in enumerate(enemy_public) if v == 0]
            return _xy(random.choice(u)) if u else None
        hits = [i for i, v in enumerate(enemy_public) if v == 2]
        def neigh(i):
            x, y = _xy(i); return [_idx(x + dx, y + dy) for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)) if _inb(x+dx, y+dy)]
        if hits:
            oriented = []
            xs = [_xy(h)[0] for h in hits]; ys = [_xy(h)[1] for h in hits]
            if len(hits) >= 2:
                if len(set(xs)) == 1:
                    x = xs[0]
                    for y in (min(ys) - 1, max(ys) + 1):
                        if _inb(x, y):
                            j = _idx(x, y)
                            if enemy_public[j] == 0: oriented.append(j)
                if len(set(ys)) == 1:
                    y = ys[0]
                    for x in (min(xs) - 1, max(xs) + 1):
                        if _inb(x, y):
                            j = _idx(x, y)
                            if enemy_public[j] == 0: oriented.append(j)
            if oriented: return _xy(random.choice(oriented))
            cand = [n for h in hits for n in neigh(h) if enemy_public[n] == 0]
            if cand: return _xy(random.choice(cand))
        if self.diff != "god":
            u = [i for i, v in enumerate(enemy_public) if v == 0 and (i % 10 + i // 10) % 2 == 0] or [i for i, v in enumerate(enemy_public) if v == 0]
            return _xy(random.choice(u)) if u else None
        u = [i for i, v in enumerate(enemy_public) if v == 0]
        if not u: return None
        heat = {i: 0 for i in u}
        for length in remaining_sizes:
            for y in range(10):
                for x in range(10):
                    if x + length <= 10:
                        cells = [_idx(x + k, y) for k in range(length)]
                        if all(enemy_public[c] == 0 for c in cells):
                            for c in cells:
                                if c in heat: heat[c] += 1
                    if y + length <= 10:
                        cells = [_idx(x, y + k) for k in range(length)]
                        if all(enemy_public[c] == 0 for c in cells):
                            for c in cells:
                                if c in heat: heat[c] += 1
        return _xy(max(heat, key=heat.get))


_games: dict[str, dict] = {}


def _save_game(channel_id: str, game: dict):
    state = {"slots": [{"user_id": s.user_id, "is_ai": s.is_ai, "ai_diff": s.ai_diff} for s in game["slots"]],
             "boards": [{"grid": b.grid, "ships": b.ships, "sunk": b.sunk} for b in game["boards"]],
             "turn": game["turn"], "phase": game["phase"], "setup_progress": game["setup_progress"], "ts": game.get("ts")}
    _db("INSERT INTO games(channel_id, state_json) VALUES(?,?) ON CONFLICT(channel_id) DO UPDATE SET state_json=excluded.state_json",
        (channel_id, json.dumps(state)))


def _parse_coord(text: str):
    text = text.strip().upper()
    if not text or len(text) < 2: return None, None
    if text[0] in LETTERS:
        col_ch, row_ch = text[0], text[1:]
    elif text[-1] in LETTERS:
        row_ch, col_ch = text[:-1], text[-1]
    else:
        return None, None
    if col_ch not in LETTERS: return None, None
    try: y = int(row_ch)
    except ValueError: return None, None
    if not (0 <= y < 10): return None, None
    return LETTERS.index(col_ch), y


def _remaining_sizes(game: dict, enemy_idx: int):
    b = game["boards"][enemy_idx]; sizes = []
    for ship, sunk in zip(b.ships, b.sunk):
        if not sunk: sizes.append(len(ship))
    return sizes if sizes else SHIP_SIZES[:]


async def _post_game_update(client, game: dict, channel_id: str, msg: str):
    if game.get("ts"):
        try:
            result = await client.chat_update(channel=channel_id, ts=game["ts"], text=msg)
            return
        except Exception: pass
    result = await client.chat_postMessage(channel=channel_id, text=msg)
    game["ts"] = result["ts"]


async def _run_ai_turn(client, channel_id: str, game: dict):
    ai_idx = 1 if game["slots"][0].user_id == "ai" else (0 if game["slots"][1].user_id == "ai" else -1)
    if ai_idx == -1: return
    if game["turn"] != ai_idx: return
    ai: SmartAI = game["ai"]
    enemy_idx = 1 - ai_idx
    enemy_pub = game["boards"][enemy_idx].public_grid()
    sizes = _remaining_sizes(game, enemy_idx)
    shot = ai.shoot(enemy_pub, sizes)
    if not shot: return
    x, y = shot
    res, sunk_len = game["boards"][enemy_idx].apply_shot(x, y)
    cell = f"{LETTERS[x]}{y}"
    if res == "miss":
        msg = f"{MISS_EMOJI} *AI MISS* at `{cell}`\n\n" + game["boards"][enemy_idx].render(False)
        game["turn"] ^= 1
    else:
        msg = f"{HIT_EMOJI} *AI HIT* at `{cell}`"
        if sunk_len: msg += f"  {SUNK_EMOJI} *SUNK ({sunk_len})*"
        msg += "\n\n" + game["boards"][enemy_idx].render(False)
    if game["boards"][enemy_idx].all_destroyed():
        msg += "\n\n:trophy: *AI wins!*"
        await _post_game_update(client, game, channel_id, msg)
        _finish_game(channel_id, game, ai_idx)
        return
    await _post_game_update(client, game, channel_id, msg)
    _save_game(channel_id, game)
    cur_slot = game["slots"][game["turn"]]
    await client.chat_postMessage(channel=channel_id, text=f":dart: Your turn, <@{cur_slot.user_id}>! Use `/bs fire <col><row>` to fire (e.g. `/bs fire B5`)")


def _finish_game(channel_id: str, game: dict, winner_idx: int | None):
    slots = game["slots"]
    p1 = slots[0]; p2 = slots[1]
    if winner_idx is not None and not p1.is_ai and not p2.is_ai:
        w_id = slots[winner_idx].user_id; l_id = slots[1 - winner_idx].user_id
        _db("INSERT OR IGNORE INTO stats(user_id, wins, losses, elo) VALUES(?,0,0,1000)", (w_id,))
        _db("INSERT OR IGNORE INTO stats(user_id, wins, losses, elo) VALUES(?,0,0,1000)", (l_id,))
        w = _db("SELECT wins, losses, elo FROM stats WHERE user_id=?", (w_id,), fetch=True, one=True)
        l = _db("SELECT wins, losses, elo FROM stats WHERE user_id=?", (l_id,), fetch=True, one=True)
        w_elo = w[2]; l_elo = l[2]
        w_new = _elo_update(w_elo, l_elo, 1.0); l_new = _elo_update(l_elo, w_elo, 0.0)
        _db("UPDATE stats SET wins=wins+1, elo=? WHERE user_id=?", (w_new, w_id))
        _db("UPDATE stats SET losses=losses+1, elo=? WHERE user_id=?", (l_new, l_id))
        _db("INSERT INTO history(channel_id, p1_id, p2_id, winner_id, ts) VALUES(?,?,?,?,?)",
            (channel_id, p1.user_id, p2.user_id, w_id, _now()))
    _db("DELETE FROM games WHERE channel_id=?", (channel_id,))
    _games.pop(channel_id, None)


async def setup(app):
    _ensure_db()

    @app.command("/battleship")
    async def battleship_cmd(ack, command, client):
        await ack()
        uid = command["user_id"]; channel = command["channel_id"]
        text = (command.get("text") or "").strip()
        if channel in _games:
            await client.chat_postEphemeral(channel=channel, user=uid, text="a game is already running here — use `/bs_status` to see the board"); return
        import re as re_mod
        m = re_mod.search(r"<@([A-Z0-9]+)(?:\|[^>]+)?>", text)
        is_ai = False; ai_diff = "normal"; opponent_id = None
        if m:
            opponent_id = m.group(1)
            if opponent_id == uid:
                await client.chat_postEphemeral(channel=channel, user=uid, text="you can't challenge yourself"); return
        else:
            is_ai = True
            parts = text.lower().split()
            if "ai" in parts:
                idx = parts.index("ai")
                if idx + 1 < len(parts) and parts[idx + 1] in ("easy", "normal", "hard", "god"):
                    ai_diff = parts[idx + 1]
        slots = [Slot(uid, False, "normal"), Slot("ai" if is_ai else (opponent_id or ""), is_ai, ai_diff)]
        game = {"slots": slots, "boards": [Board(), Board()], "turn": 0, "phase": "setup", "setup_progress": [0, 0], "ts": None, "ai": SmartAI(ai_diff) if is_ai else None}
        _games[channel] = game
        if is_ai:
            ai = game["ai"]
            while game["setup_progress"][1] < len(SHIP_SIZES):
                length = SHIP_SIZES[game["setup_progress"][1]]
                pos = ai.place_ship(game["boards"][1], length)
                if pos: x, y, d = pos; game["boards"][1].place(x, y, d, length)
                game["setup_progress"][1] += 1
        _save_game(channel, game)
        if is_ai:
            opponent_text = f"playing vs AI ({ai_diff})"
        else:
            opponent_text = f"playing vs <@{opponent_id}>"
        await client.chat_postMessage(channel=channel, text=f":anchor: *Battleship* started! {opponent_text}\n\nBoth players: place your ships using `/bs place <col><row> <r|d>`\n*Ship sizes:* 5, 4, 3, 3, 2 — place them one at a time in that order\n\nExample: `/bs place A0 r` places next ship starting at A0 going right\n\n{uid}: you go first. Place your 5-length ship.")
        if not is_ai:
            await client.chat_postMessage(channel=channel, text=f"<@{opponent_id}>: place your 5-length ship using `/bs place <col><row> <r|d>` in this channel.")

    @app.command("/bs")
    async def bs_cmd(ack, command, client):
        await ack()
        uid = command["user_id"]; channel = command["channel_id"]
        parts = (command.get("text") or "").strip().split(None, 1)
        action = parts[0].lower() if parts else "status"
        arg = parts[1].strip() if len(parts) > 1 else ""

        if action == "place":
            game = _games.get(channel)
            if not game:
                await client.chat_postEphemeral(channel=channel, user=uid, text="no active battleship game here"); return
            if game["phase"] != "setup":
                await client.chat_postEphemeral(channel=channel, user=uid, text="game is not in setup phase"); return
            pidx = next((i for i, s in enumerate(game["slots"]) if s.user_id == uid and not s.is_ai), None)
            if pidx is None:
                await client.chat_postEphemeral(channel=channel, user=uid, text="you're not in this game"); return
            if game["setup_progress"][pidx] >= len(SHIP_SIZES):
                await client.chat_postEphemeral(channel=channel, user=uid, text="you've already placed all your ships"); return
            sub_parts = arg.split()
            if not sub_parts:
                await client.chat_postEphemeral(channel=channel, user=uid, text="usage: `/bs place <col><row> [r|d]`  e.g. `/bs place B3 r`"); return
            coord_str = sub_parts[0]; direction = (sub_parts[1].lower() if len(sub_parts) > 1 else "r")
            if direction not in ("r", "d"):
                await client.chat_postEphemeral(channel=channel, user=uid, text="direction must be `r` (horizontal) or `d` (vertical)"); return
            x, y = _parse_coord(coord_str)
            if x is None:
                await client.chat_postEphemeral(channel=channel, user=uid, text="invalid coordinate — try something like `B3` or `A0`"); return
            length = SHIP_SIZES[game["setup_progress"][pidx]]
            board = game["boards"][pidx]
            if not board.can_place(x, y, direction, length):
                await client.chat_postEphemeral(channel=channel, user=uid, text=f"can't place ship of length {length} at {LETTERS[x]}{y} going {'right' if direction == 'r' else 'down'} — try a different spot"); return
            board.place(x, y, direction, length); game["setup_progress"][pidx] += 1; placed = game["setup_progress"][pidx]
            board_str = board.render(reveal=True)
            if placed < len(SHIP_SIZES):
                await client.chat_postEphemeral(channel=channel, user=uid, text=f"placed! next ship: size `{SHIP_SIZES[placed]}`\n{board_str}")
            else:
                await client.chat_postEphemeral(channel=channel, user=uid, text=f"all ships placed!\n{board_str}")
            if all(game["setup_progress"][i] >= len(SHIP_SIZES) for i, s in enumerate(game["slots"]) if not s.is_ai):
                game["phase"] = "battle"; game["turn"] = 0; _save_game(channel, game)
                cur_slot = game["slots"][0]
                await client.chat_postMessage(channel=channel, text=f":crossed_swords: *Battle!* All ships placed.\n<@{cur_slot.user_id}>: your turn. Use `/bs fire <col><row>` to fire.")
            else:
                _save_game(channel, game)
                other_pidx = 1 - pidx
                if not game["slots"][other_pidx].is_ai and game["setup_progress"][other_pidx] < len(SHIP_SIZES):
                    next_size = SHIP_SIZES[game["setup_progress"][other_pidx]]
                    await client.chat_postMessage(channel=channel, text=f"<@{game['slots'][other_pidx].user_id}>: place your {next_size}-length ship using `/bs place <col><row> <r|d>`")

        elif action == "fire":
            game = _games.get(channel)
            if not game:
                await client.chat_postEphemeral(channel=channel, user=uid, text="no active battleship game here"); return
            if game["phase"] != "battle":
                await client.chat_postEphemeral(channel=channel, user=uid, text="game is still in setup phase — all players must place their ships first"); return
            cur_slot = game["slots"][game["turn"]]
            if cur_slot.user_id != uid:
                await client.chat_postEphemeral(channel=channel, user=uid, text=f"not your turn — it's <@{cur_slot.user_id}>'s turn"); return
            x, y = _parse_coord(arg)
            if x is None:
                await client.chat_postEphemeral(channel=channel, user=uid, text="invalid coordinate — try something like `B5` or `A0`"); return
            enemy_idx = 1 - game["turn"]; res, sunk_len = game["boards"][enemy_idx].apply_shot(x, y)
            if res == "repeat":
                await client.chat_postEphemeral(channel=channel, user=uid, text="you already fired there"); return
            cell = f"{LETTERS[x]}{y}"
            if res == "miss":
                msg = f"{MISS_EMOJI} *MISS* — <@{uid}> at `{cell}`\n\n" + game["boards"][enemy_idx].render(False)
                game["turn"] ^= 1
            else:
                msg = f"{HIT_EMOJI} *HIT* — <@{uid}> at `{cell}`"
                if sunk_len: msg += f"  {SUNK_EMOJI} *SUNK ship ({sunk_len})*"
                msg += "\n\n" + game["boards"][enemy_idx].render(False)
            if game["boards"][enemy_idx].all_destroyed():
                msg += f"\n\n:trophy: *<@{uid}> wins!*"
                await client.chat_postMessage(channel=channel, text=msg)
                _finish_game(channel, game, game["turn"]); return
            await client.chat_postMessage(channel=channel, text=msg)
            _save_game(channel, game)
            if game["slots"][game["turn"]].is_ai:
                await _run_ai_turn(client, channel, game)
            else:
                next_slot = game["slots"][game["turn"]]
                await client.chat_postMessage(channel=channel, text=f":dart: <@{next_slot.user_id}>'s turn! Use `/bs fire <col><row>`")

        elif action in ("status", ""):
            game = _games.get(channel)
            if not game:
                await client.chat_postEphemeral(channel=channel, user=uid, text="no active battleship game here"); return
            pidx = next((i for i, s in enumerate(game["slots"]) if s.user_id == uid and not s.is_ai), None)
            phase = game["phase"]
            if pidx is not None and phase == "battle":
                enemy_idx = 1 - pidx
                await client.chat_postEphemeral(channel=channel, user=uid, text=f"*Your board:*\n{game['boards'][pidx].render(reveal=True)}\n*Enemy board:*\n{game['boards'][enemy_idx].render(False)}")
            elif pidx is not None and phase == "setup":
                placed = game["setup_progress"][pidx]; remaining = SHIP_SIZES[placed:] if placed < len(SHIP_SIZES) else []
                await client.chat_postEphemeral(channel=channel, user=uid, text=f"*Your board:* (placed {placed}/{len(SHIP_SIZES)})\n{game['boards'][pidx].render(reveal=True)}\n" + (f"Ships to place: {remaining}" if remaining else "All ships placed! Waiting for opponent."))
            else:
                await client.chat_postEphemeral(channel=channel, user=uid, text=f"phase: `{phase}` | turn: `{game['turn']}`")

        elif action == "forfeit":
            game = _games.get(channel)
            if not game:
                await client.chat_postEphemeral(channel=channel, user=uid, text="no active battleship game here"); return
            pidx = next((i for i, s in enumerate(game["slots"]) if s.user_id == uid and not s.is_ai), None)
            if pidx is None:
                await client.chat_postEphemeral(channel=channel, user=uid, text="you're not in this game"); return
            winner_idx = 1 - pidx; winner_slot = game["slots"][winner_idx]
            winner_text = "AI" if winner_slot.is_ai else f"<@{winner_slot.user_id}>"
            await client.chat_postMessage(channel=channel, text=f":white_flag: <@{uid}> forfeited. {winner_text} wins!")
            _finish_game(channel, game, winner_idx)

        elif action == "resume":
            if channel in _games:
                await client.chat_postEphemeral(channel=channel, user=uid, text="a game is already active here"); return
            row = _db("SELECT state_json FROM games WHERE channel_id=?", (channel,), fetch=True, one=True)
            if not row:
                await client.chat_postEphemeral(channel=channel, user=uid, text="no saved game found here"); return
            state = json.loads(row[0])
            slots = [Slot(**d) for d in state["slots"]]
            boards = [Board(**b) for b in state["boards"]]
            ai = SmartAI(next((s.ai_diff for s in slots if s.is_ai), "normal")) if any(s.is_ai for s in slots) else None
            game = {"slots": slots, "boards": boards, "turn": state["turn"], "phase": state["phase"], "setup_progress": state["setup_progress"], "ts": state.get("ts"), "ai": ai}
            _games[channel] = game
            phase = game["phase"]; cur_slot = game["slots"][game["turn"]]
            msg = f"game resumed (phase: `{phase}`)"
            if phase == "battle":
                msg += ("\nAI is thinking..." if cur_slot.is_ai else f"\n<@{cur_slot.user_id}>'s turn — use `/bs fire <col><row>`")
            await client.chat_postMessage(channel=channel, text=msg)
            if phase == "battle" and cur_slot.is_ai:
                await _run_ai_turn(client, channel, game)

        elif action == "stats":
            import re as re_mod
            m = re_mod.search(r"<@([A-Z0-9]+)>", arg); target_id = m.group(1) if m else uid
            row = _db("SELECT wins, losses, elo FROM stats WHERE user_id=?", (target_id,), fetch=True, one=True)
            if not row:
                await client.chat_postEphemeral(channel=channel, user=uid, text=f"no stats for <@{target_id}> yet"); return
            w, l, e = row
            await client.chat_postMessage(channel=channel, text=f":bar_chart: *<@{target_id}>*\nWins: `{w}` | Losses: `{l}` | ELO: `{e:.0f}`")

        elif action == "leaderboard":
            rows = _db("SELECT user_id, wins, losses, elo FROM stats ORDER BY elo DESC LIMIT 10", fetch=True)
            if not rows:
                await client.chat_postMessage(channel=channel, text="no battleship stats yet"); return
            lines = [f"*{n}.* <@{u}> — ELO `{e:.0f}` (W{w}/L{l})" for n, (u, w, l, e) in enumerate(rows, start=1)]
            await client.chat_postMessage(channel=channel, text=":trophy: *Battleship Leaderboard*\n" + "\n".join(lines))

        else:
            await client.chat_postEphemeral(channel=channel, user=uid, text="actions: `place <coord> [r|d]` | `fire <coord>` | `status` | `forfeit` | `resume` | `stats [@user]` | `leaderboard`")
