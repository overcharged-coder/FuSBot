import random
from economy_shared import state, save_state
from economy import get_user, update_balance, get_pray_boost

_sessions: dict[str, dict] = {}


def _init_world():
    world = state.setdefault("world", {})
    world.setdefault("corruption", 0.0)
    world.setdefault("raid_boss", None)
    world.setdefault("raid_hp", 0)
    world.setdefault("raid_max_hp", 0)
    world.setdefault("raid_cycle", 0)
    world.setdefault("last_event", "Dormant")
    world.setdefault("rift_level", 0)
    world.setdefault("rift_instability", 0.0)
    return world


def _get_power(d, world):
    s = d["skills"]
    base = d["floor"] * 12 + len(d["relics"]) * 9 + s["might"] * 14 + s["ward"] * 5 + s["instinct"] * 8
    base += d["rift_depth"] * 3 + len(d["mutations"]) * 6
    return max(10, base - len(d["curses"]) * 11 - len(d["afflictions"]) * 8)


def _get_luck(d):
    s = d["skills"]
    return max(0.15, 1.0 + s["greed"] * 0.09 + len(d["relics"]) * 0.02 + len(d["mutations"]) * 0.01 - len(d["curses"]) * 0.04 - d["rift_depth"] * 0.005)


def _get_warp(d):
    return d["skills"]["warp"] * 0.035 + len(d["relics"]) * 0.006 + d["rift_depth"] * 0.004


def _get_sanity_modifier(d):
    ratio = max(0, min(d["sanity"], d["max_sanity"])) / max(1, d["max_sanity"])
    if ratio >= 0.9: return 1.05, 0.0
    if ratio >= 0.7: return 1.0, 0.0
    if ratio >= 0.5: return 0.95, 0.02
    if ratio >= 0.3: return 0.9, 0.05
    return 0.82, 0.1


def _adjust_sanity(d, delta):
    d["sanity"] = max(0, min(d["max_sanity"], d["sanity"] + delta))
    if d["sanity"] == 0 and "Broken Mind" not in d["curses"]:
        d["curses"].append("Broken Mind")


def _ensure_raid_boss(world):
    if world["raid_boss"] is None or world["raid_hp"] <= 0:
        world["raid_cycle"] += 1
        boss = random.choice(["Abyssal World-Serpent", "Chronophage Colossus", "Starlit Void Leviathan", "Omega Horsey of Endings", "Reality-Flaying Dragon"])
        base_hp = 1200 + int(world["corruption"] * 350) + world["raid_cycle"] * 320 + world["rift_level"] * 120
        world["raid_boss"] = boss; world["raid_hp"] = base_hp; world["raid_max_hp"] = base_hp
        world["last_event"] = f"New raid boss: {boss}"; save_state()


def _dungeon_text(d, world, uid=""):
    s = d["skills"]
    power = _get_power(d, world); luck = _get_luck(d); warp = _get_warp(d)
    hp_bar = f"{d['hp']}/{d['max_hp']}"; san_bar = f"{d['sanity']}/{d['max_sanity']}"
    lines = [
        f"*:european_castle: Dungeon Rift*",
        f"Floor {d['floor']} | HP {hp_bar} | Sanity {san_bar} | Energy {d['energy']} ⚡",
        f"Relics {len(d['relics'])} | Curses {len(d['curses'])} | Mutations {len(d['mutations'])}",
        f"Power {power} | Luck {luck:.2f} | Warp {warp:.2f}",
        f"Skills → Might {s['might']} Ward {s['ward']} Greed {s['greed']} Warp {s['warp']} Instinct {s['instinct']}",
        f"SP {d['skill_points']} | Raid Tokens {d['raid_tokens']} | Rift Depth {d['rift_depth']}",
        f"World Corruption {world['corruption']:.2f} | Rift Level {world['rift_level']}",
        f"Event: {world['last_event']}",
    ]
    if world["raid_boss"]:
        hp = world["raid_hp"]; mx = max(1, world["raid_max_hp"])
        bar = "█" * int(14 * hp / mx) + "░" * (14 - int(14 * hp / mx))
        lines.append(f"*Raid Boss:* {world['raid_boss']} {bar} {hp}/{mx}")
    lines.append(f"\n_{d.get('last_log', '')}_")
    return "\n".join(lines)


def _dungeon_blocks(uid: str, d: dict, world: dict) -> list[dict]:
    return [
        {"type": "section", "text": {"type": "mrkdwn", "text": _dungeon_text(d, world, uid)}},
        {"type": "actions", "elements": [
            {"type": "button", "text": {"type": "plain_text", "text": "Explore"}, "action_id": "dng_explore", "style": "primary", "value": uid},
            {"type": "button", "text": {"type": "plain_text", "text": "Rest"}, "action_id": "dng_rest", "value": uid},
            {"type": "button", "text": {"type": "plain_text", "text": "Skills"}, "action_id": "dng_skills", "value": uid},
            {"type": "button", "text": {"type": "plain_text", "text": "Raid Boss"}, "action_id": "dng_raid", "value": uid},
        ]},
        {"type": "actions", "elements": [
            {"type": "button", "text": {"type": "plain_text", "text": "Rift Dive"}, "action_id": "dng_rift", "value": uid},
            {"type": "button", "text": {"type": "plain_text", "text": "Leave"}, "action_id": "dng_leave", "style": "danger", "value": uid},
        ]},
    ]


async def _refresh(client, channel, ts, uid, d, world):
    await client.chat_update(channel=channel, ts=ts, blocks=_dungeon_blocks(uid, d, world), text="Dungeon")


async def _explore(uid: str, d: dict, world: dict):
    if d["hp"] <= 0:
        d["active"] = False; save_state()
        return None, "You cannot move. The dungeon has consumed you.", True
    if d["energy"] <= 0:
        d["last_log"] = "You are exhausted. Rest first."; save_state()
        return d, None, False
    d["energy"] -= 1; world["corruption"] += 0.02 + d["floor"] * 0.001
    san_mult, extra_curse = _get_sanity_modifier(d)
    pressure = 0.05 + d["rift_depth"] * 0.01 + world["rift_instability"] * 0.15
    event_roll = random.random()
    boss_floor = d["floor"] % 7 == 0
    if boss_floor and random.random() < 0.6 * san_mult:
        return await _boss(uid, d, world, san_mult)
    if event_roll < 0.32:   return await _battle(uid, d, world, san_mult, extra_curse)
    elif event_roll < 0.54: return await _loot(uid, d, world, san_mult)
    elif event_roll < 0.70: return await _trap(uid, d, world, san_mult, extra_curse)
    elif event_roll < 0.82: return await _altar(uid, d, world)
    elif event_roll < 0.92: return await _world_rift(uid, d, world, pressure)
    else:
        inv_chance = 0.08 + _get_warp(d) * 0.5 + pressure * 0.4
        if random.random() < inv_chance and d["invasion_shield"] <= 0:
            return await _invasion(uid, d, world)
        return await _world_rift(uid, d, world, pressure)


async def _battle(uid, d, world, san_mult, extra_curse):
    power = _get_power(d, world) * san_mult; luck = _get_luck(d); ward = d["skills"]["ward"]
    tier = min(6, 1 + d["floor"] // 5)
    monsters = {
        1: [("Gloom Slime",40,0.70),("Duskwolf",65,0.62)], 2: [("Abyss Stalker",120,0.55),("Shatter Imp",150,0.50)],
        3: [("Grave Titan",240,0.44),("Spectral Butcher",260,0.42)], 4: [("Entropy Hydra",360,0.36),("Obsidian Warden",380,0.34)],
        5: [("World Scar",520,0.30),("Chrono Horror",560,0.28)], 6: [("Rift-Torn Colossus",700,0.26),("Mind-Latched Leviathan",740,0.24)]
    }
    name, reward, base_win = random.choice(monsters[tier])
    win = max(0.05, min(0.96, base_win + power*0.0008 + luck*0.02 - world["corruption"]*0.01 - world["rift_instability"]*0.02))
    if random.random() < win:
        crit = random.random() < (0.08 + d["skills"]["might"] * 0.02)
        final = int(reward * luck * (2 if crit else 1) * get_pray_boost(uid))
        await update_balance(uid, final)
        d["floor"] += 1
        if d["floor"] % 4 == 0: d["skill_points"] += 1
        _adjust_sanity(d, random.randint(0, 3))
        d["last_log"] = f"Defeated {name} for {final} horsenncy." + (" *CRIT!*" if crit else "")
    else:
        dmg = max(1, int((random.randint(18,60) + int(world["corruption"]*5)) * (1 - ward*0.06) * (1 + world["rift_instability"]*0.4)))
        d["hp"] -= dmg; _adjust_sanity(d, -random.randint(3,8))
        if extra_curse > 0 and random.random() < extra_curse:
            d["curses"].append(random.choice(["Shivering Mind","Fading Color","Static Whispers"]))
        if d["hp"] <= 0:
            d["hp"] = 0; d["active"] = False; save_state()
            return None, f"{name} crushed you at floor {d['floor']}.", True
        d["last_log"] = f"{name} wounded you for {dmg} HP."
    save_state(); return d, None, False


async def _loot(uid, d, world, san_mult):
    luck = _get_luck(d); coin = int((random.randint(50,200) + d["floor"]*15) * luck * san_mult * get_pray_boost(uid))
    await update_balance(uid, coin); log = f"Found cache: {coin} horsenncy."
    if random.random() < 0.20 + luck*0.05:
        relic = random.choice(["Temporal Shard","Crown of Echoes","Void Mane Fragment","Prismatic Hoofprint","Stellar Bridle","Gilded Neighstone","Riftglass Eye"])
        d["relics"].append(relic); log += f" Relic: {relic}."
    if random.random() < 0.06 + d["rift_depth"]*0.01:
        mut = random.choice(["Extra Spine","Glass Nerves","Echoing Hoof","Fractal Tail"])
        d["mutations"].append(mut); _adjust_sanity(d, -random.randint(2,5)); log += f" Mutation: {mut}."
    if random.random() < 0.04 + world["corruption"]*0.02:
        curse = random.choice(["Mark of Hunger","Fractured Time","Weak Hoof","Gaze of the Abyss"])
        d["curses"].append(curse); log += f" Curse: {curse}."
    d["floor"] += 1
    if d["floor"] % 4 == 0: d["skill_points"] += 1
    d["last_log"] = log; save_state(); return d, None, False


async def _trap(uid, d, world, san_mult, extra_curse):
    ward = d["skills"]["ward"]
    dmg = max(5, int((random.randint(25,130) + int(world["corruption"]*10)) * (1 - ward*0.05) * (1 + world["rift_instability"]*0.4)))
    evade = 0.10 + d["skills"]["instinct"]*0.03
    if random.random() < evade * san_mult:
        d["last_log"] = "You sense the trap and dodge."
    else:
        d["hp"] -= dmg; _adjust_sanity(d, -random.randint(5,12))
        if extra_curse > 0 and random.random() < extra_curse + 0.05:
            d["curses"].append(random.choice(["Hollow Pulse","Bleeding Colors","Rusting Soul"]))
        if d["hp"] <= 0:
            d["hp"] = 0; d["active"] = False; save_state()
            return None, f"A catastrophic trap obliterates you on floor {d['floor']}.", True
        d["last_log"] = f"Trap hits you for {dmg} HP."
    d["floor"] += 1; save_state(); return d, None, False


async def _altar(uid, d, world):
    roll = random.random()
    if roll < 0.40:
        heal = random.randint(20,80) + d["skills"]["ward"]*10
        d["hp"] = min(d["max_hp"], d["hp"] + heal); _adjust_sanity(d, random.randint(4,9))
        d["last_log"] = f"Altar heals you for {heal} HP."
    elif roll < 0.70:
        d["skill_points"] += 1; _adjust_sanity(d, random.randint(1,4))
        d["last_log"] = "Altar grants 1 skill point."
    else:
        curse = random.choice(["Silent Brand","Bone Tax","Entropy Mark"])
        d["curses"].append(curse); _adjust_sanity(d, -random.randint(4,10))
        d["last_log"] = f"False altar curses you: {curse}."
    d["floor"] += 1; save_state(); return d, None, False


async def _world_rift(uid, d, world, pressure):
    _ensure_raid_boss(world); warp = _get_warp(d); roll = random.random()
    if roll < 0.23 + warp:
        world["corruption"] = max(0, world["corruption"] - 0.30); world["rift_instability"] = max(0, world["rift_instability"] - 0.08)
        world["last_event"] = "A cleansing wave sweeps the dungeon."; _adjust_sanity(d, random.randint(5,12))
        d["last_log"] = "Cleansing rift lowers corruption."
    elif roll < 0.50 + pressure:
        world["corruption"] += 0.5; world["rift_instability"] += 0.10; world["rift_level"] += 1
        world["last_event"] = "A catastrophic surge deepens all rifts."
        if world["raid_boss"]: world["raid_hp"] = int(world["raid_hp"]*1.20)+120; world["raid_max_hp"] = int(world["raid_max_hp"]*1.20)+120
        _adjust_sanity(d, -random.randint(5,14)); d["last_log"] = "Violent rift swells the world boss."
    else:
        shift = random.choice(["up","down"])
        if shift == "up":
            d["floor"] += 2; d["rift_depth"] += 1; _adjust_sanity(d, -random.randint(2,6))
            d["last_log"] = "Rift hurls you 2 floors forward."
        else:
            d["floor"] = max(1, d["floor"]-2); d["rift_depth"] = max(0, d["rift_depth"]-1); _adjust_sanity(d, random.randint(1,5))
            d["last_log"] = "Collapsing rift drags you 2 floors back."
    d["floor"] += 1; save_state(); return d, None, False


async def _boss(uid, d, world, san_mult):
    power = _get_power(d, world); luck = _get_luck(d)
    boss_name = random.choice(["Crown-Eater Stallion","Oblivion Roc","Sunless Unicorn King","Titanic Leviathan Colt","Rift-Crowned Archbeast"])
    hp_scale = 80 + d["floor"]*25 + int(world["corruption"]*40) + int(world["rift_instability"]*120)
    win = max(0.05, min(0.95, 0.40 + luck*0.05 + power*0.001 - world["corruption"]*0.03 - world["rift_instability"]*0.03))
    if random.random() < win:
        loot = int(hp_scale * luck * 1.8 * get_pray_boost(uid)); await update_balance(uid, loot)
        d["boss_kills"] += 1; d["floor"] += 1; d["energy"] = min(10, d["energy"]+2); d["skill_points"] += 2
        _adjust_sanity(d, random.randint(6,15))
        reliq = random.choice(["Crown of Ends","Star-Shear Bridle","Omega Hoofprint","Heart of the Rift"])
        d["relics"].append(reliq); d["last_log"] = f"Slain {boss_name} for {loot} horsenncy + relic {reliq}."
    else:
        dmg = random.randint(70,170) + int(world["corruption"]*25) + int(world["rift_instability"]*90)
        d["hp"] -= dmg; _adjust_sanity(d, -random.randint(8,18))
        curse = random.choice(["Shattered Courage","Fraying Reality","Burning Hooves","Riftburn Scars"])
        d["curses"].append(curse)
        if d["hp"] <= 0:
            d["hp"] = 0; d["active"] = False; save_state()
            return None, f"Boss {boss_name} erases you at floor {d['floor']}.", True
        d["last_log"] = f"Boss {boss_name} maimed you for {dmg} HP and inflicted {curse}."; d["floor"] += 1
    save_state(); return d, None, False


async def _invasion(uid, d, world):
    candidates = [(raw_id, udata["dungeon"]) for raw_id, udata in state["users"].items()
                  if raw_id != uid and isinstance(udata.get("dungeon"), dict) and udata["dungeon"].get("active") and udata["dungeon"].get("hp", 0) > 0]
    if not candidates:
        d["last_log"] = "Invasion rift sputters. No target."; d["floor"] += 1; save_state(); return d, None, False
    tid, td = random.choice(candidates)
    atk_power = _get_power(d, world) * (1 + d["skills"]["might"]*0.05)
    def_power = _get_power(td, world) * (1 + td["skills"]["ward"]*0.05)
    ratio = atk_power / max(10, atk_power + def_power)
    win = max(0.05, min(0.95, 0.55 + d["skills"]["instinct"]*0.03 - len(d["curses"])*0.02 - len(td["relics"])*0.01 + ratio*0.25))
    steal_ratio = random.uniform(0.06, 0.20)
    target_user = get_user(tid)
    if random.random() < win:
        stolen = int(target_user["balance"] * steal_ratio); target_user["balance"] = max(0, target_user["balance"] - stolen)
        get_user(uid)["balance"] += stolen
        relic_text = ""
        if td["relics"]: sr = random.choice(td["relics"]); td["relics"].remove(sr); d["relics"].append(sr); relic_text = f" and stole relic {sr}"
        _adjust_sanity(d, -random.randint(1,4)); d["last_log"] = f"Invaded <@{tid}> stealing {stolen} horsenncy{relic_text}."
        if d["invasion_shield"] < 2: d["invasion_shield"] += 1
    else:
        penalty = min(int(get_user(uid)["balance"] * 0.05), get_user(uid)["balance"])
        if penalty > 0: await update_balance(uid, -penalty)
        _adjust_sanity(d, -random.randint(2,6)); d["last_log"] = f"Invasion of <@{tid}> fails. Lost {penalty} horsenncy."
    d["floor"] += 1; save_state(); return d, None, False


async def setup(app):

    @app.command("/dungeon")
    async def dungeon_cmd(ack, command, client):
        await ack()
        uid = command["user_id"]; channel = command["channel_id"]
        user = get_user(uid); world = _init_world()
        d = user.setdefault("dungeon", {})
        for k, v in [("active",False),("floor",1),("hp",100),("max_hp",100),("energy",5),("skills",{}),
                     ("relics",[]),("curses",[]),("mutations",[]),("afflictions",[]),("skill_points",0),
                     ("last_floor_cleared",0),("raid_tokens",1),("invasion_shield",0),("last_log","You descend."),
                     ("runs",0),("boss_kills",0),("sanity",100),("max_sanity",100),("rift_depth",0),("session_id",0)]:
            d.setdefault(k, v)
        for sk in ["might","ward","greed","warp","instinct"]: d["skills"].setdefault(sk, 0)
        if not d["active"]:
            d.update({"floor":1,"hp":d["max_hp"],"energy":5,"sanity":d["max_sanity"],"rift_depth":0,"relics":[],"curses":[],"mutations":[],"afflictions":[],"invasion_shield":0,"last_log":"You descend into a fresh rifted dungeon."})
        d["active"] = True; d["session_id"] = random.randint(1, 10**12)
        _sessions[uid] = {"world": world}; save_state()
        result = await client.chat_postMessage(channel=channel, blocks=_dungeon_blocks(uid, d, world), text="Dungeon")
        _sessions[uid]["ts"] = result["ts"]; _sessions[uid]["channel"] = channel

    async def _handle(body, client, action_fn):
        uid = body["actions"][0]["value"]; actor = body["user"]["id"]
        if actor != uid: return
        sess = _sessions.get(uid)
        if not sess: return
        channel = sess["channel"]; ts = sess["ts"]
        user = get_user(uid); d = user.get("dungeon", {}); world = _init_world()
        if not d.get("active"):
            await client.chat_update(channel=channel, ts=ts, text="This dungeon run has ended. Use /dungeon to start a new run.", blocks=[])
            return
        result = await action_fn(uid, d, world)
        new_d, death_msg, dead = result
        if dead:
            await client.chat_update(channel=channel, ts=ts, text=f":skull: {death_msg}", blocks=[])
        else:
            await _refresh(client, channel, ts, uid, d, world)

    @app.action("dng_explore")
    async def dng_explore(ack, body, client):
        await ack()
        await _handle(body, client, _explore)

    @app.action("dng_rest")
    async def dng_rest(ack, body, client):
        await ack()
        uid = body["actions"][0]["value"]; actor = body["user"]["id"]
        if actor != uid: return
        sess = _sessions.get(uid)
        if not sess: return
        channel = sess["channel"]; ts = sess["ts"]
        user = get_user(uid); d = user.get("dungeon", {}); world = _init_world()
        if not d.get("active"): return
        if d["energy"] >= 6 and d["hp"] >= d["max_hp"]*0.8 and d["sanity"] >= d["max_sanity"]*0.7:
            d["last_log"] = "You're in good shape — resting feels pointless."; save_state()
        else:
            amb = 0.25 + world["corruption"]*0.02 + world["rift_instability"]*0.04
            if random.random() < amb:
                dmg = random.randint(20,80); d["hp"] -= dmg; _adjust_sanity(d, -random.randint(4,9))
                if d["hp"] <= 0:
                    d["hp"] = 0; d["active"] = False; save_state()
                    await client.chat_update(channel=channel, ts=ts, text=f":skull: Ambushed in sleep. You perish at floor {d['floor']}.", blocks=[])
                    return
                d["last_log"] = f"Ambushed while resting for {dmg} HP."
            else:
                heal = random.randint(25,80) + d["skills"]["ward"]*8; d["hp"] = min(d["max_hp"], d["hp"]+heal)
                d["energy"] = min(10, d["energy"]+3); _adjust_sanity(d, random.randint(4,10))
                d["last_log"] = f"You rest, healing {heal} HP and restoring energy."; save_state()
        await _refresh(client, channel, ts, uid, d, world)

    @app.action("dng_skills")
    async def dng_skills(ack, body, client):
        await ack()
        uid = body["actions"][0]["value"]; actor = body["user"]["id"]
        if actor != uid: return
        sess = _sessions.get(uid)
        if not sess: return
        channel = sess["channel"]; ts = sess["ts"]
        user = get_user(uid); d = user.get("dungeon", {}); world = _init_world()
        if not d.get("active"): return
        if d["skill_points"] <= 0:
            d["last_log"] = "No skill points available."; save_state()
        else:
            weights = [(k, max(1, 4 - d["skills"][k]) + (d["rift_depth"]//3 if k=="warp" else 0)) for k in ["might","ward","greed","warp","instinct"]]
            pool = [k for k, w in weights for _ in range(w)]
            chosen = random.choice(pool); d["skills"][chosen] += 1; d["skill_points"] -= 1
            _adjust_sanity(d, random.randint(0,2)); d["last_log"] = f"{chosen.title()} grows to {d['skills'][chosen]}."; save_state()
        await _refresh(client, channel, ts, uid, d, world)

    @app.action("dng_raid")
    async def dng_raid(ack, body, client):
        await ack()
        uid = body["actions"][0]["value"]; actor = body["user"]["id"]
        if actor != uid: return
        sess = _sessions.get(uid)
        if not sess: return
        channel = sess["channel"]; ts = sess["ts"]
        user = get_user(uid); d = user.get("dungeon", {}); world = _init_world()
        if not d.get("active"): return
        _ensure_raid_boss(world)
        if d["raid_tokens"] <= 0: d["last_log"] = "No raid tokens."; save_state()
        elif world["raid_hp"] <= 0: d["last_log"] = "Raid boss already defeated."; save_state()
        else:
            d["raid_tokens"] -= 1; power = _get_power(d, world); luck = _get_luck(d)
            dmg = int(power * random.uniform(0.7, 1.4) * luck); crit = random.random() < (0.10 + d["skills"]["might"]*0.03)
            if crit: dmg = int(dmg * 1.8)
            world["raid_hp"] = max(0, world["raid_hp"]-dmg)
            reward = int(dmg * (0.6+luck) * get_pray_boost(uid)); await update_balance(uid, reward)
            _adjust_sanity(d, random.randint(3,8))
            if world["raid_hp"] <= 0:
                bonus = int(world["raid_max_hp"]*0.2*get_pray_boost(uid)); await update_balance(uid, bonus)
                world["last_event"] = f"{world['raid_boss']} was slain!"; d["last_log"] = f"You deal {dmg} dmg and land the killing blow! +{reward+bonus} horsenncy."
                world["raid_boss"] = None; world["raid_hp"] = 0; world["raid_max_hp"] = 0; save_state()
            else:
                d["last_log"] = f"You strike {world['raid_boss']} for {dmg} dmg, earning {reward} horsenncy."; save_state()
        await _refresh(client, channel, ts, uid, d, world)

    @app.action("dng_rift")
    async def dng_rift(ack, body, client):
        await ack()
        uid = body["actions"][0]["value"]; actor = body["user"]["id"]
        if actor != uid: return
        sess = _sessions.get(uid)
        if not sess: return
        channel = sess["channel"]; ts = sess["ts"]
        user = get_user(uid); d = user.get("dungeon", {}); world = _init_world()
        if not d.get("active"): return
        if d["hp"] <= 0: d["active"] = False; save_state(); await client.chat_update(channel=channel, ts=ts, text=":skull: Your body is gone.", blocks=[]); return
        if d["energy"] < 2: d["last_log"] = "Need at least 2 energy to dive."; save_state(); await _refresh(client, channel, ts, uid, d, world); return
        d["energy"] -= 2; d["rift_depth"] += 1; world["rift_instability"] += 0.04; world["rift_level"] += 1; roll = random.random()
        if roll < 0.40:
            gain = int((80 + d["floor"]*18) * _get_luck(d) * get_pray_boost(uid)); await update_balance(uid, gain)
            _adjust_sanity(d, -random.randint(3,7)); d["last_log"] = f"Rift yields {gain} horsenncy."
        elif roll < 0.70:
            relic = random.choice(["Rift-Linked Crown","Glass Ribcage","Endless Lantern","Gravity Knot"])
            d["relics"].append(relic); _adjust_sanity(d, -random.randint(5,10)); d["last_log"] = f"Rift fuses relic {relic} to you."
        elif roll < 0.88:
            mut = random.choice(["Second Shadow","Hollow Voice","Clockwork Gaze","Liquid Bones"])
            d["mutations"].append(mut); _adjust_sanity(d, -random.randint(6,14)); d["last_log"] = f"Rift rewrites you with mutation {mut}."
        else:
            _adjust_sanity(d, -random.randint(10,18)); curse = random.choice(["Unbound Echo","Screaming Thread","Molten Silence"])
            d["curses"].append(curse); d["last_log"] = f"Rift collapses, branding you: {curse}."
        save_state(); await _refresh(client, channel, ts, uid, d, world)

    @app.action("dng_leave")
    async def dng_leave(ack, body, client):
        await ack()
        uid = body["actions"][0]["value"]; actor = body["user"]["id"]
        if actor != uid: return
        sess = _sessions.get(uid)
        if not sess: return
        channel = sess["channel"]; ts = sess["ts"]
        user = get_user(uid); d = user.get("dungeon", {})
        d["active"] = False; d["runs"] = d.get("runs", 0) + 1
        reward = int(max(0, d["floor"]*40 + len(d["relics"])*60 - len(d["curses"])*45 + d["rift_depth"]*30) * get_pray_boost(uid))
        await update_balance(uid, reward); save_state()
        await client.chat_update(channel=channel, ts=ts, text=f":door: You leave at floor {d['floor']} with {reward} horsenncy.", blocks=[])
        _sessions.pop(uid, None)
