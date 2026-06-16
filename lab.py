import random
from economy_shared import state, save_state
from economy import get_user, update_balance, get_balance, get_pray_boost

_sessions: dict[str, dict] = {}

BREAKTHROUGHS_DESC = {
    "Efficient Stock Algos": "Minor edge on market-related features and simulations.",
    "Dungeon Resonance Mapping": "Understanding of dungeon rifts improves flavor and future synergies.",
    "Arena Combat Analytics": "Deep statistics for Arena battles, enabling stronger builds.",
    "Prayer Wave Amplifier": "Theoretical boost to global prayer phenomena.",
    "Casino Edge Tuning": "Insights into gambling behaviors and odds manipulation.",
    "Meta-Currency Compression": "Research into densifying value flows across all systems."
}


def _lab_text(lab, world):
    bt_list = lab["breakthroughs"]
    bt_text = "\n".join(f"• *{n}* — {BREAKTHROUGHS_DESC.get(n,'Unknown effect.')}" for n in bt_list) if bt_list else "None yet."
    return "\n".join([
        ":alembic: *HORSEY RESEARCH LAB*",
        f"Level {lab['level']} | XP {lab['xp']}/100 | Stability {lab['stability']}/{lab['max_stability']}",
        f"Anomalies: {len(lab['anomalies'])} | Breakthroughs: {len(lab['breakthroughs'])}",
        f"World Instability: {world['instability']:.2f}",
        f"_{world['last_event']}_",
        f"\n{lab['last_log']}",
        f"\n*Breakthroughs:*\n{bt_text}",
    ])


def _lab_blocks(uid: str, lab: dict, world: dict) -> list[dict]:
    return [
        {"type": "section", "text": {"type": "mrkdwn", "text": _lab_text(lab, world)}},
        {"type": "actions", "elements": [
            {"type": "button", "text": {"type": "plain_text", "text": "Research"}, "action_id": "lab_research", "style": "primary", "value": uid},
            {"type": "button", "text": {"type": "plain_text", "text": "Experiment"}, "action_id": "lab_experiment", "value": uid},
            {"type": "button", "text": {"type": "plain_text", "text": "Stabilize"}, "action_id": "lab_stabilize", "value": uid},
            {"type": "button", "text": {"type": "plain_text", "text": "Leave"}, "action_id": "lab_leave", "style": "danger", "value": uid},
        ]},
    ]


async def _refresh(client, channel, ts, uid, lab, world):
    await client.chat_update(channel=channel, ts=ts, blocks=_lab_blocks(uid, lab, world), text="Lab")


async def setup(app):

    @app.command("/lab")
    async def lab_cmd(ack, command, client):
        await ack()
        uid = command["user_id"]; channel = command["channel_id"]
        user = get_user(uid); lab = user.setdefault("lab", {})
        for k, v in [("level",1),("xp",0),("stability",100),("max_stability",100),("anomalies",[]),
                     ("breakthroughs",[]),("queue",[]),("running",False),("last_log","The machinery hums as you enter.")]:
            lab.setdefault(k, v)
        world = state.setdefault("lab_world", {})
        for k, v in [("instability",0.0),("discoveries",0),("last_event","The labs are unusually calm.")]:
            world.setdefault(k, v)
        save_state()
        result = await client.chat_postMessage(channel=channel, blocks=_lab_blocks(uid, lab, world), text="Lab")
        _sessions[uid] = {"lab": lab, "world": world, "ts": result["ts"], "channel": channel}

    async def _get_sess(body):
        uid = body["actions"][0]["value"]; actor = body["user"]["id"]
        if actor != uid: return None, None, None, None, None
        sess = _sessions.get(uid)
        if not sess: return uid, None, None, None, None
        return uid, sess["lab"], sess["world"], sess["channel"], sess["ts"]

    @app.action("lab_research")
    async def lab_research(ack, body, client):
        await ack()
        uid, lab, world, channel, ts = await _get_sess(body)
        if lab is None: return
        fields = ["Economy", "Dungeonology", "Arena Theory", "Cosmic Luck"]
        field = random.choice(fields)
        base_xp = random.randint(18, 35); instability_gain = random.uniform(0.03, 0.09); stab_loss = random.randint(2, 7)
        lab["xp"] += base_xp; lab["stability"] = max(0, lab["stability"] - stab_loss); world["instability"] += instability_gain
        leveled = False
        while lab["xp"] >= 100:
            lab["xp"] -= 100; lab["level"] += 1; world["discoveries"] += 1; leveled = True
        bt_log = ""
        bt_chance = 0.06 + lab["level"] * 0.01 + world["instability"] * 0.02
        if random.random() < bt_chance:
            bt = random.choice(list(BREAKTHROUGHS_DESC.keys()))
            if bt not in lab["breakthroughs"]:
                lab["breakthroughs"].append(bt); bt_log = f" Breakthrough: *{bt}*."
            else: lab["xp"] += 20
        log = f"Researched *{field}* for {base_xp} XP, stability -{stab_loss}, instability +{instability_gain:.2f}."
        if leveled: log += f" Lab leveled to {lab['level']}."
        if bt_log: log += bt_log
        if lab["stability"] <= 0:
            lab["stability"] = 0
            if "Core Fracture" not in lab["anomalies"]: lab["anomalies"].append("Core Fracture")
            log += " The core fractures under pressure."
        lab["last_log"] = log; world["last_event"] = "A surge of research energy ripples across all labs."
        save_state(); await _refresh(client, channel, ts, uid, lab, world)

    @app.action("lab_experiment")
    async def lab_experiment(ack, body, client):
        await ack()
        uid, lab, world, channel, ts = await _get_sess(body)
        if lab is None: return
        user = get_user(uid); balance = user.get("balance", 0)
        if balance < 80:
            await client.chat_postEphemeral(channel=channel, user=uid, text="Not enough horsenncy to fund an experiment."); return
        stake = max(80, min(balance // 10, 600)); await update_balance(uid, -stake)
        r = random.random(); pray_boost = get_pray_boost(uid)
        if r < 0.22:
            mult = random.uniform(1.4, 2.6); gain = int(stake * mult * pray_boost); await update_balance(uid, gain)
            xp_gain = random.randint(10, 25); lab["xp"] += xp_gain; lab["stability"] = max(0, lab["stability"] - random.randint(4, 10))
            world["instability"] += 0.10; log = f"Experiment yields lucrative result. Gain {gain} horsenncy and {xp_gain} lab XP."
        elif r < 0.60:
            mult = random.uniform(0.8, 1.3); gain = int(stake * mult); await update_balance(uid, gain)
            lab["stability"] = max(0, lab["stability"] - random.randint(2, 6)); world["instability"] += 0.04
            log = f"Mildly successful experiment. Net result: {gain - stake:+} horsenncy."
        elif r < 0.88:
            loss = int(stake * random.uniform(0.4, 1.2)); loss = min(loss, user.get("balance", 0))
            await update_balance(uid, -loss); lab["stability"] = max(0, lab["stability"] - random.randint(5, 12))
            world["instability"] += 0.08; anomaly = random.choice(["Phantom Feedback","Quantum Noise","Harmonic Glitch"])
            lab["anomalies"].append(anomaly); log = f"Experiment misbehaves. Extra loss {loss} horsenncy, anomaly {anomaly}."
        else:
            extra_loss = min(int(stake * 2), user.get("balance", 0)); await update_balance(uid, -extra_loss)
            stab_crash = random.randint(15, 35); lab["stability"] = max(0, lab["stability"] - stab_crash)
            world["instability"] += 0.18; anomaly = random.choice(["Lab Explosion","Temporal Backdraft","Spatial Tear"])
            lab["anomalies"].append(anomaly); log = f"Catastrophic failure. Lose extra {extra_loss} horsenncy, stability -{stab_crash}, anomaly {anomaly}."
        if lab["stability"] <= 0 and "Core Fracture" not in lab["anomalies"]:
            lab["anomalies"].append("Core Fracture"); lab["stability"] = 0; log += " The fractured core screams silently."
        lab["last_log"] = log; world["last_event"] = "Experimental waves distort the lab complex."
        save_state(); await _refresh(client, channel, ts, uid, lab, world)

    @app.action("lab_stabilize")
    async def lab_stabilize(ack, body, client):
        await ack()
        uid, lab, world, channel, ts = await _get_sess(body)
        if lab is None: return
        if lab["stability"] >= lab["max_stability"]:
            lab["last_log"] = "Systems already at peak stability."; save_state()
            await _refresh(client, channel, ts, uid, lab, world); return
        cost_xp = random.randint(8, 18); heal = random.randint(12, 28); world_reduce = random.uniform(0.05, 0.18)
        if lab["xp"] < cost_xp:
            await client.chat_postEphemeral(channel=channel, user=uid, text="Not enough lab XP for stabilization."); return
        lab["xp"] -= cost_xp; lab["stability"] = min(lab["max_stability"], lab["stability"] + heal)
        world["instability"] = max(0.0, world["instability"] - world_reduce)
        removed = None
        if lab["anomalies"] and random.random() < 0.35:
            removed = random.choice(lab["anomalies"]); lab["anomalies"].remove(removed)
        log = f"Stabilization cycle. Stability +{heal}, instability -{world_reduce:.2f}."
        if removed: log += f" Anomaly {removed} neutralized."
        lab["last_log"] = log; world["last_event"] = "A stabilizing wave passes through the lab network."
        save_state(); await _refresh(client, channel, ts, uid, lab, world)

    @app.action("lab_leave")
    async def lab_leave(ack, body, client):
        await ack()
        uid = body["actions"][0]["value"]; actor = body["user"]["id"]
        if actor != uid: return
        sess = _sessions.pop(uid, None)
        if not sess: return
        channel = sess["channel"]; ts = sess["ts"]
        await client.chat_update(channel=channel, ts=ts, text=":alembic: You step away from the humming machines.", blocks=[])
