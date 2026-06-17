import datetime
from economy import get_user

try:
    from achievement import get_profile_meta, format_mastery_block, format_next_up, format_rare_unlocks
except Exception:
    get_profile_meta = None
    format_mastery_block = None
    format_next_up = None
    format_rare_unlocks = None


def parse_iso(ts):
    if not ts:
        return None
    try:
        return datetime.datetime.fromisoformat(ts)
    except Exception:
        return None


def format_remaining(ts) -> str:
    dt = parse_iso(ts)
    if not dt:
        return "Ready"
    remaining = dt - datetime.datetime.utcnow()
    if remaining.total_seconds() <= 0:
        return "Ready"
    total = int(remaining.total_seconds())
    h = total // 3600; m = (total % 3600) // 60; s = total % 60
    if h: return f"{h}h {m}m"
    if m: return f"{m}m {s}s"
    return f"{s}s"


def cooldown_from_last(ts, delta: datetime.timedelta) -> str:
    dt = parse_iso(ts)
    if not dt:
        return "Ready"
    return format_remaining((dt + delta).isoformat())


def bool_text(value: bool) -> str:
    return "Yes" if value else "No"


def protect_text(ts) -> str:
    dt = parse_iso(ts) if not isinstance(ts, datetime.datetime) else ts
    if dt and dt > datetime.datetime.utcnow():
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    return "Inactive"


def compact_number(n: int) -> str:
    try: n = int(n)
    except Exception: n = 0
    sign = "-" if n < 0 else ""; n = abs(n)
    if n >= 1_000_000_000: return f"{sign}{n/1_000_000_000:.1f}b"
    if n >= 1_000_000: return f"{sign}{n/1_000_000:.1f}m"
    if n >= 1_000: return f"{sign}{n/1_000:.1f}k"
    return f"{sign}{n}"


def fallback_meta(user_id: str, data: dict):
    balance = int(data.get("balance", 0) or 0)
    pray_points = int(data.get("pray", 0) or 0)
    inventory = data.get("inventory", {}) if isinstance(data.get("inventory"), dict) else {}
    owned_animals = data.get("owned_animals", []) if isinstance(data.get("owned_animals"), list) else []
    team = data.get("team", []) if isinstance(data.get("team"), list) else []
    dungeon = data.get("dungeon", {}) if isinstance(data.get("dungeon"), dict) else {}
    raid = data.get("raid", {}) if isinstance(data.get("raid"), dict) else {}
    arena = data.get("arena", {}) if isinstance(data.get("arena"), dict) else {}
    voidmaze = data.get("voidmaze", {}) if isinstance(data.get("voidmaze"), dict) else {}
    lab = data.get("lab", {}) if isinstance(data.get("lab"), dict) else {}
    hack = state_from_hack(user_id, data)
    team_power = sum(int(a.get("strength", 0) or 0) for a in team if isinstance(a, dict))
    snapshot = {
        "balance": balance, "pray_points": pray_points, "net_worth": balance,
        "inventory_unique": sum(1 for v in inventory.values() if int(v or 0) > 0),
        "inventory_total": sum(max(0, int(v or 0)) for v in inventory.values()),
        "owned_animals_count": len(owned_animals), "legendary_plus_animals": 0,
        "team_size": len(team), "team_power": team_power,
        "strongest_team_member_name": "None", "strongest_team_member_power": 0,
        "stock_symbols": len(data.get("stocks", {}) or {}),
        "stock_value": 0, "wealth_rank": None, "ranked_users": 0,
        "dungeon_active": bool(dungeon.get("active")),
        "dungeon_floor": int(dungeon.get("floor", 1) or 1),
        "dungeon_hp": int(dungeon.get("hp", 100) or 100),
        "dungeon_max_hp": int(dungeon.get("max_hp", 100) or 100),
        "dungeon_energy": int(dungeon.get("energy", 3) or 3),
        "dungeon_relics": len(dungeon.get("relics", [])) if isinstance(dungeon.get("relics"), list) else 0,
        "dungeon_curses": len(dungeon.get("curses", [])) if isinstance(dungeon.get("curses"), list) else 0,
        "raid_joined": bool(raid.get("joined")),
        "raid_damage": int(raid.get("damage", 0) or 0),
        "raid_relic_bonus": int(raid.get("relic_bonus", 0) or 0),
        "pvp_offense_bonus": int((data.get("pvp") or {}).get("offense_bonus", 0) or 0),
        "pvp_defense_bonus": int((data.get("pvp") or {}).get("defense_bonus", 0) or 0),
        "arena_rating": int(arena.get("rating", 0) or 0),
        "arena_xp": int(arena.get("xp", 0) or 0),
        "arena_crowns": int(arena.get("crowns", 0) or 0),
        "void_best_depth": int(voidmaze.get("best_depth", 0) or 0),
        "void_streak": int(voidmaze.get("streak", 0) or 0),
        "void_artifacts": len(voidmaze.get("artifacts", [])) if isinstance(voidmaze.get("artifacts"), list) else 0,
        "void_fragments": int(voidmaze.get("fragments", 0) or 0),
        "void_keys": int(voidmaze.get("keys", 0) or 0),
        "lab_level": int(lab.get("level", 0) or 0),
        "lab_xp": int(lab.get("xp", 0) or 0),
        "lab_stability": int(lab.get("stability", 0) or 0),
        "lab_breakthroughs": len(lab.get("breakthroughs", [])) if isinstance(lab.get("breakthroughs"), list) else 0,
        "hack_skill": int(hack.get("skill", 0) or 0),
        "hack_reputation": int(hack.get("reputation", 0) or 0),
        "hack_trace": int(hack.get("trace", 0) or 0),
        "active_modes": sum(1 for x in [balance > 0, len(inventory) > 0, len(owned_animals) > 0, bool(arena), bool(voidmaze), bool(lab), bool(hack)] if x),
        "ready_cooldowns": sum(1 for v in [
            cooldown_from_last(data.get("last_daily"), datetime.timedelta(days=1)),
            cooldown_from_last(data.get("last_work"), datetime.timedelta(hours=1)),
            cooldown_from_last(data.get("last_pray"), datetime.timedelta(minutes=10)),
            format_remaining(data.get("fish_cooldown")),
            format_remaining(data.get("hunt_cooldown")),
        ] if v == "Ready"),
        "roast_protection_until": parse_iso(data.get("roast_protection_until")),
    }
    return {"snapshot": snapshot, "summary": {"unlocked_count": 0, "total_count": 0, "completion": 0, "total_points": 0}, "title": "fresh spawn", "grades": [], "next_up": [], "rare_unlocked": []}


def state_from_hack(user_id: str, data: dict) -> dict:
    from economy_shared import state
    return state.get("hacker_profiles", {}).get(str(user_id), {})


def _build_profile_text(uid: str, data: dict, display_name: str) -> str:
    meta = get_profile_meta(uid, data) if get_profile_meta else fallback_meta(uid, data)
    snapshot = meta["snapshot"]
    summary = meta["summary"]
    grades = meta.get("grades", [])

    wealth_rank = f"#{snapshot['wealth_rank']}/{snapshot['ranked_users']}" if snapshot.get("wealth_rank") else "Unranked"
    ach_text = f"{summary['unlocked_count']}/{summary['total_count']} ({summary['completion']}%)" if summary["total_count"] else "not loaded"

    lines = [
        f"*:scroll: {display_name} — {meta['title']}*",
        f"Achievements: `{ach_text}` | Points: `{summary['total_points']}`",
        "",
        "*Overview*",
        f":gem: Net Worth: `{snapshot['net_worth']:,}` horsenncy | Rank: `{wealth_rank}`",
        f":ng_man: Active Modes: `{snapshot['active_modes']}`",
        "",
        "*Economy*",
        f":banknote: Balance: `{snapshot['balance']:,}` | Stocks: `{snapshot['stock_symbols']}` symbols | Prayer: `{snapshot['pray_points']}`",
        "",
        "*Collection*",
        f":briefcase: Inventory: `{snapshot['inventory_total']}` items | Animals: `{snapshot['owned_animals_count']}` | Team: `{snapshot['team_size']}/8` (Power: `{snapshot['team_power']:,}`)",
        "",
        "*Progression*",
        f":european_castle: Dungeon F{snapshot['dungeon_floor']} HP:{snapshot['dungeon_hp']}/{snapshot['dungeon_max_hp']} E:{snapshot['dungeon_energy']}",
        f":stadium: Arena: Rating `{snapshot['arena_rating']}` Crowns `{snapshot['arena_crowns']}`",
        f":cyclone: Void: Depth `{snapshot['void_best_depth']}` Streak `{snapshot['void_streak']}`",
        f":alembic: Lab Lvl `{snapshot['lab_level']}` | :wrench: Hack Skill `{snapshot['hack_skill']}` Rep `{snapshot['hack_reputation']}`",
        "",
        "*Cooldowns*",
        f":gift: Daily: `{cooldown_from_last(data.get('last_daily'), datetime.timedelta(days=1))}` | :briefcase: Work: `{cooldown_from_last(data.get('last_work'), datetime.timedelta(hours=1))}` | :pray: Pray: `{cooldown_from_last(data.get('last_pray'), datetime.timedelta(minutes=10))}`",
        f":fishing_pole_and_fish: Fish: `{format_remaining(data.get('fish_cooldown'))}` | :bow_and_arrow: Hunt: `{format_remaining(data.get('hunt_cooldown'))}` | Ready: `{snapshot['ready_cooldowns']}/5`",
        "",
        "*Status*",
        f":shield: Roast Prot: `{protect_text(snapshot.get('roast_protection_until') or data.get('roast_protection_until'))}` | Dungeon Relics: `{snapshot['dungeon_relics']}` Curses: `{snapshot['dungeon_curses']}`",
    ]

    if grades and format_mastery_block:
        lines.append("")
        lines.append(f"*Masteries*\n{format_mastery_block(grades)}")

    if meta.get("rare_unlocked") and format_rare_unlocks:
        lines.append("")
        lines.append(f"*Rare Unlocks*\n{format_rare_unlocks(meta['rare_unlocked'])}")

    if meta.get("next_up") and format_next_up:
        lines.append("")
        lines.append(f"*Next Up*\n{format_next_up(meta['next_up'])}")

    return "\n".join(lines)


async def setup(app):

    @app.command("/fus_profile")
    async def profile(ack, command, client, respond):
        await ack()
        import re as re_mod
        uid = command["user_id"]
        text = (command.get("text") or "").strip()
        parts = text.split(None, 1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "achievements":
            try:
                from achievement import get_profile_meta, TIER_ORDER, TIER_EMOJIS, TIER_LABELS, format_mastery_block, format_rare_unlocks, format_next_up
            except Exception:
                await respond(text="Achievement module not available."); return
            channel = command["channel_id"]
            target_id = uid; mention = f"<@{uid}>"
            m = re_mod.search(r"<@([A-Z0-9]+)>", rest)
            if m: target_id = m.group(1); mention = f"<@{target_id}>"
            meta = get_profile_meta(target_id)
            snapshot = meta["snapshot"]; summary = meta["summary"]; results = meta["results"]; grades = meta["grades"]
            wealth_text = f"#{snapshot['wealth_rank']}/{snapshot['ranked_users']}" if snapshot["wealth_rank"] else "Unranked"
            tier_sections = []
            for tier in reversed(TIER_ORDER):
                unlocked = [a for a in results if a["unlocked"] and a["tier"] == tier]
                if unlocked:
                    tier_sections.append(f"{TIER_EMOJIS[tier]} *{TIER_LABELS[tier]}*: " + " ".join(f"{a['emoji']}{a['name']}" for a in unlocked))
            in_progress = sorted([a for a in results if not a["unlocked"]], key=lambda a: -a["percent"])[:5]
            progress_lines = "\n".join(f"• {a['emoji']} *{a['name']}* {a['percent']}% — {a['progress_text']}" for a in in_progress)
            text_out = (
                f":trophy: *{mention}'s Achievements*\n"
                f"Title: `{meta['title']}`\n"
                f"Unlocked: `{summary['unlocked_count']}/{summary['total_count']}` ({summary['completion']}%) | Points: `{summary['total_points']}`\n"
                f"Net Worth: `{snapshot['net_worth']:,}` | Rank: `{wealth_text}` | Active Modes: `{snapshot['active_modes']}`\n\n"
                f"*Masteries:*\n{format_mastery_block(grades)}\n\n"
                f"*Unlocks:*\n{chr(10).join(tier_sections) if tier_sections else 'None yet'}\n\n"
                f"*Next Up:*\n{progress_lines or 'All unlocked!'}\n\n"
                f"*Rare Unlocks:*\n{format_rare_unlocks(meta['rare_unlocked'])}"
            )
            await client.chat_postMessage(channel=channel, text=text_out[:3000])

        elif sub == "collections":
            try:
                from collection import rarity_counts, compact_dict_lines, build_snapshot as coll_snapshot
            except Exception:
                coll_snapshot = None; rarity_counts = lambda x: {}; compact_dict_lines = lambda d: "n/a"
            channel = command["channel_id"]
            target_id = uid; mention = f"<@{uid}>"
            m = re_mod.search(r"<@([A-Z0-9]+)>", rest)
            if m: target_id = m.group(1); mention = f"<@{target_id}>"
            data = get_user(target_id)
            snapshot = coll_snapshot(target_id, data) if coll_snapshot else None
            inventory = data.get("inventory", {}) if isinstance(data.get("inventory", {}), dict) else {}
            owned_animals = data.get("owned_animals", []) if isinstance(data.get("owned_animals", []), list) else []
            team = data.get("team", []) if isinstance(data.get("team", []), list) else []
            dungeon = data.get("dungeon", {}) if isinstance(data.get("dungeon", {}), dict) else {}
            voidmaze = data.get("voidmaze", {}) if isinstance(data.get("voidmaze", {}), dict) else {}
            lab = data.get("lab", {}) if isinstance(data.get("lab", {}), dict) else {}
            stocks = data.get("stocks", {}) if isinstance(data.get("stocks", {}), dict) else {}
            inv_unique = sum(1 for qty in inventory.values() if int(qty or 0) > 0)
            inv_total = sum(max(0, int(qty or 0)) for qty in inventory.values())
            animal_counts = rarity_counts(owned_animals)
            team_power = sum(int(a.get("strength", 0) or 0) for a in team if isinstance(a, dict))
            relics = dungeon.get("relics", []) if isinstance(dungeon.get("relics", []), list) else []
            curses = dungeon.get("curses", []) if isinstance(dungeon.get("curses", []), list) else []
            artifacts = voidmaze.get("artifacts", []) if isinstance(voidmaze.get("artifacts", []), list) else []
            breakthroughs = lab.get("breakthroughs", []) if isinstance(lab.get("breakthroughs", []), list) else []
            stock_symbols = sum(1 for _, amount in stocks.items() if int(amount or 0) > 0)
            inv_items_text = compact_dict_lines({k: int(v or 0) for k, v in inventory.items() if int(v or 0) > 0})
            rarities_text = compact_dict_lines(animal_counts)
            grade_section = ""
            if snapshot:
                grade_section = (
                    f"\n*Collector Grade*\n"
                    f"inventory score base: `{snapshot['inventory_unique']}`\n"
                    f"animal count: `{snapshot['owned_animals_count']}`\n"
                    f"legendary+ animals: `{snapshot['legendary_plus_animals']}`\n"
                    f"strongest member: `{snapshot['strongest_team_member_name']}`"
                )
            msg = (
                f":books: *{mention}'s Collections*\n\n"
                f"*Inventory*\ntotal: `{inv_total}` | unique: `{inv_unique}`\ntop items:\n{inv_items_text}\n\n"
                f"*Animals*\nowned: `{len(owned_animals)}` | team: `{len(team)}` | power: `{team_power}`\nrarities:\n{rarities_text}\n\n"
                f"*Special Finds*\nrelics: `{len(relics)}` | curses: `{len(curses)}` | void artifacts: `{len(artifacts)}` | lab breakthroughs: `{len(breakthroughs)}` | stocks: `{stock_symbols}`"
                f"{grade_section}"
            )
            await client.chat_postMessage(channel=channel, text=msg[:3000])

        else:
            target_id = uid; display_name = f"<@{uid}>"
            m = re_mod.search(r"<@([A-Z0-9]+)>", text)
            if m: target_id = m.group(1); display_name = f"<@{target_id}>"
            data = get_user(target_id)
            profile_text = _build_profile_text(target_id, data, display_name)
            await respond(text=profile_text)
