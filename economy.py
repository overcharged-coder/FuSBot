# Slack port of the economy system
from collections import Counter
import datetime
import asyncio
import random
import json, os
from economy_shared import state, save_state

STOCKS = {
    "HRS":   {"name": "Horsey Corp",              "price": 120, "volatility": 0.05},
    "MOO":   {"name": "Moo Industries",           "price": 80,  "volatility": 0.04},
    "NAY":   {"name": "Neigh Technologies",       "price": 150, "volatility": 0.06},
    "UDDR":  {"name": "UdderBank",                "price": 95,  "volatility": 0.03},
    "HOOF":  {"name": "Hoof Logistics",           "price": 60,  "volatility": 0.07},
    "HAY":   {"name": "HayStack Farms",           "price": 45,  "volatility": 0.05},
    "WHNY":  {"name": "Whinny Media Group",       "price": 135, "volatility": 0.06},
    "TROT":  {"name": "Trot Motors",              "price": 200, "volatility": 0.08},
    "GALP":  {"name": "Gallop Aerospace",         "price": 260, "volatility": 0.09},
    "MINT":  {"name": "Minty Pasture Drinks",     "price": 55,  "volatility": 0.05},
    "CLVR":  {"name": "Clover Softworks",         "price": 110, "volatility": 0.045},
    "BEEF":  {"name": "BEEF Defense Systems",     "price": 165, "volatility": 0.07},
    "HNGR":  {"name": "Hungerhorse Foods",        "price": 70,  "volatility": 0.045},
    "SALT":  {"name": "Salt Lick Mining Co.",     "price": 90,  "volatility": 0.05},
    "GLUE":  {"name": "GlueTech Supplies",        "price": 30,  "volatility": 0.08},
    "PRNC":  {"name": "Prance Entertainment",     "price": 180, "volatility": 0.065},
    "STBL":  {"name": "StableCoin Ltd.",          "price": 150, "volatility": 0.015},
    "CART":  {"name": "CartWheel Robotics",       "price": 220, "volatility": 0.07},
    "MANE":  {"name": "Mane Fashion Group",       "price": 95,  "volatility": 0.055},
    "WHIP":  {"name": "WhipSpeed AI Systems",     "price": 300, "volatility": 0.09},
}

_MARKET_SENTIMENT = 0.0

# ── helpers ────────────────────────────────────────────────────────────────────

def get_pray_boost(user_id: str):
    return 1 + min(get_user(user_id).get("pray", 0) * 0.015, 0.20)


def set_cooldown(user_id: str, key: str, hours: int):
    user = get_user(user_id)
    user[key] = (datetime.datetime.utcnow() + datetime.timedelta(hours=hours)).isoformat()
    save_state()


def get_cooldown(user_id: str, key: str):
    ts = get_user(user_id).get(key)
    return datetime.datetime.fromisoformat(ts) if ts else None


def get_user(uid):
    uid = str(uid)
    if uid not in state["users"]:
        state["users"][uid] = {
            "balance": 0, "last_daily": None, "last_work": None,
            "fish_cooldown": None, "hunt_cooldown": None, "inventory": {},
            "roast_protection_until": None, "pray": 0, "last_pray": None,
            "codepad": {}, "owned_animals": [], "team": [], "stocks": {},
            "dungeon": {"active": False, "floor": 1, "hp": 100, "max_hp": 100, "energy": 3,
                        "relics": [], "curses": [], "skills": {}, "cooldowns": {}, "last_event": None, "last_log": ""},
            "raid": {"joined": False, "damage": 0, "relic_bonus": 0},
            "pvp": {"invasion_cooldown": None, "defense_bonus": 0, "offense_bonus": 0},
        }
        save_state()
    u = state["users"][uid]
    u.setdefault("balance", 0); u.setdefault("inventory", {}); u.setdefault("pray", 0)
    u.setdefault("owned_animals", []); u.setdefault("team", []); u.setdefault("stocks", {})
    d = u.setdefault("dungeon", {})
    for k in ["active","floor","hp","max_hp","energy","relics","curses","cooldowns","last_event","last_log"]:
        d.setdefault(k, False if k=="active" else 1 if k in ("floor","energy") else 100 if k=="hp" else [] if k in ("relics","curses") else {} if k=="cooldowns" else None if k=="last_event" else "")
    if d.get("max_hp") is None: d["max_hp"] = 100
    d.setdefault("skills", {})
    for k in ["power","fortune","endurance","instability","might","ward","greed","warp","instinct","focus","agility","spirit"]:
        d["skills"].setdefault(k, 0)
    u.setdefault("raid", {"joined": False, "damage": 0, "relic_bonus": 0})
    u.setdefault("pvp", {"invasion_cooldown": None, "defense_bonus": 0, "offense_bonus": 0})
    return u


async def get_balance(user_id: str) -> int:
    return get_user(user_id)["balance"]


async def update_balance(user_id: str, amount: int):
    get_user(user_id)["balance"] += amount
    save_state()


async def set_daily_timestamp(user_id: str):
    get_user(user_id)["last_daily"] = datetime.datetime.utcnow().isoformat()
    save_state()


async def get_last_daily(user_id: str):
    return get_user(user_id)["last_daily"]


# ── stock market ───────────────────────────────────────────────────────────────

def simulate_stock_prices():
    global _MARKET_SENTIMENT
    _MARKET_SENTIMENT *= 0.9
    _MARKET_SENTIMENT += random.uniform(-0.03, 0.03)
    _MARKET_SENTIMENT = max(min(_MARKET_SENTIMENT, 1.0), -1.0)
    event = None
    event_multiplier = 1.0
    roll = random.random()
    if roll < 0.004:   event = "Global Market Crash";  event_multiplier = random.uniform(0.60, 0.85); _MARKET_SENTIMENT -= random.uniform(0.3, 0.6)
    elif roll < 0.008: event = "Market Euphoria";      event_multiplier = random.uniform(1.10, 1.35); _MARKET_SENTIMENT += random.uniform(0.3, 0.5)
    elif roll < 0.015: event = "Interest Rate Scare";  event_multiplier = random.uniform(0.90, 0.97); _MARKET_SENTIMENT -= 0.2
    elif roll < 0.020: event = "Strong Growth";        event_multiplier = random.uniform(1.02, 1.08); _MARKET_SENTIMENT += 0.15
    SECTORS = {"tech":["NAY","CLVR","WHIP"],"finance":["UDDR","STBL"],"media":["WHNY","PRNC"],"transport":["HOOF","TROT","CART"],"food":["HAY","HNGR","MINT"],"industry":["BEEF","SALT","GLUE"],"luxury":["MANE","MOO"]}
    sector_sentiment = {s: _MARKET_SENTIMENT + random.uniform(-0.1, 0.1) for s in SECTORS}
    individual = {}
    for symbol in STOCKS:
        r = random.random()
        if r < 0.01: individual[symbol] = (1.25, "Breakthrough Discovery")
        elif r < 0.02: individual[symbol] = (0.85, "Supply Issues")
        elif r < 0.025: individual[symbol] = (1.40, "Major Insider Buy")
        elif r < 0.03: individual[symbol] = (0.75, "Corporate Scandal")
    for symbol, data in STOCKS.items():
        price = data["price"]
        vol = data["volatility"]
        sec = next((n for n, syms in SECTORS.items() if symbol in syms), None)
        sec_sent = sector_sentiment.get(sec, 0)
        mom = data.get("momentum", 0.0) * 0.85 + random.uniform(-0.02, 0.02)
        revert = (150 - price) / 1500
        move = random.gauss(0, vol) + (_MARKET_SENTIMENT * 0.15) + (sec_sent * 0.10) + (mom * 0.25) + revert
        move *= event_multiplier
        if symbol in individual: move *= individual[symbol][0]
        new = max(int(price * (1 + move)), 1)
        if new < price * 0.80: new = int(price * 0.80)
        data["momentum"] = mom
        data["price"] = new
    return event, individual


def _stocks_text(uid: str) -> str:
    event, news = simulate_stock_prices()
    mood = random.choice(["Bull", "Bear", "Chaos", "Chill", "On Fire"])
    lines = [f"*HORSEY STOCK EXCHANGE — {mood}*\n"]
    for s, d in STOCKS.items():
        old = d.get("last", d["price"]); new = d["price"]; d["last"] = new
        arr = "up" if new > old else ("down" if new < old else "flat")
        lines.append(f"*{s}* — {d['name']} | `{new}` horsenncy ({arr})")
    if event:
        lines.append(f"\n*Market Event:* {event}")
    for sym, (_, msg) in news.items():
        lines.append(f"*{sym}:* {msg}")
    user = get_user(uid)
    port = user.setdefault("stocks", {})
    if port:
        total = sum(q * STOCKS[s]["price"] for s, q in port.items() if s in STOCKS)
        lines.append(f"\n*Portfolio:* `{total}` horsenncy")
        for s, q in port.items():
            val = q * STOCKS.get(s, {}).get("price", 0)
            lines.append(f"• {s} × {q} (value `{val}`)")
    else:
        lines.append("\n_No stocks owned yet._")
    return "\n".join(lines)


# ── blackjack state ────────────────────────────────────────────────────────────

_bj_games: dict[str, dict] = {}


def _bj_card_val(rank: str) -> int:
    if rank == "A": return 11
    if rank in ("J","Q","K"): return 10
    return int(rank)


def _bj_hand_val(hand):
    total = sum(_bj_card_val(r) for r, _ in hand)
    aces = sum(1 for r, _ in hand if r == "A")
    while total > 21 and aces:
        total -= 10; aces -= 1
    return total


def _bj_card_art(rank, suit, hidden=False):
    if hidden:
        return ["┌─────┐","│░░░░░│","│░░░░░│","│░░░░░│","└─────┘"]
    r_l = f"{rank:<2}"[:2]; r_r = f"{rank:>2}"[-2:]
    return ["┌─────┐", f"│{r_l}   │", f"│  {suit}  │", f"│   {r_r}│", "└─────┘"]


def _bj_hand_art(hand, hide_second=False):
    if not hand: return "(no cards)"
    rows = [""] * 5
    for idx, (r, s) in enumerate(hand):
        for i, line in enumerate(_bj_card_art(r, s, hidden=(hide_second and idx == 1))):
            rows[i] += line + " "
    return "\n".join(rows)


def _bj_blocks(uid: str, game: dict, state_text: str, reveal: bool = False) -> list[dict]:
    player = game["player"]
    dealer = game["dealer"]
    d_total = _bj_hand_val(dealer)
    p_total = _bj_hand_val(player)
    d_label = f"[{d_total}]" if reveal else f"[{_bj_card_val(dealer[0][0])} + ?]"
    d_art = _bj_hand_art(dealer, hide_second=not reveal)
    p_art = _bj_hand_art(player)
    text = (
        f"*Bet:* {game['bet']} horsenncy\n\n"
        f"*Dealer* {d_label}\n```\n{d_art}\n```\n"
        f"*You* [{p_total}]\n```\n{p_art}\n```\n"
        f"{state_text}"
    )
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": text}}]
    if not reveal:
        blocks.append({"type": "actions", "elements": [
            {"type": "button", "text": {"type": "plain_text", "text": "Hit"}, "action_id": "bj_hit", "style": "primary", "value": uid},
            {"type": "button", "text": {"type": "plain_text", "text": "Stand"}, "action_id": "bj_stand", "value": uid},
        ]})
    return blocks


# ── loot tables ───────────────────────────────────────────────────────────────

_LOOT_HUNT = [
    ("Rat",10,"Common"),("Field Mouse",12,"Common"),("Sparrow",15,"Common"),("Bunny",20,"Common"),("Fox",25,"Common"),("Raccoon",18,"Common"),("Squirrel",17,"Common"),("Chicken",19,"Common"),("Duck",23,"Common"),("Cow (baby)",30,"Common"),("Stray Dog",28,"Common"),("Wild Cat",29,"Common"),("Hunting Dog",33,"Common"),("Piglet",26,"Common"),("Swan",21,"Common"),("Barn Owl",27,"Common"),("Parrot",24,"Common"),("Lizard",14,"Common"),("Small Snake",16,"Common"),("Sparrow",15,"Common"),
    ("Deer",70,"Uncommon"),("Wild Hog",65,"Uncommon"),("Turkey",55,"Uncommon"),("Mountain Goat",60,"Uncommon"),("Rooster",48,"Uncommon"),("Giant Swan",50,"Uncommon"),("Skunk",52,"Uncommon"),("Baby Croc",80,"Uncommon"),("Wolf",85,"Uncommon"),("Beaver",57,"Uncommon"),("Otter",68,"Uncommon"),("Young Tiger",75,"Uncommon"),("Wallaby",58,"Uncommon"),("Ram",72,"Uncommon"),("Eagle",88,"Uncommon"),("Flamingo",63,"Uncommon"),("Peacock",66,"Uncommon"),("Badger",71,"Uncommon"),("Giant Dodo",90,"Uncommon"),("Mini Seal",69,"Uncommon"),
    ("Bear",180,"Rare"),("Tiger",160,"Rare"),("Rhino (baby)",150,"Rare"),("Gorilla",170,"Rare"),("Buffalo",155,"Rare"),("Baby Elephant",140,"Rare"),("Elk",145,"Rare"),("Reef Shark",175,"Rare"),("Crocodile",190,"Rare"),("Giraffe",165,"Rare"),("Hippo",185,"Rare"),("Leopard",200,"Rare"),("Mutant Turkey",130,"Rare"),("Tropical Macaw",120,"Rare"),("Enraged Swan",125,"Rare"),("Alpha Badger",150,"Rare"),("Great Seal",160,"Rare"),("Demon Goat",140,"Rare"),("Mammoth Calf",180,"Rare"),("Sea Otter King",190,"Rare"),
    ("Baby Dragon",320,"Epic"),("Roc Hatchling",300,"Epic"),("Mini Wyvern",260,"Epic"),("Giant Scorpion",240,"Epic"),("Young T-Rex",350,"Epic"),("Brontosaurus Hatchling",330,"Epic"),("Titan Gorilla",310,"Epic"),("Lava Drake",340,"Epic"),("Megalodon Pup",325,"Epic"),("Dire Wolf",285,"Epic"),("Unicorn Fawn",300,"Epic"),("Forest Dragonling",290,"Epic"),("Chaos Goat",260,"Epic"),("Storm Eagle",270,"Epic"),("Demon Boar",255,"Epic"),("Shadow Panther",295,"Epic"),("Vampire Batlord",275,"Epic"),("Titan Serpent",310,"Epic"),("Elder Lizard",265,"Epic"),("Giant Elephant Spirit",300,"Epic"),
    ("Ancient Dragon",700,"Legendary"),("Celestial Wyvern",680,"Legendary"),("Thunder Roc",650,"Legendary"),("Eternal Unicorn",640,"Legendary"),("Moon Wolf",590,"Legendary"),("Galaxy Panther",620,"Legendary"),("King Scorpion",575,"Legendary"),("Elder T-Rex",750,"Legendary"),("Prime Bronto",770,"Legendary"),("Abyssal Croc",800,"Legendary"),
    ("Shadow Colossus",1500,"Mythic"),("Volcano Titan",1800,"Mythic"),("Storm Leviathan",2000,"Mythic"),("Cosmic Dragon",2500,"Mythic"),("Phoenix",3000,"Mythic"),
]
_HUNT_W = [*([35]*20),*([15]*20),*([5]*20),*([1.5]*20),*([0.35]*10),*([0.1]*5)]

_LOOT_FISH = [
    ("Common Carp",15,"Common"),("Clownfish",25,"Common"),("Shrimp",10,"Common"),("Sardine",12,"Common"),("Sunfish",14,"Common"),("Anchovy",11,"Common"),("Guppy",13,"Common"),("Minnow",10,"Common"),("Baby Squid",18,"Common"),("Small Crab",20,"Common"),("Sea Snail",17,"Common"),("Tiny Jellyfish",16,"Common"),("Bluegill",19,"Common"),("Perch",22,"Common"),("Butterflyfish",21,"Common"),("Tadpole",9,"Common"),("Krill Cluster",12,"Common"),("Baby Blowfish",18,"Common"),("Wet Fur Scrap",7,"Common"),("Seashell Fragment",8,"Common"),
    ("Bass",30,"Uncommon"),("Neon Tetra",35,"Uncommon"),("Trout",40,"Uncommon"),("Tiger Shrimp",36,"Uncommon"),("Spiked Puffer",50,"Uncommon"),("Angel Fish",42,"Uncommon"),("Golden Carp",45,"Uncommon"),("Squid",48,"Uncommon"),("Stone Crab",38,"Uncommon"),("Conch Shell",33,"Uncommon"),("Zebra Fish",37,"Uncommon"),("Salmon",55,"Uncommon"),("Swordtail",34,"Uncommon"),("Banded Puffer",47,"Uncommon"),("Pink Jellyfish",52,"Uncommon"),("Moorish Idol",41,"Uncommon"),("Catfish",49,"Uncommon"),("Hermit Crab",44,"Uncommon"),("Rainbow Fish",53,"Uncommon"),("Jumbo Shrimp",39,"Uncommon"),
    ("Octopus",90,"Rare"),("Lobster",120,"Rare"),("Lionfish",110,"Rare"),("Giant Squidling",105,"Rare"),("Balloon Puffer",95,"Rare"),("King Crab",130,"Rare"),("Electric Eel",125,"Rare"),("Baby Whale",140,"Rare"),("Dolphin Tooth",135,"Rare"),("Reef Shark",150,"Rare"),("Koi Spirit",145,"Rare"),("Ink Demon Octopus",160,"Rare"),("Steelhead Fish",115,"Rare"),("Blood Lobster",155,"Rare"),("Toxic Puffer",100,"Rare"),("Stinger Jellyfish",120,"Rare"),("Ghost Fish",143,"Rare"),("Leviathan Scale",170,"Rare"),("Royal Crab",155,"Rare"),("Echo Dolphin",165,"Rare"),
    ("Shark",250,"Epic"),("Leviathan Fragment",300,"Epic"),("Abyss Dragonfish",280,"Epic"),("Titan Octopus",260,"Epic"),("Krakenling",275,"Epic"),("Astro Puffer",245,"Epic"),("Cosmic Lobster",290,"Epic"),("Thunder Eel",255,"Epic"),("Celestial Dolphin",310,"Epic"),("Void Crab",265,"Epic"),("Crystal Koi",295,"Epic"),("Nebula Jellyfish",270,"Epic"),("Soul Shell",240,"Epic"),("Abyss Whale",300,"Epic"),("Ironjaw Shark",250,"Epic"),("Galactic Puffer",320,"Epic"),("Dimensional Octopus",305,"Epic"),("Arcane Squid",285,"Epic"),("Star Whale Cub",330,"Epic"),("Tidal Leviathan",350,"Epic"),
    ("Sea Dragon",450,"Legendary"),("Megalodon",500,"Legendary"),("Leviathan",600,"Legendary"),("Kraken",550,"Legendary"),("Ocean Serpent",650,"Legendary"),("Colossal Squid",520,"Legendary"),("Astral Dolphin",580,"Legendary"),("Mythic Lobster",490,"Legendary"),("Thunderbird Fish",470,"Legendary"),("Radiant Jellyfish",530,"Legendary"),
    ("Tidal Colossus",900,"Mythic"),("Cosmic Leviathan",1100,"Mythic"),("Phoenix Salmon",1300,"Mythic"),("Storm Serpent",1500,"Mythic"),("Eternal Flamefish",2000,"Mythic"),
]
_FISH_W = [*([35]*20),*([20]*20),*([8]*20),*([2]*20),*([0.4]*10),*([0.1]*5)]


async def setup(app):

    # ── /balance ──────────────────────────────────────────────────────────────

    @app.command("/balance")
    async def balance(ack, command, respond):
        await ack()
        uid = command["user_id"]
        text = (command.get("text") or "").strip()
        target_id = uid
        if text and text.startswith("<@"):
            import re
            m = re.search(r"<@([A-Z0-9]+)>", text)
            if m: target_id = m.group(1)
        horsenncy = await get_balance(target_id)
        await respond(text=f":banknote: <@{target_id}> has *{horsenncy} horsenncy*.")

    # ── /stocks ───────────────────────────────────────────────────────────────

    @app.command("/stocks")
    async def stocks_main(ack, command, respond):
        await ack()
        uid = command["user_id"]
        text = _stocks_text(uid)
        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": text}},
            {"type": "actions", "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "Refresh"}, "action_id": "stocks_refresh", "value": uid},
            ]},
        ]
        await respond(blocks=blocks, text="Horsey Stock Exchange")

    @app.action("stocks_refresh")
    async def stocks_refresh(ack, body, respond):
        await ack()
        uid = body["actions"][0]["value"]
        text = _stocks_text(uid)
        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": text}},
            {"type": "actions", "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "Refresh"}, "action_id": "stocks_refresh", "value": uid},
            ]},
        ]
        await respond(replace_original=True, blocks=blocks, text="Horsey Stock Exchange")

    @app.command("/stocks_buy")
    async def stocks_buy(ack, command, respond):
        await ack()
        uid = command["user_id"]
        args = (command.get("text") or "").split()
        if len(args) < 2:
            return await respond(text="Usage: `/stocks_buy SYMBOL AMOUNT`", response_type="ephemeral")
        symbol, *rest = args
        symbol = symbol.upper()
        if symbol not in STOCKS:
            return await respond(text="Unknown stock symbol.", response_type="ephemeral")
        try:
            amount = int(rest[0])
        except Exception:
            return await respond(text="Amount must be a number.", response_type="ephemeral")
        if amount <= 0:
            return await respond(text="Amount must be positive.", response_type="ephemeral")
        price = STOCKS[symbol]["price"]
        cost = price * amount
        user = get_user(uid)
        if user["balance"] < cost:
            return await respond(text=f"You need `{cost}` horsenncy but only have `{user['balance']}`.", response_type="ephemeral")
        user["balance"] -= cost
        port = user.setdefault("stocks", {})
        port[symbol] = port.get(symbol, 0) + amount
        save_state()
        await respond(text=f":white_check_mark: Bought *{amount}× {symbol}* @ `{price}` = `{cost}` horsenncy")

    @app.command("/stocks_sell")
    async def stocks_sell(ack, command, respond):
        await ack()
        uid = command["user_id"]
        args = (command.get("text") or "").split()
        if len(args) < 2:
            return await respond(text="Usage: `/stocks_sell SYMBOL AMOUNT`", response_type="ephemeral")
        symbol = args[0].upper()
        if symbol not in STOCKS:
            return await respond(text="Unknown stock.", response_type="ephemeral")
        try:
            amount = int(args[1])
        except Exception:
            return await respond(text="Amount must be a number.", response_type="ephemeral")
        user = get_user(uid)
        port = user.setdefault("stocks", {})
        if port.get(symbol, 0) < amount:
            return await respond(text="You don't own that many shares.", response_type="ephemeral")
        price = STOCKS[symbol]["price"]
        earnings = amount * price
        port[symbol] -= amount
        if port[symbol] <= 0: del port[symbol]
        user["balance"] += earnings
        save_state()
        await respond(text=f":white_check_mark: Sold *{amount}× {symbol}* @ `{price}` = `{earnings}` horsenncy earned")

    # ── /blackjack ────────────────────────────────────────────────────────────

    @app.command("/blackjack")
    async def blackjack(ack, command, client, respond):
        await ack()
        uid = command["user_id"]
        try:
            bet = int((command.get("text") or "").strip())
        except Exception:
            return await respond(text="Usage: `/blackjack <bet>`", response_type="ephemeral")
        if bet <= 0:
            return await respond(text="Bet must be positive.", response_type="ephemeral")
        balance = await get_balance(uid)
        if bet > balance:
            return await respond(text="Not enough horsenncy.", response_type="ephemeral")

        suits = ["♠","♥","♦","♣"]
        ranks = ["A","2","3","4","5","6","7","8","9","10","J","Q","K"]
        deck = [(r, s) for s in suits for r in ranks]
        random.shuffle(deck)

        def draw():
            if not deck:
                deck.extend([(r,s) for s in suits for r in ranks])
                random.shuffle(deck)
            return deck.pop()

        player = [draw(), draw()]
        dealer = [draw(), draw()]
        game = {"bet": bet, "player": player, "dealer": dealer, "deck": deck, "uid": uid}
        _bj_games[uid] = game

        blocks = _bj_blocks(uid, game, ":clock1: Choose *Hit* or *Stand*.", reveal=False)
        result = await respond(blocks=blocks, text="Blackjack", response_type="in_channel")

    @app.action("bj_hit")
    async def bj_hit(ack, body, client):
        await ack()
        actor = body["user"]["id"]
        uid = body["actions"][0]["value"]
        if actor != uid:
            return
        game = _bj_games.get(uid)
        if not game:
            return
        suits = ["♠","♥","♦","♣"]; ranks = ["A","2","3","4","5","6","7","8","9","10","J","Q","K"]
        deck = game["deck"]
        if not deck:
            deck.extend([(r,s) for s in suits for r in ranks]); random.shuffle(deck)
        game["player"].append(deck.pop())
        total = _bj_hand_val(game["player"])
        channel = body["container"]["channel_id"]
        ts = body["container"]["message_ts"]
        if total > 21:
            await update_balance(uid, -game["bet"])
            del _bj_games[uid]
            blocks = _bj_blocks(uid, game, f":skull: *BUST!* You lost *{game['bet']} horsenncy.*", reveal=True)
            await client.chat_update(channel=channel, ts=ts, blocks=blocks, text="Blackjack")
        else:
            blocks = _bj_blocks(uid, game, f":clock1: {total} — Hit or Stand?", reveal=False)
            await client.chat_update(channel=channel, ts=ts, blocks=blocks, text="Blackjack")

    @app.action("bj_stand")
    async def bj_stand(ack, body, client):
        await ack()
        actor = body["user"]["id"]
        uid = body["actions"][0]["value"]
        if actor != uid:
            return
        game = _bj_games.get(uid)
        if not game:
            return
        suits = ["♠","♥","♦","♣"]; ranks = ["A","2","3","4","5","6","7","8","9","10","J","Q","K"]
        deck = game["deck"]
        while _bj_hand_val(game["dealer"]) < 17:
            if not deck:
                deck.extend([(r,s) for s in suits for r in ranks]); random.shuffle(deck)
            game["dealer"].append(deck.pop())
        p = _bj_hand_val(game["player"])
        d = _bj_hand_val(game["dealer"])
        boost = get_pray_boost(uid)
        if d > 21 or p > d:
            winnings = int(game["bet"] * boost)
            await update_balance(uid, winnings)
            result = f":tada: *You win!* Earned *{winnings} horsenncy.*"
        elif p == d:
            result = ":handshake: *Push!* Horsenncy safe."
        else:
            await update_balance(uid, -game["bet"])
            result = f":skull: *Dealer wins.* Lost *{game['bet']} horsenncy.*"
        del _bj_games[uid]
        channel = body["container"]["channel_id"]
        ts = body["container"]["message_ts"]
        blocks = _bj_blocks(uid, game, result, reveal=True)
        await client.chat_update(channel=channel, ts=ts, blocks=blocks, text="Blackjack")

    # ── /daily ────────────────────────────────────────────────────────────────

    @app.command("/daily")
    async def daily(ack, command, respond):
        await ack()
        uid = command["user_id"]
        last = await get_last_daily(uid)
        now = datetime.datetime.utcnow()
        if last:
            diff = (now - datetime.datetime.fromisoformat(last)).total_seconds()
            if diff < 86400:
                rem = int(86400 - diff)
                return await respond(text=f":hourglass: Already claimed. Try again in *{rem//3600}h {(rem%3600)//60}m*.", response_type="ephemeral")
        reward = random.randint(100, 300)
        await update_balance(uid, reward)
        await set_daily_timestamp(uid)
        await respond(text=f":gift: *Daily Reward:* You received *{reward} horsenncy!*")

    # ── /give ─────────────────────────────────────────────────────────────────

    @app.command("/give")
    async def give(ack, command, respond):
        await ack()
        uid = command["user_id"]
        import re
        text = (command.get("text") or "").strip()
        m = re.search(r"<@([A-Z0-9]+)>", text)
        if not m:
            return await respond(text="Usage: `/give @user amount`", response_type="ephemeral")
        target_id = m.group(1)
        rest = re.sub(r"<@[A-Z0-9]+>", "", text).strip()
        try:
            amount = int(rest)
        except Exception:
            return await respond(text="Usage: `/give @user amount`", response_type="ephemeral")
        if amount <= 0:
            return await respond(text="Amount must be positive.", response_type="ephemeral")
        if uid == target_id:
            return await respond(text="Can't give to yourself.", response_type="ephemeral")
        bal = await get_balance(uid)
        if bal < amount:
            return await respond(text="Not enough horsenncy.", response_type="ephemeral")
        await update_balance(uid, -amount)
        await update_balance(target_id, amount)
        await respond(text=f":handshake: <@{uid}> gave *{amount} horsenncy* to <@{target_id}>!")

    # ── /coinflip ─────────────────────────────────────────────────────────────

    @app.command("/coinflip")
    async def coinflip(ack, command, respond):
        await ack()
        uid = command["user_id"]
        args = (command.get("text") or "").split()
        if len(args) < 2:
            return await respond(text="Usage: `/coinflip heads|tails amount`", response_type="ephemeral")
        side = args[0].lower()
        if side not in ("heads","tails"):
            return await respond(text="Pick heads or tails.", response_type="ephemeral")
        try:
            amount = int(args[1])
        except Exception:
            return await respond(text="Amount must be a number.", response_type="ephemeral")
        if amount <= 0:
            return await respond(text="Bet must be positive.", response_type="ephemeral")
        bal = await get_balance(uid)
        if bal < amount:
            return await respond(text="Not enough horsenncy.", response_type="ephemeral")
        result = random.choice(("heads","tails"))
        boost = get_pray_boost(uid)
        if result == side:
            await update_balance(uid, int(amount * boost))
            await respond(text=f":tada: Coin landed *{result}* — you won *{amount} horsenncy!*")
        else:
            await update_balance(uid, -amount)
            await respond(text=f":skull: Coin landed *{result}* — you lost *{amount} horsenncy.*")

    # ── /pray ─────────────────────────────────────────────────────────────────

    @app.command("/pray")
    async def pray(ack, command, respond):
        await ack()
        uid = command["user_id"]
        user = get_user(uid)
        now = datetime.datetime.utcnow()
        last = user.get("last_pray")
        if last:
            diff = (now - datetime.datetime.fromisoformat(last)).total_seconds()
            if diff < 600:
                rem = int(600 - diff)
                return await respond(text=f":hourglass: Wait *{rem//60}m {rem%60}s* before praying again.", response_type="ephemeral")
        user["last_pray"] = now.isoformat()
        if random.random() < 0.10:
            user["pray"] = 0; save_state()
            return await respond(text=random.choice([":skull: The Horsey god is displeased.","⚡ Your prayer backfires."]) + " Your *prayer points reset to 0.*")
        user["pray"] += 1; save_state()
        await respond(text=random.choice([":sparkles: The overlord Horsey respects your worship.",":horse: A divine neigh echoes approvingly.",":sunny: Horsey energy flows through you."]) + f" You have *{user['pray']} prayer points!*")

    # ── /leaderboard ──────────────────────────────────────────────────────────

    @app.command("/leaderboard")
    async def leaderboard(ack, command, respond):
        await ack()
        users = state.get("users", {})
        if not users:
            return await respond(text="No data yet.", response_type="ephemeral")
        top = sorted(users.items(), key=lambda x: x[1].get("balance", 0), reverse=True)[:10]
        lines = [f"*#{i+1}* — <@{uid}>: *{d.get('balance',0)} horsenncy*" for i, (uid, d) in enumerate(top)]
        await respond(text=":trophy: *Top 10 Richest*\n" + "\n".join(lines))

    # ── /team ─────────────────────────────────────────────────────────────────

    @app.command("/team")
    async def team_cmd(ack, command, respond):
        await ack()
        uid = command["user_id"]
        args = (command.get("text") or "").split()
        action = args[0].lower() if args else "list"
        user = get_user(uid)
        owned = user.setdefault("owned_animals", [])
        team = user.setdefault("team", [])
        if action == "list":
            owned_str = "\n".join(f"{i} — {a['name']} ({a['rarity']}, {a['strength']} str)" for i, a in enumerate(owned)) or "_None_"
            team_str = "\n".join(f"{i} — {t['name']} ({t['rarity']}, {t['strength']} str)" for i, t in enumerate(team)) or "_Empty_"
            return await respond(text=f"*Owned Animals:*\n{owned_str}\n\n*Team (max 8):*\n{team_str}")
        if action == "add":
            if len(args) < 2:
                return await respond(text="Specify animal index.", response_type="ephemeral")
            try: idx = int(args[1])
            except Exception: return await respond(text="Index must be a number.", response_type="ephemeral")
            if idx < 0 or idx >= len(owned):
                return await respond(text="Invalid index.", response_type="ephemeral")
            if len(team) >= 8:
                return await respond(text="Team full (8 max).", response_type="ephemeral")
            animal = owned.pop(idx); team.append(animal); save_state()
            return await respond(text=f":white_check_mark: *{animal['name']}* added to team!")
        if action == "remove":
            if len(args) < 2:
                return await respond(text="Specify team index.", response_type="ephemeral")
            try: idx = int(args[1])
            except Exception: return await respond(text="Index must be a number.", response_type="ephemeral")
            if idx < 0 or idx >= len(team):
                return await respond(text="Invalid team index.", response_type="ephemeral")
            removed = team.pop(idx); owned.append(removed); save_state()
            return await respond(text=f":x: Removed *{removed['name']}* from team.")
        await respond(text="Usage: `/team list|add <idx>|remove <idx>`", response_type="ephemeral")

    # ── /hunt ─────────────────────────────────────────────────────────────────

    @app.command("/hunt")
    async def hunt(ack, command, respond):
        await ack()
        uid = command["user_id"]
        user = get_user(uid)
        cd = get_cooldown(uid, "hunt_cooldown")
        now = datetime.datetime.utcnow()
        if cd and now < cd:
            rem = cd - now
            return await respond(text=f":deer: Wilderness too dangerous! Try in *{rem.seconds//3600}h {(rem.seconds%3600)//60}m*.", response_type="ephemeral")
        animal_name, base_reward, rarity = random.choices([(a,b,c) for a,b,c in _LOOT_HUNT], weights=_HUNT_W, k=1)[0]
        escape = min(0.75, max(0.10, base_reward / 3000))
        if random.random() < escape:
            set_cooldown(uid, "hunt_cooldown", 5)
            return await respond(text=f":dash: *The {animal_name} escaped!* Exhausted for 5 hours.")
        if random.random() < 0.05:
            return await respond(text=":dash: You missed everything. Skill issue.")
        crit = random.random() < 0.10
        reward = int(base_reward * (2 if crit else 1) * get_pray_boost(uid))
        await update_balance(uid, reward)
        user.setdefault("owned_animals", []).append({"name": animal_name, "rarity": rarity, "strength": base_reward})
        save_state()
        await respond(text=f":bow_and_arrow: You hunted a *{animal_name}* ({rarity}) and earned *{reward} horsenncy!*" + (" :boom: *CRIT!*" if crit else ""))

    # ── /fish ─────────────────────────────────────────────────────────────────

    @app.command("/fish")
    async def fish(ack, command, respond):
        await ack()
        uid = command["user_id"]
        user = get_user(uid)
        cd = get_cooldown(uid, "fish_cooldown")
        now = datetime.datetime.utcnow()
        if cd and now < cd:
            rem = cd - now
            return await respond(text=f":no_entry: Rod broken! Try in *{rem.seconds//3600}h {(rem.seconds%3600)//60}m*.", response_type="ephemeral")
        fish_name, value, rarity = random.choices([(a,b,c) for a,b,c in _LOOT_FISH], weights=_FISH_W, k=1)[0]
        break_chance = min(0.75, max(0.10, value / 2000))
        if random.random() < break_chance:
            set_cooldown(uid, "fish_cooldown", 5)
            return await respond(text=f":boom: *Rod snapped catching {fish_name}!* Can't fish for 5 hours.")
        jackpot = random.random() < 0.05
        if jackpot: value *= 5
        value = int(value * get_pray_boost(uid))
        await update_balance(uid, value)
        user.setdefault("owned_animals", []).append({"name": fish_name, "rarity": rarity, "strength": value // (5 if jackpot else 1)})
        save_state()
        await respond(text=f":fishing_pole_and_fish: You caught *{fish_name}* ({rarity}) worth *{value} horsenncy!*" + (" :tada: *JACKPOT x5!*" if jackpot else ""))

    # ── /battle ───────────────────────────────────────────────────────────────

    @app.command("/battle")
    async def battle(ack, command, respond):
        await ack()
        uid = command["user_id"]
        user = get_user(uid)
        monsters = [("Slime",30,0.70),("Bandit",50,0.60),("Goblin",80,0.55),("Wolf",75,0.58),("Skeleton",65,0.62),("Zombie",70,0.60),("Orc",85,0.54),("Giant Rat",45,0.66),("Bat Swarm",40,0.68),("Stone Imp",90,0.53),("Minotaur",140,0.45),("Forest Troll",120,0.48),("Sand Golem",110,0.50),("Ice Wraith",130,0.46),("Dark Ranger",115,0.49),("Cave Spider",95,0.52),("Demon",250,0.30),("Ogre",190,0.38),("Vampire",160,0.42),("Ancient Dragon",500,0.15),("Flame Titan",480,0.16),("Elder Lich",680,0.09),("World Eater",1500,0.05)]
        if random.random() < 0.03: monster = ("World Eater Horsey",1500,0.05)
        else: monster = random.choice(monsters)
        name, reward, win_rate = monster
        boost = get_pray_boost(uid)
        team = user.setdefault("team", [])
        team_strength = sum(a.get("strength",0) for a in team if isinstance(a, dict))
        win_rate = min(win_rate * boost * (1 + min(0.25, team_strength / 8000)), 0.98)
        crit = random.random() < 0.12
        if random.random() < win_rate:
            final = int(reward * (2 if crit else 1) * boost)
            await update_balance(uid, final)
            await respond(text=f":crossed_swords: You defeated *{name}* and earned *{final} horsenncy!*" + (" :boom: *CRITICAL STRIKE!*" if crit else ""))
        else:
            loss = random.randint(25, 80)
            await update_balance(uid, -loss)
            await respond(text=f":skull: *{name}* destroyed you. Dropped *{loss} horsenncy.*")

    # ── /crime ────────────────────────────────────────────────────────────────

    @app.command("/crime")
    async def crime(ack, command, respond):
        await ack()
        uid = command["user_id"]
        crimes = [("Pickpocketed a tourist",30),("Stole a bike",45),("Hacked an ATM",80),("Robbed a jewelry store",150),("Embezzled government funds",300),("Robbed the central bank",600),("Scammed someone online",85),("Stole cryptocurrency keys",100),("Committed tax fraud",150),("Cracked a safe",160),("Manipulated stock trades",300),("Robbed an armored truck",400),("Hijacked a crypto exchange",700),("Stole an alien artifact",1000),("Cracked an interdimensional bank",1500)]
        boost = get_pray_boost(uid)
        action, reward = random.choice(crimes)
        reward = int(reward * boost)
        if random.random() < 0.02:
            reward *= 10
            await update_balance(uid, reward)
            return await respond(text=f":money_with_wings: *LEGENDARY HEIST!* You stole *{reward} horsenncy!!!*")
        if random.random() < min(0.45 * boost, 0.90):
            await update_balance(uid, reward)
            return await respond(text=f":spy: You *{action}* and earned *{reward} horsenncy!*")
        else:
            user = get_user(uid)
            if random.random() < 0.75:
                loss = user["balance"]
                user["balance"] = 0; save_state()
                return await respond(text=f":rotating_light: Police caught you! Lost ALL *{loss} horsenncy.*")
            loss = random.randint(30, 120)
            await update_balance(uid, -loss)
            return await respond(text=f":police_car: Got caught. Lost *{loss} horsenncy.*")

    # ── /slots ────────────────────────────────────────────────────────────────

    @app.command("/slots")
    async def slots(ack, command, respond):
        await ack()
        uid = command["user_id"]
        try:
            bet = int((command.get("text") or "").strip())
        except Exception:
            return await respond(text="Usage: `/slots <bet>`", response_type="ephemeral")
        if bet <= 0:
            return await respond(text="Bet must be positive.", response_type="ephemeral")
        bal = await get_balance(uid)
        if bet > bal:
            return await respond(text="Not enough horsenncy!", response_type="ephemeral")
        icons = [":cherries:",":lemon:",":grapes:",":star:",":gem:",":fire:"]
        boost = get_pray_boost(uid)
        grid = [[random.choice(icons) for _ in range(3)] for _ in range(3)]

        def all_same(seq): return seq[0] == seq[1] == seq[2]

        reward = 0; lines_hit = []
        god_event = random.random() < 0.004
        if god_event:
            reward = int(bet * 40 * boost); lines_hit.append("*HORSEY GOD JACKPOT x40!*")
        else:
            for idx, row in enumerate(grid):
                if all_same(row):
                    sym = row[0]
                    mult = 15 if sym == ":fire:" else 10 if sym == ":gem:" else 6
                    reward = int(bet * mult * boost)
                    lines_hit.append(f"Row {idx+1} triple x{mult}!")
                    break
            if not reward:
                cols = [[grid[r][c] for r in range(3)] for c in range(3)]
                for idx, col in enumerate(cols):
                    if all_same(col):
                        sym = col[0]; mult = 8 if sym == ":fire:" else 6 if sym == ":gem:" else 4
                        reward = int(bet * mult * boost); lines_hit.append(f"Col {idx+1} x{mult}!")
                        break

        grid_str = "\n".join(" | ".join(grid[r][c] for c in range(3)) for r in range(3))
        if reward <= 0 and not god_event:
            await update_balance(uid, -bet)
            result = f":x: No wins. Lost *{bet} horsenncy.*"
        else:
            await update_balance(uid, reward)
            result = ("\n".join(lines_hit) + f"\n\n:moneybag: Earned *{reward} horsenncy!*")
        await respond(text=f":slot_machine: *Slots* — Bet: `{bet}`\n```\n{grid_str}\n```\n{result}")

    # ── /work ─────────────────────────────────────────────────────────────────

    @app.command("/work")
    async def work(ack, command, respond):
        await ack()
        uid = command["user_id"]
        user = get_user(uid)
        last = user.get("last_work")
        now = datetime.datetime.utcnow()
        if last:
            diff = (now - datetime.datetime.fromisoformat(last)).total_seconds()
            if diff < 3600:
                rem = int(3600 - diff)
                return await respond(text=f":hourglass: Wait *{rem//60}m {rem%60}s* before working again.", response_type="ephemeral")
        jobs = [("Barista",(30,60)),("Janitor",(20,50)),("Programmer",(70,150)),("Delivery Driver",(40,90)),("Business Analyst",(100,180)),("Scientist",(150,250)),("Fast Food Worker",(25,55)),("Mechanic",(40,80)),("Artist",(50,100)),("AI Engineer",(160,280)),("Astronaut Trainee",(180,300)),("Astrophysicist",(170,300)),("Quantum Engineer",(200,320))]
        job, pay_range = random.choice(jobs)
        reward = random.randint(*pay_range)
        promo = ""
        if random.random() < 0.05:
            reward *= 3; promo = " :tada: *PROMOTION BONUS!*"
        user["last_work"] = now.isoformat()
        await update_balance(uid, reward); save_state()
        await respond(text=f"{job}: Earned *{reward} horsenncy!*{promo}")

    # ── /shop / /buy / /inventory ─────────────────────────────────────────────

    @app.command("/shop")
    async def shop(ack, command, respond):
        await ack()
        items = state.get("items", {})
        if not items:
            return await respond(text=":shopping_trolley: Shop is empty. Come back later.", response_type="ephemeral")
        lines = [f"*{item['name']}* — {item['price']} horsenncy | `{item_id}`" for item_id, item in items.items()]
        await respond(text=":shopping_bags: *Shop Items*\n\n" + "\n".join(lines))

    @app.command("/buy")
    async def buy(ack, command, respond):
        await ack()
        uid = command["user_id"]
        item_id = (command.get("text") or "").strip()
        if not item_id:
            return await respond(text="Usage: `/buy <item_id>`", response_type="ephemeral")
        user = get_user(uid)
        items = state.get("items", {})
        if item_id not in items:
            return await respond(text=":x: Unknown item ID.", response_type="ephemeral")
        item = items[item_id]
        if user["balance"] < item["price"]:
            return await respond(text=":x: Too broke for that.", response_type="ephemeral")
        user["balance"] -= item["price"]
        inv = user.setdefault("inventory", {})
        inv[item_id] = inv.get(item_id, 0) + 1
        save_state()
        await respond(text=f":tada: Received *{item['name']}*! Added to inventory.")

    @app.command("/inventory")
    async def inventory(ack, command, respond):
        await ack()
        uid = command["user_id"]
        user = get_user(uid)
        inv = user.get("inventory", {})
        items_data = state.get("items", {})
        if not inv:
            return await respond(text="Your inventory is empty.", response_type="ephemeral")
        lines = [f"• *{items_data.get(iid, {}).get('name', iid)}* × {qty}" for iid, qty in inv.items() if qty > 0]
        await respond(text=":bag: *Inventory*\n" + "\n".join(lines))

    @app.command("/use")
    async def use(ack, command, respond):
        await ack()
        uid = command["user_id"]
        item_id = (command.get("text") or "").strip()
        if not item_id:
            return await respond(text="Usage: `/use <item_id>`", response_type="ephemeral")
        user = get_user(uid)
        inv = user.get("inventory", {})
        if not inv.get(item_id):
            return await respond(text=":x: You don't have that item.", response_type="ephemeral")
        items_data = state.get("items", {})
        item = items_data.get(item_id, {})
        inv[item_id] -= 1
        if inv[item_id] <= 0: del inv[item_id]
        effect = item.get("effect", "")
        save_state()
        await respond(text=f":sparkles: Used *{item.get('name', item_id)}*. {effect}")
