from economy import get_user

try:
    from achievement import build_snapshot
except Exception:
    build_snapshot = None


def rarity_counts(animals):
    counts = {}
    if not isinstance(animals, list):
        return counts
    for animal in animals:
        if isinstance(animal, dict):
            rarity = str(animal.get("rarity") or animal.get("tier") or "unknown").lower()
        else:
            rarity = "unknown"
        counts[rarity] = counts.get(rarity, 0) + 1
    return counts


def compact_dict_lines(d: dict, limit: int = 12):
    if not d:
        return "none"
    items = sorted(d.items(), key=lambda x: (-x[1], x[0]))[:limit]
    return "\n".join(f"• {k}: `{v}`" for k, v in items)


async def setup(app):

    @app.command("/collections")
    async def collections_cmd(ack, command, client):
        await ack()
        import re as re_mod
        uid = command["user_id"]; channel = command["channel_id"]
        text = (command.get("text") or "").strip(); target_id = uid; mention = f"<@{uid}>"
        m = re_mod.search(r"<@([A-Z0-9]+)>", text)
        if m: target_id = m.group(1); mention = f"<@{target_id}>"
        data = get_user(target_id)
        snapshot = build_snapshot(target_id, data) if build_snapshot else None
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
        team_power = sum(int(animal.get("strength", 0) or 0) for animal in team if isinstance(animal, dict))
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
            f":books: *{mention}'s Collections*\n"
            f"your account-wide collector board\n\n"
            f"*Inventory*\n"
            f"total items: `{inv_total}`\n"
            f"unique entries: `{inv_unique}`\n"
            f"top items:\n{inv_items_text}\n\n"
            f"*Animals*\n"
            f"owned animals: `{len(owned_animals)}`\n"
            f"team size: `{len(team)}`\n"
            f"team power: `{team_power}`\n"
            f"rarities:\n{rarities_text}\n\n"
            f"*Special Finds*\n"
            f"dungeon relics: `{len(relics)}`\n"
            f"dungeon curses: `{len(curses)}`\n"
            f"void artifacts: `{len(artifacts)}`\n"
            f"lab breakthroughs: `{len(breakthroughs)}`\n"
            f"stock symbols owned: `{stock_symbols}`"
            f"{grade_section}"
        )
        await client.chat_postMessage(channel=channel, text=msg[:3000])
