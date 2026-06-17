from economy import get_user
from economy_shared import save_state

try:
    from achievement import get_profile_meta
except Exception:
    get_profile_meta = None


def normalize(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def unlocked_titles(uid: str):
    data = get_user(uid)
    titles = ["fresh spawn"]
    if get_profile_meta:
        meta = get_profile_meta(uid, data)
        title = meta.get("title")
        if title:
            titles.append(title)
        unlocked_ids = {a["id"] for a in meta.get("results", []) if a.get("unlocked")}
        mapping = {
            "starter_wallet": "coin flipper",
            "five_figures": "stable banker",
            "capital_engine": "market titan",
            "pack_starter": "rookie tamer",
            "creature_curator": "beast collector",
            "menagerie_lord": "menagerie lord",
            "full_squad": "squad captain",
            "alpha_pack": "pack alpha",
            "rare_bloodline": "rare bloodline",
            "deep_delver": "deep delver",
            "worldbreaker": "worldbreaker",
            "crown_duelist": "crown duelist",
            "abyss_walker": "abyss walker",
            "fracture_scholar": "fracture scholar",
            "ghost_operator": "ghost operator",
            "all_terrain": "all-terrain user",
            "all_rounder": "all-rounder",
            "horselord_prime": "horselord prime",
        }
        for achievement_id, title_name in mapping.items():
            if achievement_id in unlocked_ids:
                titles.append(title_name)
    else:
        balance = int(data.get("balance", 0) or 0)
        if balance >= 10000:
            titles.append("stable banker")
    seen = set(); out = []
    for item in titles:
        key = normalize(item)
        if key and key not in seen:
            seen.add(key); out.append(item)
    return out


async def setup(app):

    @app.command("/fus_titles")
    async def titles_cmd(ack, command, client):
        await ack()
        import re as re_mod
        uid = command["user_id"]; channel = command["channel_id"]
        text = (command.get("text") or "").strip()
        parts = text.split(None, 1)
        action = parts[0].lower() if parts else ""
        arg = parts[1].strip() if len(parts) > 1 else ""

        if action == "equip":
            title_input = arg
            if not title_input:
                await client.chat_postEphemeral(channel=channel, user=uid, text="usage: `/fus_titles equip <title name>`"); return
            data = get_user(uid); titles = unlocked_titles(uid); wanted = normalize(title_input)
            match = next((t for t in titles if normalize(t) == wanted), None)
            if not match:
                await client.chat_postEphemeral(channel=channel, user=uid, text="that title isnt unlocked for you"); return
            data["equipped_title"] = match; save_state()
            await client.chat_postMessage(channel=channel, text=f"equipped title set to `{match}`")

        else:
            target_id = uid; mention = f"<@{uid}>"
            m = re_mod.search(r"<@([A-Z0-9]+)>", text)
            if m: target_id = m.group(1); mention = f"<@{target_id}>"
            data = get_user(target_id); titles = unlocked_titles(target_id)
            equipped = data.get("equipped_title") or titles[0]
            lines = "\n".join(f"• {t}" for t in titles[:25])
            msg = (
                f":medal: *{mention}'s Titles*\n"
                f"equipped: `{equipped}`\n"
                f"unlocked: `{len(titles)}`\n\n"
                f"{lines}\n\n_use `/fus_titles equip <title>` to equip one_"
            )
            await client.chat_postMessage(channel=channel, text=msg)
