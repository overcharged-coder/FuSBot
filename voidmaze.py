import random
import asyncio
from economy_shared import state, save_state
from economy import get_user, update_balance, get_pray_boost, get_balance

_sessions: dict[str, dict] = {}


def _power(vm):
    base = vm["depth"] * 6 + len(vm["artifacts"]) * 10 + vm["keys"] * 4 + vm["fragments"] * 2
    base += vm["streak"] * 8 + vm.get("combo", 0) * 5
    return max(5, base - len(vm["anomalies"]) * 9)


def _clarity_mod(vm):
    r = vm["clarity"] / max(1, vm["max_clarity"])
    if r >= 0.9: return 1.12, 0.01
    if r >= 0.7: return 1.0, 0.02
    if r >= 0.5: return 0.92, 0.03
    if r >= 0.3: return 0.85, 0.06
    return 0.75, 0.10


def _adjust_clarity(vm, amt):
    vm["clarity"] = max(0, min(vm["max_clarity"], vm["clarity"] + amt))
    if vm["clarity"] == 0 and "Mind-Hollowed" not in vm["anomalies"]:
        vm["anomalies"].append("Mind-Hollowed")


def _roll_cooldown(key):
    ranges = {
        "glass_pebble": (2, 4), "abyss_lantern": (2, 4), "omega_prism": (1, 3),
        "ghost_spiral": (3, 6), "echo_recursive": (2, 4), "warp_phase": (3, 5),
        "temporal_shear": (2, 4), "fractal_glyph": (3, 6), "reversed_compass": (1, 3),
        "cubic_worm": (2, 5), "eternal_coil": (1, 4), "star_bleed": (3, 7),
        "obsidian_bloom": (2, 4), "hollow_static": (1, 2), "loose_geometry": (2, 4),
        "parasitic_dream": (1, 2), "mind_static": (2, 5), "recursion_blessing": (2, 4),
        "stillheart_boon": (1, 3), "stormwalker_boon": (3, 6),
        "glyphreader_insight": (2, 4), "pulse_harmony": (2, 5),
    }
    lo, hi = ranges.get(key, (2, 4))
    return random.randint(lo, hi)


def _apply_synergies(vm, world):
    arts = vm["artifacts"]; anoms = vm["anomalies"]; boons = vm.get("boons", [])
    sy_cd = vm.setdefault("synergy_cd", {}); lines = []

    def can_trigger(key):
        cd = sy_cd.get(key, 0)
        if cd > 0: sy_cd[key] = cd - 1; return False
        return True

    def trigger(key, text, fn):
        if not can_trigger(key): return
        fn(); sy_cd[key] = _roll_cooldown(key); lines.append(text)

    if "Glass Feather" in arts and "Silent Pebble" in arts:
        trigger("glass_pebble", "Glass Feather + Silent Pebble → Clarity +2", lambda: _adjust_clarity(vm, 2))
    if "Abyssal Crown" in arts and "Inverse Lantern" in arts:
        trigger("abyss_lantern", "Abyssal Crown + Inverse Lantern → Storm +0.02", lambda: world.__setitem__("storm", world["storm"] + 0.02))
    if "Omega Prism" in arts:
        trigger("omega_prism", "Omega Prism → Fragments +1", lambda: vm.__setitem__("fragments", vm["fragments"] + 1))
    if "Ghost Spiral" in arts and world["pulse"] > 0.3:
        trigger("ghost_spiral", "Ghost Spiral (Pulse > 0.3) → Depth +1", lambda: vm.__setitem__("depth", vm["depth"] + 1))
    if "Echo Crown" in arts and "Recursive Loop" in anoms:
        def f_echo():
            _adjust_clarity(vm, -3); vm["fragments"] += 2
        trigger("echo_recursive", "Echo Crown + Recursive Loop → Clarity -3, Fragments +2", f_echo)
    if "Warp Tablet" in arts and "Phase Drift" in anoms:
        trigger("warp_phase", "Warp Tablet + Phase Drift → Keys +1", lambda: vm.__setitem__("keys", vm["keys"] + 1))
    if "Temporal Harness" in arts and "Time Shear" in anoms:
        trigger("temporal_shear", "Temporal Harness + Time Shear → Depth +1", lambda: vm.__setitem__("depth", vm["depth"] + 1))
    if "Fractal Glyph" in arts:
        trigger("fractal_glyph", "Fractal Glyph → Depth +1", lambda: vm.__setitem__("depth", vm["depth"] + 1))
    if "Reversed Compass" in arts:
        def f_rev():
            if random.random() < 0.15: vm["depth"] += 1
        trigger("reversed_compass", "Reversed Compass → 15% chance Depth +1", f_rev)
    if "Cubic Heart" in arts and "Worming Echo" in anoms:
        trigger("cubic_worm", "Cubic Heart + Worming Echo → Clarity -2", lambda: _adjust_clarity(vm, -2))
    if "Eternal Coil" in arts:
        trigger("eternal_coil", "Eternal Coil → Pulse +0.01", lambda: world.__setitem__("pulse", world["pulse"] + 0.01))
    if "Star-Bleed Idol" in arts and vm["clarity"] < 40:
        trigger("star_bleed", "Star-Bleed Idol (Low Clarity) → Fragments +4", lambda: vm.__setitem__("fragments", vm["fragments"] + 4))
    if "Obsidian Bloom" in arts:
        def f_obs():
            if random.random() < 0.2: vm["fragments"] += 3
        trigger("obsidian_bloom", "Obsidian Bloom → 20% chance Fragments +3", f_obs)
    if "Hollow Static" in anoms:
        trigger("hollow_static", "Hollow Static → Clarity -1", lambda: _adjust_clarity(vm, -1))
    if "Loose Geometry" in anoms:
        def f_lg():
            if random.random() < 0.1: vm["depth"] += 1
        trigger("loose_geometry", "Loose Geometry → 10% chance Depth +1", f_lg)
    if "Parasitic Dream" in anoms:
        def f_pd(): vm["clarity"] = max(1, vm["clarity"] - 1)
        trigger("parasitic_dream", "Parasitic Dream → Clarity -1", f_pd)
    if "Mind Static" in anoms:
        def f_ms():
            if random.random() < 0.1 and vm["keys"] > 0: vm["keys"] -= 1
        trigger("mind_static", "Mind Static → 10% chance lose 1 Key", f_ms)
    if "Recursion Blessing" in boons:
        def f_rb():
            if random.random() < 0.15: vm["fragments"] += 2
        trigger("recursion_blessing", "Recursion Blessing → 15% chance Fragments +2", f_rb)
    if "Stillheart Boon" in boons:
        def f_sh():
            if vm["clarity"] < vm["max_clarity"]: _adjust_clarity(vm, 1)
        trigger("stillheart_boon", "Stillheart Boon → Clarity +1 (if not full)", f_sh)
    if "Stormwalker Boon" in boons:
        def f_sw():
            if world["storm"] > 0.5: vm["depth"] += 1
        trigger("stormwalker_boon", "Stormwalker Boon (High Storm) → Depth +1", f_sw)
    if "Glyphreader Insight" in boons:
        def f_gi():
            if random.random() < 0.25: vm["fragments"] += 1; _adjust_clarity(vm, 1)
        trigger("glyphreader_insight", "Glyphreader Insight → 25% chance Fragments +1 and Clarity +1", f_gi)
    if "Pulse Harmony" in boons:
        def f_ph():
            if world["pulse"] > 0.5: vm["depth"] += 1; _adjust_clarity(vm, 1)
        trigger("pulse_harmony", "Pulse Harmony (High Pulse) → Depth +1 and Clarity +1", f_ph)
    vm["last_synergy_log"] = "\n".join(f"• {l}" for l in lines) if lines else ""


def _roll_boon(vm):
    boon = random.choice(["Recursion Blessing", "Stillheart Boon", "Stormwalker Boon", "Glyphreader Insight", "Pulse Harmony"])
    vm.setdefault("boons", []).append(boon)
    return boon


def _apply_passive_world(world):
    if world["storm"] > 1.5: world["pulse"] += 0.02
    if world["pulse"] > 1.0:
        world["season"] += 1; world["pulse"] *= 0.4; world["storm"] *= 0.6
        world["last_event"] = "The Maze enters a new micro-season."
    if world["storm"] < 0: world["storm"] = 0
    if world["pulse"] < 0: world["pulse"] = 0


def _vm_text(vm, world, rooms):
    pwr = _power(vm); m, cpen = _clarity_mod(vm)
    room_lines = "\n".join(f"*[{i+1}] {r['name']}*\n{r['desc']}" for i, r in enumerate(rooms))
    synergy = vm.get("last_synergy_log", "")
    lines = [
        f":cyclone: *VOIDMAZE — Depth {vm['depth']}*",
        room_lines,
        f"Power {pwr} | Clarity {vm['clarity']}/{vm['max_clarity']} | Combo {vm.get('combo',0)}",
        f"Artifacts {len(vm['artifacts'])} | Keys {vm['keys']} | Fragments {vm['fragments']} | Anomalies {len(vm['anomalies'])} | Streak {vm['streak']}",
        f"World: Storm {world['storm']:.2f} | Pulse {world['pulse']:.2f} | Season {world['season']}",
        f"_{world['last_event']}_",
        f"\n{vm.get('last_log', '')}",
    ]
    if synergy: lines.append(f"*Synergy:*\n{synergy}")
    return "\n".join(lines)


def _generate_rooms():
    choices = [
        ("Door of the Abyss", "A humming monolith leaking black light. Power rises, clarity bleeds.", "abyss_door"),
        ("Tangle Key Node", "Threads of logic and illusion knot together. Solving it grants a Maze Key.", "key_node"),
        ("Artifact Vault", "A floating vault of mirrors. Contains an Artifact or something far worse.", "artifact_vault"),
        ("Reality Fracture", "A raw tear into impossible geometry. Immense rewards or instant collapse.", "fracture"),
        ("Locus of Stillness", "A calm white chamber where the Maze forgets to breathe. Clarity may return.", "rest"),
        ("Echo Storm", "The Maze convulses with cosmic thunder. Global effects ripple outward.", "echo_storm"),
    ]
    weights = [4, 3, 3, 3, 2, 1]
    pool = [c for c, w in zip(choices, weights) for _ in range(w)]
    return [random.choice(pool) for _ in range(3)]


def _vm_blocks(uid: str, vm: dict, world: dict, rooms: list) -> list[dict]:
    return [
        {"type": "section", "text": {"type": "mrkdwn", "text": _vm_text(vm, world, rooms)}},
        {"type": "actions", "elements": [
            {"type": "button", "text": {"type": "plain_text", "text": f"Room {i+1}: {r[0]}"}, "action_id": f"vm_room_{i+1}", "style": "primary", "value": uid}
            for i, r in enumerate(rooms)
        ]},
        {"type": "actions", "elements": [
            {"type": "button", "text": {"type": "plain_text", "text": "Leave Maze"}, "action_id": "vm_leave", "style": "danger", "value": uid},
        ]},
    ]


async def _after_room(uid, vm, world, client, channel, ts, rooms):
    _apply_synergies(vm, world)
    _apply_passive_world(world)
    save_state()
    await client.chat_update(channel=channel, ts=ts, blocks=_vm_blocks(uid, vm, world, rooms), text="VoidMaze")


async def _handle_room(body, client, room_idx: int):
    uid = body["actions"][0]["value"]; actor = body["user"]["id"]
    if actor != uid: return
    sess = _sessions.get(uid)
    if not sess: return
    channel = sess["channel"]; ts = sess["ts"]; vm = sess["vm"]; world = sess["world"]
    if not vm.get("active"): return
    rooms = sess["rooms"]
    if room_idx < 1 or room_idx > len(rooms): return
    room_type = rooms[room_idx - 1][2]
    await _do_room(uid, vm, world, room_type, client, channel, ts)


async def _do_room(uid, vm, world, room_type, client, channel, ts):
    sess = _sessions[uid]
    m, cpen = _clarity_mod(vm)
    pwr = _power(vm)

    if room_type == "abyss_door":
        gain_frag = int(2 + vm["depth"] * 0.4 + pwr * 0.05); clarity_loss = random.randint(5, 14)
        vm["depth"] += 1; vm["fragments"] += gain_frag; vm["combo"] = vm.get("combo", 0) + 1
        _adjust_clarity(vm, -clarity_loss)
        if random.random() < cpen:
            anomaly = random.choice(["Hollow Static", "Worming Echo", "Loose Geometry"])
            vm["anomalies"].append(anomaly); vm["combo"] = 0
            vm["last_log"] = f"The door floods you with power but twists you. Gain {gain_frag} fragments and anomaly {anomaly}."
        else:
            vm["last_log"] = f"The door pulses. Gain {gain_frag} fragments but lose {clarity_loss} clarity. Combo grows."

    elif room_type == "key_node":
        puzzle = random.choice(["left", "right", "center"]); choice = random.choice(["left", "right", "center"])
        success = puzzle == choice; clarity_shift = random.randint(-4, 8)
        if success:
            vm["keys"] += 1; vm["depth"] += 1; vm["combo"] = vm.get("combo", 0) + 1
            _adjust_clarity(vm, clarity_shift)
            if random.random() < 0.25:
                boon = _roll_boon(vm); vm["last_log"] = f"Intuition aligns. Gain 1 key, {clarity_shift} clarity, boon {boon}."
            else: vm["last_log"] = f"Intuition aligns. Gain 1 key and {clarity_shift} clarity."
        else:
            _adjust_clarity(vm, -abs(clarity_shift))
            anomaly = random.choice(["Fractured Insight", "Recursive Loop"])
            vm["anomalies"].append(anomaly); vm["combo"] = 0
            vm["last_log"] = f"The Node rejects you. Anomaly {anomaly} and clarity loss."

    elif room_type == "artifact_vault":
        tier = min(5, 1 + vm["depth"] // 5)
        art_tables = {1: ["Glass Feather","Silent Pebble","Hollow Ring"], 2: ["Inverse Lantern","Fractal Glyph","Reversed Compass"],
                      3: ["Abyssal Crown","Cubic Heart","Orb of Warp"], 4: ["Star-Bleed Idol","Ghost Spiral","Temporal Harness"],
                      5: ["Omega Prism","Eternal Coil","Riftborn Crown"]}
        artifact = random.choice(art_tables[tier]); bad_roll = random.random() < 0.25
        clarity_hit = random.randint(3, 12); vm["artifacts"].append(artifact); vm["depth"] += 1
        if bad_roll:
            anomaly = random.choice(["Artifact Backlash", "Mirror Shatter"]); vm["anomalies"].append(anomaly)
            vm["combo"] = 0; _adjust_clarity(vm, -clarity_hit)
            vm["last_log"] = f"Vault yields {artifact}, but backlash gives {anomaly} and {clarity_hit} clarity loss."
        else:
            heal = random.randint(1, 7); _adjust_clarity(vm, heal); vm["combo"] = vm.get("combo", 0) + 1
            if random.random() < 0.35:
                boon = _roll_boon(vm); vm["last_log"] = f"Vault gifts {artifact} and boon {boon}."
            else: vm["last_log"] = f"Vault gifts {artifact}. The Maze hums approvingly."

    elif room_type == "fracture":
        roll = random.random()
        if roll < 0.25:
            drop = int(170 + pwr * 0.9 + vm["depth"] * 4)
            await update_balance(uid, drop); vm["depth"] += 2; vm["fragments"] += 4
            vm["combo"] = vm.get("combo", 0) + 2; _adjust_clarity(vm, -random.randint(5, 15))
            vm["last_log"] = f"Fracture erupts with wealth. Gain {drop} horsenncy and surge deeper."
        elif roll < 0.55:
            art = random.choice(["Echo Crown","Warp Tablet","Obsidian Bloom"]); vm["artifacts"].append(art)
            vm["depth"] += 1; vm["combo"] = vm.get("combo", 0) + 1; _adjust_clarity(vm, -random.randint(4, 8))
            if random.random() < 0.3:
                boon = _roll_boon(vm); vm["last_log"] = f"Fracture gifts {art} and boon {boon}, but clarity bleeds."
            else: vm["last_log"] = f"Fracture gifts {art}, but clarity bleeds."
        elif roll < 0.85:
            anomaly = random.choice(["Time Shear","Phase Drift","Soul Split"]); vm["anomalies"].append(anomaly)
            vm["depth"] += 1; vm["combo"] = 0; _adjust_clarity(vm, -random.randint(10, 20))
            vm["last_log"] = f"Fracture lashes out. Anomaly {anomaly}."
        else:
            vm["active"] = False; penalty = int(pwr * 1.5 + vm["depth"] * 20)
            bal = get_user(uid).get("balance", 0); penalty = min(penalty, bal)
            await update_balance(uid, -penalty); save_state()
            await client.chat_update(channel=channel, ts=ts, text=f":skull: The fracture consumes you. You lose {penalty} horsenncy.", blocks=[])
            return

    elif room_type == "rest":
        danger = 0.25 + world["storm"] * 0.1
        if random.random() < danger:
            dmg = random.randint(6, 16); _adjust_clarity(vm, -dmg)
            anomaly = random.choice(["Parasitic Dream","Mind Static"]); vm["anomalies"].append(anomaly); vm["combo"] = 0
            vm["last_log"] = f"Rest is shattered. Lose {dmg} clarity and gain anomaly {anomaly}."
        else:
            heal = random.randint(10, 25); _adjust_clarity(vm, heal); vm["depth"] += 1; vm["combo"] = 0
            if random.random() < 0.2:
                boon = _roll_boon(vm); vm["last_log"] = f"Stillness restores. Regain {heal} clarity, boon {boon}."
            else: vm["last_log"] = f"Stillness restores. Regain {heal} clarity."

    elif room_type == "echo_storm":
        r = random.random()
        if r < 0.33:
            world["storm"] += 0.4; world["pulse"] += 0.1; vm["depth"] += 1
            vm["combo"] = vm.get("combo", 0) + 1; _adjust_clarity(vm, -random.randint(6, 12))
            vm["last_log"] = "The Maze convulses. Storm intensifies and you are dragged deeper."
        elif r < 0.66:
            world["pulse"] += 0.3; reward = int(70 + vm["depth"] * 6); await update_balance(uid, reward); vm["fragments"] += 3
            if random.random() < 0.3:
                boon = _roll_boon(vm); vm["last_log"] = f"Pulse grants {reward} horsenncy, fragments, boon {boon}."
            else: vm["last_log"] = f"Pulse grants {reward} horsenncy and fragments."
        else:
            world["season"] += 1; world["storm"] *= 0.5; world["pulse"] *= 0.3
            vm["depth"] += 2; vm["combo"] = vm.get("combo", 0) + 2; _adjust_clarity(vm, random.randint(4, 12))
            vm["last_log"] = "A season turns. The Maze shifts and you slip further in."
        world["last_event"] = vm["last_log"]

    new_rooms = _generate_rooms()
    sess["rooms"] = new_rooms
    await _after_room(uid, vm, world, client, channel, ts, new_rooms)


async def setup(app):

    @app.command("/fus_voidmaze")
    async def voidmaze_cmd(ack, command, client):
        await ack()
        uid = command["user_id"]; channel = command["channel_id"]
        user = get_user(uid); vm = user.setdefault("voidmaze", {})
        for k, v in [("active",False),("depth",0),("clarity",100),("max_clarity",100),("keys",0),("artifacts",[]),
                     ("boons",[]),("anomalies",[]),("fragments",0),("runs",0),("streak",0),("last_log","The Maze awakens."),
                     ("best_depth",0),("synergy_cd",{}),("last_synergy_log",""),("combo",0)]:
            vm.setdefault(k, v)
        if not vm["active"]:
            vm.update({"depth":0,"clarity":vm["max_clarity"],"anomalies":[],"boons":[],"artifacts":[],"keys":0,
                       "fragments":0,"synergy_cd":{},"last_synergy_log":"","combo":0})
        vm["active"] = True
        world = state.setdefault("voidmaze_world", {})
        for k, v in [("storm",0.0),("pulse",0.0),("season",1),("last_event","The labyrinth hums with cold awareness.")]:
            world.setdefault(k, v)
        save_state()
        rooms = _generate_rooms()
        result = await client.chat_postMessage(channel=channel, blocks=_vm_blocks(uid, vm, world, rooms), text="VoidMaze")
        _sessions[uid] = {"vm": vm, "world": world, "rooms": rooms, "ts": result["ts"], "channel": channel}

    @app.action("vm_room_1")
    async def vm_room_1(ack, body, client):
        await ack()
        await _handle_room(body, client, 1)

    @app.action("vm_room_2")
    async def vm_room_2(ack, body, client):
        await ack()
        await _handle_room(body, client, 2)

    @app.action("vm_room_3")
    async def vm_room_3(ack, body, client):
        await ack()
        await _handle_room(body, client, 3)

    @app.action("vm_leave")
    async def vm_leave(ack, body, client):
        await ack()
        uid = body["actions"][0]["value"]; actor = body["user"]["id"]
        if actor != uid: return
        sess = _sessions.get(uid)
        if not sess: return
        channel = sess["channel"]; ts = sess["ts"]; vm = sess["vm"]; world = sess["world"]
        final_depth = vm["depth"]; combo = vm.get("combo", 0)
        reward = max(0, int(final_depth*45 + len(vm["artifacts"])*140 + vm["keys"]*25 + vm["fragments"]*18 - len(vm["anomalies"])*60 + world["storm"]*30 + combo*20))
        await update_balance(uid, reward)
        vm["best_depth"] = max(vm["best_depth"], final_depth)
        vm["active"] = False; vm["runs"] += 1; vm["streak"] += 1
        vm.update({"depth":0,"clarity":vm["max_clarity"],"anomalies":[],"boons":[],"artifacts":[],"keys":0,"fragments":0,"synergy_cd":{},"last_synergy_log":"","combo":0})
        vm["last_log"] = f"You escape the Maze with {reward} horsenncy."
        save_state()
        await client.chat_update(channel=channel, ts=ts, text=f":cyclone: VoidMaze run complete! Depth {final_depth}, reward {reward} horsenncy.", blocks=[])
        _sessions.pop(uid, None)
