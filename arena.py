import random
import asyncio
import datetime
from economy_shared import state, save_state
from economy import get_user, update_balance

_sessions: dict[str, dict] = {}

ASCII_SPRITES = {
    "🐺 Wolf": r"""
    /\_/\
   ( ᴥ ᴥ)
    /   \
    """,
    "🐈 Cat": r"""
    /\_/\
   ( •ᴗ•)
    /   \
    """,
    "🐶 Dog": r"""
    /  \
   (ᴗᴗ )
    / | \
    """,
    "🦊 Fox": r"""
    /\_/\
   ( ᴥ ᴥ)
   /╲  /╱
    """,
    "🐻 Bear": r"""
    /‾‾\
   (•  •)
   /__  \
    """,
    "🐢 Turtle": r"""
    ( )
   (   )
    ‾‾‾
    """,
    "🐸 Frog": r"""
    /‾‾\
   (◉  ◉)
    |__|
    """,
    "🐦 Sparrow": r"""
     /\
    (•>)
     /_\
    """,
    "🦉 Owl": r"""
    /‾‾\
   (O  O)
    \__/
    """,
    "🐍 Snake": r"""
     /^\
    ( •)
    \__~
    """,
    "🦎 Lizard": r"""
     __
    (• )
    /__≈
    """,
    "🐇 Rabbit": r"""
    |\  |
   (  • )
    \__/
    """,
    "🦔 Hedgehog": r"""
    /###\
   (•   )
    \###/
    """,
    "🐿 Squirrel": r"""
     /\
    (• •)
   //  \\
    """,
    "🦦 Sea Otter King": r"""
     (\_/)
    ( •ᴥ)
    /︶♛
    """,
    "🐉 Baby Dragon": r"""
    /\___/\
   ( •🔥• )
    / /\ \
    """,
    "🦅 Eagle": r"""
     /\___
    (•>  )
     /|
    """,
    "🐊 Crocodile": r"""
    _____
   ( •  )
   /__  )
      ‾‾
    """,
    "🦒 Giraffe": r"""
     /‾|
    (• )
     |||
    """,
    "🦛 Hippo": r"""
    (••)
   (____)
     ||
    """,
    "🐆 Leopard": r"""
    /\_/\
   (•꘎•)
   /• •\
    """,
    "🦃 Mutant Turkey": r"""
   (◉ᴗ◉)
   <▒▒▒▒>
     ||
    """,
    "🦄 Unicorn Fawn": r"""
    /\_/\
   (•ᴗ•)>
    /  \
    """,
    "🐉 Ancient Dragon": r"""
    /\____/\
   ( •🔥•  )
    / /\   \
    """,
    "🐺 Dire Wolf": r"""
    /\_/\
   ( ⚈ɷ⚈)
    /  \
    """,
    "🌑 Shadow Colossus": r"""
     ███
    (◣_◢)
    /███\
    """,
    "🌌 Cosmic Dragon": r"""
    /\___/\
   ( ✦🔥✦ )
    / ✦\
    """,
    "🔥 Phoenix": r"""
     /\
    (🔥)
    /╱\
    """,
    "🦄 Eternal Unicorn": r"""
    /\_/\
   (•ᴗ•)✨
    /   \
    """,
    "🐺 Moon Wolf": r"""
    /\_/\
   ( •ᴥ)🌙
    /   \
    """,
    "🦅 Thunder Roc": r"""
     /\____
    (•>⚡ )
     /|
    """,
}

EVOLUTIONS = {
    "🐺 Wolf": "🐺 Dire Wolf",
    "🐺 Dire Wolf": "🐺 Moon Wolf",
    "🐉 Baby Dragon": "🐉 Ancient Dragon",
    "🦅 Eagle": "🦅 Thunder Roc",
    "🦄 Unicorn Fawn": "🦄 Eternal Unicorn",
    "🐻 Bear": "🌑 Shadow Colossus",
    "🔥 Phoenix": "🔥 Phoenix",
}

ARENA_MUTATORS = [
    ("Bloodsport", "All damage increased, healing reduced.", 1.25, 0.7),
    ("Iron Wall", "Defense and shields stronger.", 0.9, 1.3),
    ("Arcane Storm", "Crit rate higher, status effects stronger.", 1.1, 1.0),
    ("Chaotic Whirl", "Random stat swings each round.", 1.0, 1.0),
    ("Blessed Grounds", "Healing stronger, damage slightly lower.", 0.9, 1.25),
]

TYPE_CHART = {
    ("fire","beast"):1.3, ("fire","mystic"):1.1, ("fire","water"):0.7,
    ("water","fire"):1.4, ("water","earth"):1.2, ("water","air"):0.8,
    ("air","beast"):1.2, ("air","earth"):1.3, ("air","mystic"):1.1,
    ("earth","fire"):1.2, ("earth","air"):0.8, ("earth","beast"):1.1,
    ("dark","mystic"):1.4, ("dark","beast"):1.1, ("dark","fire"):1.1,
    ("mystic","dark"):1.3, ("mystic","beast"):1.1,
}
ROLES = ["tank","striker","support","healer","trickster"]
RARITIES = [("Common",1.0),("Uncommon",1.10),("Rare",1.25),("Epic",1.45),("Legendary",1.75)]
ENVIRONMENTS = [("Blazing Sun","fire","water"),("Raging Storm","air","earth"),("Tidal Surge","water","fire"),("Eclipse","dark","mystic")]
MOVE_SETS = {
    "beast": [{"name":"Savage Pounce","element":"beast","kind":"attack","power":1.0,"accuracy":0.96,"status":None,"status_chance":0.0},
              {"name":"Rending Claws","element":"beast","kind":"attack","power":1.20,"accuracy":0.9,"status":"bleed","status_chance":0.35},
              {"name":"War Howl","element":"beast","kind":"buff","power":0.0,"accuracy":1.0,"status":"atk_up","status_chance":1.0}],
    "fire": [{"name":"Flame Burst","element":"fire","kind":"attack","power":1.10,"accuracy":0.93,"status":"burn","status_chance":0.4},
             {"name":"Inferno Claw","element":"fire","kind":"attack","power":1.30,"accuracy":0.85,"status":"burn","status_chance":0.5},
             {"name":"Blazing Aura","element":"fire","kind":"buff","power":0.0,"accuracy":1.0,"status":"atk_up","status_chance":1.0}],
    "water": [{"name":"Aqua Slash","element":"water","kind":"attack","power":1.05,"accuracy":0.97,"status":None,"status_chance":0.0},
              {"name":"Tidal Crash","element":"water","kind":"attack","power":1.20,"accuracy":0.9,"status":"stun","status_chance":0.2},
              {"name":"Restorative Tide","element":"water","kind":"buff","power":0.0,"accuracy":1.0,"status":"regen","status_chance":1.0}],
    "air": [{"name":"Sky Cutter","element":"air","kind":"attack","power":1.05,"accuracy":0.96,"status":None,"status_chance":0.0},
            {"name":"Storm Dive","element":"air","kind":"attack","power":1.20,"accuracy":0.88,"status":"stun","status_chance":0.3},
            {"name":"Tailwind Rush","element":"air","kind":"buff","power":0.0,"accuracy":1.0,"status":"spd_up","status_chance":1.0}],
    "earth": [{"name":"Quake Slam","element":"earth","kind":"attack","power":1.15,"accuracy":0.9,"status":"stun","status_chance":0.2},
              {"name":"Stone Crush","element":"earth","kind":"attack","power":1.30,"accuracy":0.85,"status":None,"status_chance":0.0},
              {"name":"Iron Hide","element":"earth","kind":"buff","power":0.0,"accuracy":1.0,"status":"def_up","status_chance":1.0}],
    "dark": [{"name":"Night Fang","element":"dark","kind":"attack","power":1.1,"accuracy":0.93,"status":"bleed","status_chance":0.4},
             {"name":"Shadow Rend","element":"dark","kind":"attack","power":1.25,"accuracy":0.86,"status":"poison","status_chance":0.45},
             {"name":"Abyssal Curse","element":"dark","kind":"attack","power":0.95,"accuracy":0.9,"status":"poison","status_chance":0.65}],
    "mystic": [{"name":"Radiant Horn","element":"mystic","kind":"attack","power":1.1,"accuracy":0.95,"status":None,"status_chance":0.0},
               {"name":"Starfall Lance","element":"mystic","kind":"attack","power":1.25,"accuracy":0.9,"status":"stun","status_chance":0.25},
               {"name":"Celestial Grace","element":"mystic","kind":"buff","power":0.0,"accuracy":1.0,"status":"regen","status_chance":1.0}],
}


def _infer_element(name):
    n = name.lower()
    if any(k in n for k in ["dragon","wyvern","drake","phoenix","lava","volcano"]): return "fire"
    if any(k in n for k in ["shark","seal","otter","crocodile","hippo","reef","megalodon","leviathan"]): return "water"
    if any(k in n for k in ["eagle","sparrow","owl","roc","parrot","macaw","swan","duck","flamingo","peacock"]): return "air"
    if any(k in n for k in ["rhino","mammoth","elk","buffalo","boar","hog","ram","goat","titan","colossus"]): return "earth"
    if any(k in n for k in ["shadow","demon","abyss","vampire","moon","king scorpion","scorpion"]): return "dark"
    if any(k in n for k in ["unicorn","spirit","ancient","celestial","eternal","prime","cosmic","galaxy","phoenix"]): return "mystic"
    return "beast"


def _assign_role_rarity(name):
    base = sum(ord(c) for c in name.lower())
    role = ROLES[base % len(ROLES)]; rarity_idx = (base // 5) % len(RARITIES)
    rarity, mult = RARITIES[rarity_idx]
    return role, rarity, mult


def _assign_ability(name, element, role):
    nl = name.lower()
    if "phoenix" in nl: return "rebirth", "Rebirth"
    if "wolf" in nl or "dire" in nl or "moon wolf" in nl: return "pack_hunter", "Pack Hunter"
    if "goat" in nl or "demon" in nl or "chaos" in nl: return "berserker", "Berserker"
    if "unicorn" in nl: return "aura_heal", "Blessing Aura"
    if "dragon" in nl or "wyvern" in nl or "drake" in nl: return "scales", "Draconic Scales"
    if "titan" in nl or "colossus" in nl or "leviathan" in nl: return "bulwark", "Titanic Bulwark"
    if role == "healer": return "healer", "Mender's Grace"
    if role == "support": return "speed_aura", "Tailwind Banner"
    if role == "tank": return "guard", "Guardian's Oath"
    if role == "trickster": return "hex", "Chaotic Hex"
    if role == "striker": return "finisher", "Executioner"
    return "none", "None"


def _hp_bar(hp, max_hp, width=16):
    max_hp = max(1, int(max_hp)); hp = max(0, int(hp)); ratio = hp / max_hp
    filled = int(ratio * width)
    fc = "█" if ratio > 0.66 else ("▓" if ratio > 0.33 else "▒")
    return f"{fc*filled}{'·'*(width-filled)} {hp}/{max_hp}"


def _build_team_stats(team, arena, world):
    passives = arena.get("passives", {}); evolved_map = arena.get("evolved", {})
    power_mult = 1.0 + passives.get("power_boost", 0.0)
    speed_mult = 1.0 + passives.get("speed_boost", 0.0)
    def_mult = 1.0 + passives.get("def_boost", 0.0)
    crit_bonus = passives.get("crit_boost", 0.0)
    chaos_factor = 1.0 + world["chaos"] * 0.12
    stats = []
    for unit in team:
        raw_name = unit if isinstance(unit, str) else unit.get("name", str(unit))
        name = evolved_map.get(raw_name, raw_name)
        bp = random.randint(40, 90); bs = random.randint(20, 65); bd = random.randint(15, 45)
        bh = bp * 2 + random.randint(10, 40)
        role, rarity, rarity_mult = _assign_role_rarity(name); element = _infer_element(name)
        ability_id, ability_name = _assign_ability(name, element, role)
        if role == "tank": bh *= 1.25; bd *= 1.25; bs *= 0.85
        elif role == "striker": bp *= 1.25; bs *= 1.10; bd *= 0.9
        elif role == "support": bs *= 1.15; bd *= 1.05
        elif role == "healer": bh *= 1.10; bd *= 1.10; bp *= 0.9
        elif role == "trickster": bs *= 1.2; bd *= 0.9
        bh = int(bh * rarity_mult * chaos_factor); bp = int(bp * rarity_mult * chaos_factor * power_mult)
        bs = int(bs * rarity_mult * speed_mult); bd = int(bd * rarity_mult * def_mult)
        crit = min(0.6, random.uniform(0.05, 0.17) + crit_bonus + (0.05 if role == "striker" else 0))
        stats.append({"name":name,"element":element,"role":role,"rarity":rarity,"ability_id":ability_id,"ability_name":ability_name,
                       "hp":bh,"max_hp":bh,"power":bp,"speed":bs,"def":bd,"crit":crit,"status_resist":random.uniform(0.0, 0.20)+(0.1 if role=="tank" else 0),
                       "status":None,"status_timer":0,"atk_mod":1.0,"def_mod":1.0,"spd_mod":1.0,"shield":0,
                       "has_rebirthed":False,"ult_charge":0,"ult_ready":False,"clutch":rarity in ("Common","Uncommon"),"clutch_used":False})
    return stats


def _analyze_synergies(team):
    elements = {}; roles = {}; rarities = {}
    for u in team:
        elements[u["element"]] = elements.get(u["element"], 0) + 1
        roles[u["role"]] = roles.get(u["role"], 0) + 1
        rarities[u["rarity"]] = rarities.get(u["rarity"], 0) + 1
    bonuses = []
    for el, cnt in elements.items():
        if cnt >= 3: bonuses.append(("elem", el, cnt))
    for rl, cnt in roles.items():
        if cnt >= 3: bonuses.append(("role", rl, cnt))
    for r, cnt in rarities.items():
        if r in ("Epic","Legendary") and cnt >= 2: bonuses.append(("rarity", r, cnt))
    return bonuses


def _apply_synergies_to_team(team, synergies, log_prefix):
    lines = []
    for kind, val, cnt in synergies:
        if kind == "elem":
            if val == "fire":
                for u in team:
                    if u["element"] == "fire": u["power"] = int(u["power"] * 1.10)
                lines.append(f"{log_prefix} Fire pack: fire power up.")
            elif val == "water":
                for u in team:
                    if u["element"] == "water": u["max_hp"] = int(u["max_hp"] * 1.08); u["hp"] = u["max_hp"]
                lines.append(f"{log_prefix} Water flow: water HP up.")
            elif val == "air":
                for u in team:
                    if u["element"] == "air": u["speed"] = int(u["speed"] * 1.12)
                lines.append(f"{log_prefix} Air current: air speed up.")
            elif val == "earth":
                for u in team:
                    if u["element"] == "earth": u["def"] = int(u["def"] * 1.12)
                lines.append(f"{log_prefix} Earth wall: earth defense up.")
            elif val == "dark":
                for u in team:
                    if u["element"] == "dark": u["crit"] = min(0.6, u["crit"] + 0.06)
                lines.append(f"{log_prefix} Dark pact: dark crit up.")
            elif val == "mystic":
                for u in team:
                    if u["element"] == "mystic": u["status_resist"] += 0.1
                lines.append(f"{log_prefix} Mystic veil: mystic resist up.")
        elif kind == "role":
            if val == "tank":
                for u in team:
                    if u["role"] == "tank": u["shield"] += int(u["max_hp"] * 0.12)
                lines.append(f"{log_prefix} Tank line: bonus shields.")
            elif val == "striker":
                for u in team:
                    if u["role"] == "striker": u["atk_mod"] *= 1.10
                lines.append(f"{log_prefix} Striker squad: attack raised.")
            elif val == "support":
                for u in team:
                    if u["role"] == "support": u["spd_mod"] *= 1.10
                lines.append(f"{log_prefix} Support chorus: speed up.")
            elif val == "healer":
                for u in team:
                    if u["role"] == "healer": u["def_mod"] *= 1.08
                lines.append(f"{log_prefix} Healer circle: safer heals.")
            elif val == "trickster":
                for u in team:
                    if u["role"] == "trickster": u["crit"] = min(0.6, u["crit"] + 0.05)
                lines.append(f"{log_prefix} Trickster band: more crits.")
        elif kind == "rarity":
            if val == "Epic":
                for u in team:
                    if u["rarity"] == "Epic": u["max_hp"] = int(u["max_hp"] * 1.06); u["hp"] = u["max_hp"]
                lines.append(f"{log_prefix} Epic bond: HP up.")
            elif val == "Legendary":
                for u in team:
                    if u["rarity"] == "Legendary": u["atk_mod"] *= 1.08; u["def_mod"] *= 1.08
                lines.append(f"{log_prefix} Legendary bond: all stats up.")
    return lines


def _type_multiplier(move_elem, target_elem, current_env, mutator):
    base = TYPE_CHART.get((move_elem, target_elem), 1.0) if move_elem and target_elem else 1.0
    env_name, env_boost, env_nerf = current_env
    if move_elem == env_boost: base *= 1.15
    elif move_elem == env_nerf: base *= 0.9
    if mutator and mutator[0] == "Bloodsport": base *= 1.1
    elif mutator and mutator[0] == "Blessed Grounds": base *= 0.95
    return base


def _pick_target(team):
    alive = [u for u in team if u["hp"] > 0]
    if not alive: return None
    return min(alive, key=lambda u: u["hp"]) if random.random() < 0.55 else max(alive, key=lambda u: u["power"])


def _pick_ultimate_name(unit):
    el = unit["element"]
    if el == "fire": return "Inferno Collapse"
    if el == "water": return "Tidal Rebirth"
    if el == "air": return "Tempest Assault"
    if el == "earth": return "Worldbreaker Slam"
    if el == "dark": return "Eclipse Devour"
    if el == "mystic": return "Celestial Judgment"
    return "Primal Frenzy"


def _perform_ultimate(unit, allies, enemies, log, last_ult_holder):
    el = unit["element"]; title = _pick_ultimate_name(unit)
    log.append(f"{unit['name']} unleashes {title}!")
    if el == "fire":
        for e in enemies:
            if e["hp"] <= 0: continue
            dmg = max(1, int(e["max_hp"] * 0.2)); e["hp"] -= dmg; e["status"] = "burn"; e["status_timer"] = 3
        log.append("Flames engulf the enemy team!")
    elif el == "water":
        for a in allies:
            if a["hp"] <= 0: continue
            heal = max(1, int(a["max_hp"] * 0.18)); a["hp"] = min(a["max_hp"], a["hp"] + heal)
        log.append("A tidal wave restores your team!")
    elif el == "air":
        for a in allies: a["spd_mod"] *= 1.3; a["atk_mod"] *= 1.1
        log.append("Hurricane winds accelerate your squad!")
    elif el == "earth":
        for a in allies: a["shield"] += int(a["max_hp"] * 0.25)
        log.append("The ground rises to shield your fighters!")
    elif el == "dark":
        for e in enemies:
            if e["hp"] <= 0: continue
            dmg = max(1, int(e["max_hp"] * 0.16)); e["hp"] -= dmg; e["status"] = "poison"; e["status_timer"] = 3
        log.append("Shadows devour enemy vitality!")
    elif el == "mystic":
        target = next((e for e in enemies if e["hp"] > 0), None)
        if target:
            dmg = max(1, int(target["max_hp"] * 0.35)); target["hp"] -= dmg
            log.append(f"Starfire smites {target['name']} for {dmg} damage!")
    else:
        for e in enemies:
            if e["hp"] <= 0: continue
            dmg = max(1, int(e["max_hp"] * 0.15)); e["hp"] -= dmg
        log.append("Primal rage tears through the enemy!")
    unit["ult_charge"] = 0; unit["ult_ready"] = False
    last_ult_holder[0] = f"{unit['name']} used {title}"


def _try_rebirth(unit, log):
    if unit["ability_id"] != "rebirth" or unit.get("has_rebirthed"): return False
    unit["has_rebirthed"] = True; unit["hp"] = max(1, int(unit["max_hp"] * 0.4))
    log.append(f"{unit['name']} is engulfed in flames and rises again!"); return True


def _apply_on_damage_taken(defender, attacker, dmg, log):
    aid = defender["ability_id"]
    if defender.get("clutch") and not defender.get("clutch_used") and defender["hp"] / defender["max_hp"] < 0.2:
        defender["atk_mod"] *= 1.15; defender["spd_mod"] *= 1.20; defender["crit"] = min(0.6, defender["crit"] + 0.15)
        defender["clutch_used"] = True; log.append(f"{defender['name']}'s survival instinct triggers!")
    if aid == "berserker" and defender["hp"] / max(1, defender["max_hp"]) < 0.4:
        defender["atk_mod"] *= 1.10; log.append(f"{defender['name']}'s Berserker rage boosts attack!")
    if aid == "hex" and random.random() < 0.2 and attacker["hp"] > 0:
        st = random.choice(["bleed","poison","stun"]); attacker["status"] = st; attacker["status_timer"] = 2
        log.append(f"{defender['name']}'s chaotic hex curses {attacker['name']}!")
    if aid == "bulwark" and not defender.get("bulwark_used") and dmg > defender["max_hp"] * 0.35:
        defender["bulwark_used"] = True; shield = int(defender["max_hp"] * 0.25); defender["shield"] += shield
        log.append(f"{defender['name']}'s Titanic Bulwark conjures a shield!")


def _apply_on_attack(attacker, defender, dmg, log):
    aid = attacker["ability_id"]
    if aid == "pack_hunter" and random.random() < 0.25:
        log.append(f"{attacker['name']} tears in with pack fury!")
    if aid == "finisher" and defender["hp"] / max(1, defender["max_hp"]) < 0.35 and random.random() < 0.3:
        extra = max(1, int(defender["max_hp"] * 0.08)); defender["hp"] -= extra
        log.append(f"{attacker['name']}'s Executioner strike tears extra {extra} HP!")
    if aid == "scales" and random.random() < 0.2:
        attacker["def_mod"] *= 1.12; log.append(f"{attacker['name']}'s scales harden!")


def _apply_round_end(pteam, oteam, log, mutator):
    for team in (pteam, oteam):
        alive = [u for u in team if u["hp"] > 0]
        if not alive: continue
        healers = [u for u in alive if u["ability_id"] in ("healer","aura_heal")]
        if healers:
            healer = random.choice(healers); target = min(alive, key=lambda u: u["hp"] / u["max_hp"])
            if target["hp"] > 0:
                base_pct = 0.05 if healer["ability_id"] == "healer" else 0.08
                if mutator and mutator[0] == "Blessed Grounds": base_pct *= 1.3
                if mutator and mutator[0] == "Bloodsport": base_pct *= 0.7
                amount = max(1, int(target["max_hp"] * base_pct)); target["hp"] = min(target["max_hp"], target["hp"] + amount)
                log.append(f"{healer['name']}'s aura mends {target['name']} (+{amount} HP)!")
        for u in alive:
            if u["ability_id"] == "speed_aura":
                for ally in alive: ally["spd_mod"] *= 1.02


def simulate_battle(pteam, oteam, world, current_env):
    log = []; mut = random.choice(ARENA_MUTATORS); world["mutator"] = mut
    p_sy = _analyze_synergies(pteam); o_sy = _analyze_synergies(oteam)
    log.extend(_apply_synergies_to_team(pteam, p_sy, "Your"))
    log.extend(_apply_synergies_to_team(oteam, o_sy, "Enemy"))
    for team in (pteam, oteam):
        for u in team:
            if u["ability_id"] in ("guard","bulwark"):
                shield = int(u["max_hp"] * 0.15); u["shield"] += shield
                log.append(f"{u['name']}'s {u['ability_name']} grants a {shield} HP shield!")
    last_ult = [None]; round_no = 1
    while True:
        if all(u["hp"] <= 0 for u in pteam): return "loss", log, mut, last_ult[0]
        if all(u["hp"] <= 0 for u in oteam): return "win", log, mut, last_ult[0]
        if round_no > 60: return "draw", log, mut, last_ult[0]
        acting = sorted([(u["speed"] * u["spd_mod"] + random.uniform(0,5), u) for u in pteam + oteam if u["hp"] > 0], key=lambda x: x[0], reverse=True)
        for _, unit in acting:
            if unit["hp"] <= 0: continue
            side = "p" if unit in pteam else "o"
            allies = pteam if side == "p" else oteam; enemies = oteam if side == "p" else pteam
            if all(u["hp"] <= 0 for u in enemies): break
            target = _pick_target(enemies)
            if not target: continue
            if unit["ult_ready"]:
                _perform_ultimate(unit, allies, enemies, log, last_ult); continue
            moves = MOVE_SETS.get(unit.get("element","beast"), MOVE_SETS["beast"])
            move = random.choice(moves)
            if unit["status"] == "stun":
                log.append(f"Round {round_no}: {unit['name']} is stunned!"); unit["status"] = None; unit["status_timer"] = 0
                unit["ult_charge"] = min(100, unit["ult_charge"] + 5)
                if unit["ult_charge"] >= 100: unit["ult_ready"] = True
                continue
            if move["kind"] == "buff":
                if move["status"] == "atk_up": unit["atk_mod"] *= 1.25; log.append(f"{unit['name']}'s power rose!")
                elif move["status"] == "def_up": unit["def_mod"] *= 1.25; log.append(f"{unit['name']}'s defense rose!")
                elif move["status"] == "spd_up": unit["spd_mod"] *= 1.25; log.append(f"{unit['name']}'s speed rose!")
                elif move["status"] == "regen": unit["status"] = "regen"; unit["status_timer"] = 3; log.append(f"{unit['name']} gains regen!")
                unit["ult_charge"] = min(100, unit["ult_charge"] + 15)
                if unit["ult_charge"] >= 100: unit["ult_ready"] = True
                continue
            if random.random() > move["accuracy"]:
                log.append(f"Round {round_no}: {unit['name']} used {move['name']} but missed!"); unit["ult_charge"] = min(100, unit["ult_charge"] + 10)
                if unit["ult_charge"] >= 100: unit["ult_ready"] = True
                continue
            hits = 2 if ("Claw" in move["name"] or "Fang" in move["name"]) and random.random() < 0.2 else 1
            total_dmg = 0
            txt = [f"Round {round_no}: {unit['name']} used {move['name']}!"]
            for _ in range(hits):
                base = max(5, unit["power"] * unit["atk_mod"] - target["def"] * target["def_mod"])
                crit = False
                if random.random() < unit["crit"]: crit = True; base *= 1.7
                if random.random() < 0.3: unit["atk_mod"] *= 1.12
                stab = 1.2 if move["element"] == unit["element"] else 1.0
                type_mult = _type_multiplier(move["element"], target["element"], current_env, world.get("mutator"))
                dmg = int(base * move["power"] * stab * type_mult * random.uniform(0.85, 1.0))
                if world.get("mutator") and world["mutator"][0] == "Bloodsport": dmg = int(dmg * 1.15)
                if world.get("mutator") and world["mutator"][0] == "Iron Wall": dmg = int(dmg * 0.9)
                dmg = max(1, dmg)
                if target["shield"] > 0:
                    absorbed = min(target["shield"], dmg); target["shield"] -= absorbed; dmg -= absorbed
                    if absorbed > 0: txt.append(f"{target['name']}'s shield absorbs {absorbed}!")
                target["hp"] -= dmg; total_dmg += dmg
                eff_text = "Super effective!" if type_mult > 1.25 else ("Not very effective..." if type_mult < 0.9 else "")
                txt.append(f"Hit for {dmg}." + (" CRIT!" if crit else "") + (" " + eff_text if eff_text else ""))
                if target["hp"] <= 0:
                    if not _try_rebirth(target, txt): target["hp"] = 0; txt.append(f"{target['name']} has fallen!")
                    break
            if unit["role"] == "striker" and total_dmg > 0 and unit["hp"] > 0:
                ls = int(total_dmg * 0.1); unit["hp"] = min(unit["max_hp"], unit["hp"] + ls); txt.append(f"{unit['name']} siphons {ls} HP!")
            if move["status"] in ("burn","poison","bleed","stun") and target["hp"] > 0:
                smult = 1.25 if (world.get("mutator") and world["mutator"][0] == "Arcane Storm") else 1.0
                if random.random() < move["status_chance"] * (1.0 - target["status_resist"]) * smult:
                    target["status"] = move["status"]; target["status_timer"] = {"burn":3,"poison":4,"bleed":3,"stun":1}[move["status"]]
                    txt.append(f"{target['name']} was {move['status']}ed!")
            _apply_on_attack(unit, target, total_dmg, txt); _apply_on_damage_taken(target, unit, total_dmg, txt)
            unit["ult_charge"] = min(100, unit["ult_charge"] + 18)
            if unit["ult_charge"] >= 100: unit["ult_ready"] = True
            target["ult_charge"] = min(100, target.get("ult_charge", 0) + 12)
            if target["ult_charge"] >= 100: target["ult_ready"] = True
            log.extend(txt)
            if all(u["hp"] <= 0 for u in pteam): return "loss", log, mut, last_ult[0]
            if all(u["hp"] <= 0 for u in oteam): return "win", log, mut, last_ult[0]
        mut_now = world.get("mutator")
        for team in (pteam, oteam):
            for unit in team:
                if unit["hp"] <= 0: continue
                if unit["status"] in ("burn","poison","bleed","regen"):
                    if unit["status"] == "burn":
                        dot = max(1, int(unit["max_hp"] * 0.06)); unit["hp"] -= dot; log.append(f"{unit['name']} burned ({dot}).")
                    elif unit["status"] == "poison":
                        dot = max(1, int(unit["max_hp"] * 0.07)); unit["hp"] -= dot; log.append(f"{unit['name']} poisoned ({dot}).")
                    elif unit["status"] == "bleed":
                        dot = max(1, int(unit["max_hp"] * 0.08)); unit["hp"] -= dot; log.append(f"{unit['name']} bleeding ({dot}).")
                    elif unit["status"] == "regen":
                        heal = max(1, int(unit["max_hp"] * (0.06 * (1.3 if mut_now and mut_now[0] == "Blessed Grounds" else 1.0))))
                        unit["hp"] = min(unit["max_hp"], unit["hp"] + heal); log.append(f"{unit['name']} regains {heal} HP!")
                    unit["status_timer"] -= 1
                    if unit["status_timer"] <= 0: unit["status"] = None
        if mut_now and mut_now[0] == "Chaotic Whirl":
            for team in (pteam, oteam):
                for u in team:
                    if u["hp"] <= 0: continue
                    u["atk_mod"] *= random.uniform(0.85, 1.20); u["def_mod"] *= random.uniform(0.85, 1.20); u["spd_mod"] *= random.uniform(0.85, 1.20)
                    if random.random() < 0.1: u["ult_charge"] = min(100, u["ult_charge"] + random.randint(20, 40))
                    if random.random() < 0.15: u["status"] = random.choice(["burn","poison","bleed","stun",None]); u["status_timer"] = random.randint(1,3) if u["status"] else 0
        _apply_round_end(pteam, oteam, log, mut_now)
        round_no += 1


def _arena_lobby_text(arena, world, current_env, owned):
    loadout = arena.get("loadout", [])
    env_name, env_boost, env_nerf = current_env
    mut = world.get("mutator"); mut_text = "None active."
    if mut: mut_text = f"{mut[0]}: {mut[1]}"
    team_bits = []
    for pet in loadout:
        nm = pet if isinstance(pet, str) else pet.get("name", str(pet))
        el = _infer_element(nm); role, rarity, _ = _assign_role_rarity(nm)
        team_bits.append(f"• {nm} ({rarity} {role}, {el})")
    team_text = "\n".join(team_bits) if team_bits else "None (use Set Team to add animals)"
    lines = [
        ":stadium: *HORSEY ARENA — LOBBY*",
        f"Rating {arena['rating']} | Tokens {arena['tokens']} | Crowns {arena['crowns']}",
        f"Wins {arena['wins']} | Losses {arena['losses']} | Streak {arena['streak']}",
        f"Level {arena['level']} ({arena['xp']} XP)",
        f"Season {world['season']} | Chaos {world['chaos']:.2f}",
        f"_{world['last_event']}_",
        f"Environment: *{env_name}* (boosts `{env_boost}`, weakens `{env_nerf}`)",
        f"Mutator: *{mut_text}*",
        f"\n*Team Loadout:*\n{team_text}",
        f"\n*Last Result:*\n{arena['last_log']}",
    ]
    if arena.get("last_ult"): lines.append(f"*Last Ultimate:* {arena['last_ult']}")
    return "\n".join(lines)


def _arena_blocks(uid: str, arena: dict, world: dict, owned: list, current_env: tuple) -> list[dict]:
    return [
        {"type": "section", "text": {"type": "mrkdwn", "text": _arena_lobby_text(arena, world, current_env, owned)}},
        {"type": "actions", "elements": [
            {"type": "button", "text": {"type": "plain_text", "text": "Fight Match"}, "action_id": "arena_fight", "style": "primary", "value": uid},
            {"type": "button", "text": {"type": "plain_text", "text": "View Ladder"}, "action_id": "arena_ladder", "value": uid},
            {"type": "button", "text": {"type": "plain_text", "text": "Crown Shop"}, "action_id": "arena_shop", "value": uid},
            {"type": "button", "text": {"type": "plain_text", "text": "Leave Arena"}, "action_id": "arena_leave", "style": "danger", "value": uid},
        ]},
    ]


async def setup(app):

    @app.command("/arena")
    async def arena_cmd(ack, command, client, respond):
        await ack()
        uid = command["user_id"]; channel = command["channel_id"]
        parts = (command.get("text") or "").strip().split(None, 1)
        sub = parts[0].lower() if parts else ""
        arg = parts[1].strip() if len(parts) > 1 else ""

        if sub == "buy":
            items = {
                "might": ("Might Emblem", 3, "power_boost", 0.05),
                "haste": ("Haste Emblem", 3, "speed_boost", 0.07),
                "ward": ("Ward Emblem", 3, "def_boost", 0.07),
                "luck": ("Lucky Emblem", 4, "crit_boost", 0.03),
            }
            item_key = arg.lower()
            if item_key not in items:
                await respond("Usage: `/arena buy <might|haste|ward|luck>`"); return
            name, cost, key, amount = items[item_key]
            user = get_user(uid); arena = user.setdefault("arena", {})
            arena.setdefault("crowns", 0); arena.setdefault("passives", {})
            if arena["crowns"] < cost:
                await respond(f"Not enough crowns. Need {cost}, have {arena['crowns']}."); return
            arena["crowns"] -= cost; arena["passives"][key] = arena["passives"].get(key, 0.0) + amount
            arena["last_log"] = f"Purchased {name}."
            save_state(); await respond(f":medal: Purchased *{name}*! Your {key} is now {arena['passives'][key]:.2f}.")

        elif sub == "setteam":
            if not arg:
                await respond("Usage: `/arena setteam animal1, animal2, ...` (up to 5, comma-separated)"); return
            chosen = [s.strip() for s in arg.split(",") if s.strip()][:5]
            user = get_user(uid); arena = user.setdefault("arena", {}); arena["loadout"] = chosen
            arena["last_log"] = f"Team updated: {', '.join(chosen)}"; save_state()
            await respond(f":stadium: Team set: {', '.join(chosen)}")

        else:
            user = get_user(uid); arena = user.setdefault("arena", {})
            now = datetime.datetime.utcnow().date().isoformat()
            if arena.get("last_token_reset") != now: arena["tokens"] = 3; arena["last_token_reset"] = now
            for k, v in [("rating",1000),("tokens",3),("crowns",0),("wins",0),("losses",0),("streak",0),
                         ("level",1),("xp",0),("last_log","The Arena gate creaks open."),("in_battle",False),
                         ("loadout",[]),("passives",{}),("evolved",{}),("last_mutator",None),("last_ult","")]:
                arena.setdefault(k, v)
            if not arena["loadout"]:
                arena["loadout"] = [p if isinstance(p, str) else p.get("name","Unknown") for p in user.get("team", [])[:5]]
            world = state.setdefault("arena_world", {})
            for k, v in [("season",1),("chaos",0.0),("total_matches",0),("last_champion",None),
                         ("last_event","The sands are quiet."),("ladder",{}),("mutator",None)]:
                world.setdefault(k, v)
            owned = [p if isinstance(p, str) else p.get("name","Unknown") for p in user.get("owned_animals", [])]
            idx = (world["season"] - 1) % len(ENVIRONMENTS); current_env = ENVIRONMENTS[idx]
            save_state()
            result = await client.chat_postMessage(channel=channel, blocks=_arena_blocks(uid, arena, world, owned, current_env), text="Arena")
            _sessions[uid] = {"arena": arena, "world": world, "owned": owned, "current_env": current_env, "ts": result["ts"], "channel": channel}

    @app.action("arena_fight")
    async def arena_fight(ack, body, client):
        await ack()
        uid = body["actions"][0]["value"]; actor = body["user"]["id"]
        if actor != uid: return
        sess = _sessions.get(uid)
        if not sess: return
        channel = sess["channel"]; ts = sess["ts"]; arena = sess["arena"]; world = sess["world"]
        current_env = sess["current_env"]
        if arena["tokens"] <= 0:
            await client.chat_postEphemeral(channel=channel, user=uid, text="No fight tokens left."); return
        if not arena.get("loadout"):
            await client.chat_postEphemeral(channel=channel, user=uid, text="No team selected."); return
        arena["tokens"] -= 1; arena["in_battle"] = True
        player_names = list(arena["loadout"])
        opp_names = random.sample(list(ASCII_SPRITES.keys()), k=min(5, len(ASCII_SPRITES)))
        pstats = _build_team_stats(player_names, arena, world)
        ostats = _build_team_stats(opp_names, arena, world)
        await client.chat_update(channel=channel, ts=ts, text="```Battle starting...```", blocks=[])
        result, log, mut, last_ult = simulate_battle(pstats, ostats, world, current_env)
        streak = arena["streak"]; xp = arena["xp"]; level = arena["level"]; rating = arena["rating"]
        if result == "win":
            delta = random.randint(20, 35); xp_gain = random.randint(35, 60); crowns = random.randint(0, 3)
            rating += delta; xp += xp_gain; streak += 1; arena["wins"] += 1; arena["crowns"] += crowns
            world["chaos"] += 0.05
            if arena["tokens"] < 5: arena["tokens"] += 1
            res_text = f"*Victory!*\nRating +{delta} | XP +{xp_gain} | Crowns +{crowns} | +1 Token"
        elif result == "loss":
            delta = -random.randint(8, 20); xp_gain = random.randint(15, 30); rating += delta; xp += xp_gain
            streak = 0; arena["losses"] += 1; world["chaos"] += 0.02
            res_text = f"*Defeat.*\nRating {delta} | XP +{xp_gain}"
        else:
            xp_gain = random.randint(10, 18); xp += xp_gain; world["chaos"] += 0.01
            res_text = f"*Draw.*\nXP +{xp_gain}"
        while xp >= 100: xp -= 100; level += 1; arena["crowns"] += 1; world["chaos"] += 0.05
        arena["rating"] = max(0, rating); arena["xp"] = xp; arena["level"] = level; arena["streak"] = streak
        world["total_matches"] += 1
        evolution_text = ""
        if result == "win" and streak >= 3 and arena["loadout"]:
            candidate = random.choice(arena["loadout"]); evo_target = EVOLUTIONS.get(candidate)
            if evo_target:
                arena["evolved"][candidate] = evo_target
                arena["loadout"] = [arena["evolved"].get(n, n) for n in arena["loadout"]]
                evolution_text = f"\n\n:sparkles: Evolution! {candidate} → *{evo_target}*!"
        if world["chaos"] > 6:
            world["season"] += 1; world["chaos"] = 0; world["last_event"] = "A new Arena Season begins!"
            idx = (world["season"] - 1) % len(ENVIRONMENTS); sess["current_env"] = ENVIRONMENTS[idx]
        if last_ult: arena["last_ult"] = last_ult
        arena["last_log"] = (res_text.replace("*","") + evolution_text).strip()
        save_state()
        battle_summary = "\n".join(log[-20:])
        opp_text = ", ".join(opp_names)
        mut_name = mut[0] if mut else "None"
        result_text = (
            f":stadium: *ARENA MATCH RESULT*\n"
            f"Result: *{result.upper()}*\n"
            f"Opponent: {opp_text}\nMutator: *{mut_name}*\n\n"
            f"{res_text}{evolution_text}\n\n"
            f"*Battle Log:*\n```{battle_summary}```"
        )
        await client.chat_update(channel=channel, ts=ts, text=result_text, blocks=[
            {"type": "section", "text": {"type": "mrkdwn", "text": result_text[:2800]}},
            {"type": "actions", "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "Back to Lobby"}, "action_id": "arena_back", "value": uid},
            ]},
        ])

    @app.action("arena_back")
    async def arena_back(ack, body, client):
        await ack()
        uid = body["actions"][0]["value"]; actor = body["user"]["id"]
        if actor != uid: return
        sess = _sessions.get(uid)
        if not sess: return
        channel = sess["channel"]; ts = sess["ts"]; arena = sess["arena"]; world = sess["world"]
        owned = sess["owned"]; current_env = sess["current_env"]
        await client.chat_update(channel=channel, ts=ts, blocks=_arena_blocks(uid, arena, world, owned, current_env), text="Arena")

    @app.action("arena_ladder")
    async def arena_ladder(ack, body, client):
        await ack()
        uid = body["actions"][0]["value"]; actor = body["user"]["id"]
        if actor != uid: return
        sess = _sessions.get(uid)
        if not sess: return
        channel = sess["channel"]; ts = sess["ts"]; arena = sess["arena"]; world = sess["world"]
        ladder = world.setdefault("ladder", {}); ladder[str(uid)] = arena["rating"]
        sorted_pairs = sorted(ladder.items(), key=lambda x: x[1], reverse=True)[:10]
        lines = [f"#{i} <@{pid}> — {rating}" for i, (pid, rating) in enumerate(sorted_pairs, 1)]
        board = "\n".join(lines) if lines else "No ranked players yet."
        save_state()
        ladder_text = f":trophy: *Arena Ladder*\n{board}"
        await client.chat_update(channel=channel, ts=ts, blocks=[
            {"type": "section", "text": {"type": "mrkdwn", "text": ladder_text}},
            {"type": "actions", "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "Back"}, "action_id": "arena_back", "value": uid},
            ]},
        ], text="Ladder")

    @app.action("arena_shop")
    async def arena_shop(ack, body, client):
        await ack()
        uid = body["actions"][0]["value"]; actor = body["user"]["id"]
        if actor != uid: return
        sess = _sessions.get(uid)
        if not sess: return
        channel = sess["channel"]; ts = sess["ts"]; arena = sess["arena"]
        items = {
            "might": ("Might Emblem", 3, "power_boost", 0.05),
            "haste": ("Haste Emblem", 3, "speed_boost", 0.07),
            "ward": ("Ward Emblem", 3, "def_boost", 0.07),
            "luck": ("Lucky Emblem", 4, "crit_boost", 0.03),
        }
        item_lines = "\n".join(f"• *{name}* — {cost} crowns" for _, (name, cost, _, _) in items.items())
        shop_text = f":medal: *Arena Crown Shop*\nYou have *{arena['crowns']}* crowns.\n\n{item_lines}\n\nUse `/arena_buy <might|haste|ward|luck>` to purchase."
        await client.chat_update(channel=channel, ts=ts, blocks=[
            {"type": "section", "text": {"type": "mrkdwn", "text": shop_text}},
            {"type": "actions", "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "Back"}, "action_id": "arena_back", "value": uid},
            ]},
        ], text="Crown Shop")


    @app.action("arena_leave")
    async def arena_leave(ack, body, client):
        await ack()
        uid = body["actions"][0]["value"]; actor = body["user"]["id"]
        if actor != uid: return
        sess = _sessions.pop(uid, None)
        if not sess: return
        channel = sess["channel"]; ts = sess["ts"]
        await client.chat_update(channel=channel, ts=ts, text=":stadium: You step away from the sands.", blocks=[])
