import datetime

from economy import get_user
from economy_shared import state, save_state


def guild_root():
    return state.setdefault("guild_system_v1", {"next_id": 1, "guilds": {}, "user_to_guild": {}})


def user_guild_id(uid: str):
    return guild_root()["user_to_guild"].get(str(uid))


def get_guild(guild_id):
    return guild_root()["guilds"].get(str(guild_id))


def member_count(guild_data: dict) -> int:
    return len(guild_data.get("members", [])) if isinstance(guild_data.get("members", []), list) else 0


def guild_power(guild_data: dict) -> int:
    total = 0
    for uid in guild_data.get("members", []):
        data = get_user(str(uid))
        team = data.get("team", []) if isinstance(data.get("team", []), list) else []
        total += sum(int(animal.get("strength", 0) or 0) for animal in team if isinstance(animal, dict))
    return total


async def setup(app):

    @app.command("/guild_create")
    async def guild_create(ack, command, client):
        await ack()
        uid = command["user_id"]; channel = command["channel_id"]
        name = (command.get("text") or "").strip()
        if not name or len(name) < 3 or len(name) > 32:
            await client.chat_postEphemeral(channel=channel, user=uid, text="usage: `/guild_create <name>` (3-32 chars)"); return
        if user_guild_id(uid):
            await client.chat_postEphemeral(channel=channel, user=uid, text="youre already in a guild"); return
        root = guild_root(); gid = root["next_id"]; root["next_id"] += 1
        root["guilds"][str(gid)] = {
            "id": gid, "name": name, "owner_id": uid, "members": [uid],
            "bank": 0, "level": 1, "xp": 0, "created_at": datetime.datetime.utcnow().isoformat(),
        }
        root["user_to_guild"][uid] = gid; save_state()
        await client.chat_postMessage(channel=channel, text=f"guild created: *{name}* with id `{gid}`")

    @app.command("/guild_join")
    async def guild_join(ack, command, client):
        await ack()
        uid = command["user_id"]; channel = command["channel_id"]
        text = (command.get("text") or "").strip()
        try:
            gid = int(text)
        except ValueError:
            await client.chat_postEphemeral(channel=channel, user=uid, text="usage: `/guild_join <guild_id>`"); return
        if user_guild_id(uid):
            await client.chat_postEphemeral(channel=channel, user=uid, text="leave your current guild first"); return
        guild_data = get_guild(gid)
        if not guild_data:
            await client.chat_postEphemeral(channel=channel, user=uid, text="that guild doesnt exist"); return
        if uid not in guild_data["members"]:
            guild_data["members"].append(uid)
        guild_root()["user_to_guild"][uid] = gid; save_state()
        await client.chat_postMessage(channel=channel, text=f"you joined *{guild_data['name']}*")

    @app.command("/guild_leave")
    async def guild_leave(ack, command, client):
        await ack()
        uid = command["user_id"]; channel = command["channel_id"]
        root = guild_root(); gid = user_guild_id(uid)
        if not gid:
            await client.chat_postEphemeral(channel=channel, user=uid, text="youre not in a guild"); return
        guild_data = get_guild(gid)
        if not guild_data:
            root["user_to_guild"].pop(uid, None); save_state()
            await client.chat_postMessage(channel=channel, text="your guild link was cleaned up"); return
        if uid == str(guild_data.get("owner_id")) and member_count(guild_data) > 1:
            await client.chat_postEphemeral(channel=channel, user=uid, text="transfer ownership or disband after everyone leaves"); return
        guild_data["members"] = [m for m in guild_data.get("members", []) if m != uid]
        root["user_to_guild"].pop(uid, None)
        if not guild_data["members"]:
            root["guilds"].pop(str(gid), None)
        save_state()
        await client.chat_postMessage(channel=channel, text="you left the guild")

    @app.command("/guild_info")
    async def guild_info(ack, command, client):
        await ack()
        uid = command["user_id"]; channel = command["channel_id"]
        text = (command.get("text") or "").strip()
        gid = None
        if text:
            try: gid = int(text)
            except ValueError: pass
        if not gid:
            gid = user_guild_id(uid)
        if not gid:
            await client.chat_postEphemeral(channel=channel, user=uid, text="youre not in a guild and didnt provide a guild id"); return
        guild_data = get_guild(gid)
        if not guild_data:
            await client.chat_postEphemeral(channel=channel, user=uid, text="that guild doesnt exist"); return
        owner_id = guild_data.get("owner_id", "?")
        members = guild_data.get("members", [])[:15]
        member_list = "\n".join(f"• <@{m}>" for m in members) or "none"
        power = guild_power(guild_data)
        msg = (
            f":classical_building: *{guild_data['name']}* (id `{guild_data['id']}`)\n"
            f"owner: <@{owner_id}>\n"
            f"members: `{member_count(guild_data)}`\n"
            f"level: `{guild_data.get('level', 1)}`\n"
            f"xp: `{guild_data.get('xp', 0)}`\n"
            f"bank: `{guild_data.get('bank', 0):,}` horsenncy\n"
            f"power: `{power:,}`\n\n"
            f"*Roster:*\n{member_list}"
        )
        await client.chat_postMessage(channel=channel, text=msg)

    @app.command("/guild_deposit")
    async def guild_deposit(ack, command, client):
        await ack()
        uid = command["user_id"]; channel = command["channel_id"]
        text = (command.get("text") or "").strip()
        try:
            amount = int(text)
            if amount < 1: raise ValueError
        except ValueError:
            await client.chat_postEphemeral(channel=channel, user=uid, text="usage: `/guild_deposit <amount>`"); return
        gid = user_guild_id(uid)
        if not gid:
            await client.chat_postEphemeral(channel=channel, user=uid, text="youre not in a guild"); return
        guild_data = get_guild(gid); data = get_user(uid)
        balance = int(data.get("balance", 0) or 0)
        if amount > balance:
            await client.chat_postEphemeral(channel=channel, user=uid, text="not enough horsenncy"); return
        data["balance"] = balance - amount
        guild_data["bank"] = int(guild_data.get("bank", 0) or 0) + amount
        guild_data["xp"] = int(guild_data.get("xp", 0) or 0) + max(1, amount // 100)
        save_state()
        await client.chat_postMessage(channel=channel, text=f"deposited `{amount}` horsenncy into *{guild_data['name']}*")

    @app.command("/guild_upgrade")
    async def guild_upgrade(ack, command, client):
        await ack()
        uid = command["user_id"]; channel = command["channel_id"]
        gid = user_guild_id(uid)
        if not gid:
            await client.chat_postEphemeral(channel=channel, user=uid, text="youre not in a guild"); return
        guild_data = get_guild(gid)
        if str(uid) != str(guild_data.get("owner_id")):
            await client.chat_postEphemeral(channel=channel, user=uid, text="only the guild owner can upgrade it"); return
        level = int(guild_data.get("level", 1) or 1); cost = level * 5000
        bank = int(guild_data.get("bank", 0) or 0)
        if bank < cost:
            await client.chat_postEphemeral(channel=channel, user=uid, text=f"you need `{cost}` guild bank horsenncy for the next upgrade"); return
        guild_data["bank"] = bank - cost; guild_data["level"] = level + 1; save_state()
        await client.chat_postMessage(channel=channel, text=f"*{guild_data['name']}* upgraded to level `{guild_data['level']}`")
