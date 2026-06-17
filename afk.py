import datetime
from economy_shared import state, save_state
from slack_utils import header_block, section_block

MAX_PINGS = 25


def _ts_to_relative(unix_ts: int) -> str:
    now = int(datetime.datetime.utcnow().timestamp())
    diff = now - unix_ts
    if diff < 60:
        return f"{diff}s ago"
    if diff < 3600:
        return f"{diff // 60}m ago"
    if diff < 86400:
        return f"{diff // 3600}h ago"
    return f"{diff // 86400}d ago"


async def setup(app):
    state.setdefault("afk", {})

    @app.command("/fus_afk")
    async def afk_cmd(ack, command, respond):
        await ack()
        uid = command["user_id"]
        msg = (command.get("text") or "").strip() or "AFK"

        state.setdefault("afk", {})
        state["afk"][uid] = {
            "message": msg,
            "since": int(datetime.datetime.utcnow().timestamp()),
            "pings": [],
        }
        save_state()

        blocks = [
            header_block("AFK Enabled"),
            section_block(f"*Message:* {msg}\nAFK clears automatically when you speak."),
        ]
        await respond(blocks=blocks, text="AFK enabled", response_type="ephemeral")

    @app.event("message")
    async def afk_message_handler(event, client, say):
        uid = event.get("user")
        if not uid or event.get("bot_id"):
            return

        afk = state.setdefault("afk", {})
        text = event.get("text") or ""
        channel = event["channel"]
        ts = event.get("ts", "")
        touched = False

        if uid in afk:
            data = afk.pop(uid)
            touched = True
            since_str = _ts_to_relative(data["since"])
            blocks = [
                header_block("Welcome back"),
                section_block(f"You were AFK {since_str}."),
                {"type": "actions", "elements": [
                    {"type": "button", "text": {"type": "plain_text", "text": "Show Pings"}, "action_id": "afk_show_pings",
                     "value": "|".join(data["pings"][:MAX_PINGS])[:2000]},
                ]},
            ]
            try:
                await client.chat_postMessage(channel=channel, thread_ts=ts, blocks=blocks, text="Welcome back")
            except Exception:
                await say(text="Welcome back! You were AFK.")

        import re
        mentioned_ids = re.findall(r"<@([A-Z0-9]+)>", text)
        for mid in mentioned_ids:
            if mid not in afk:
                continue
            data = afk[mid]
            entry = f"<@{uid}> in <#{channel}>"
            if len(data["pings"]) < MAX_PINGS:
                data["pings"].append(entry)
                touched = True
            since_str = _ts_to_relative(data["since"])
            blocks = [
                section_block(f"<@{mid}> is currently AFK\n*Reason:* {data['message']}\n*Since:* {since_str}"),
            ]
            try:
                await client.chat_postMessage(channel=channel, thread_ts=ts, blocks=blocks, text=f"<@{mid}> is AFK")
            except Exception:
                pass

        if touched:
            save_state()

    @app.action("afk_show_pings")
    async def show_pings(ack, body, client):
        await ack()
        uid = body["user"]["id"]
        pings_raw = body["actions"][0].get("value", "")
        pings = [p for p in pings_raw.split("|") if p] if pings_raw else []
        if not pings:
            text = "No one pinged you while AFK :relieved:"
        else:
            text = "*Pings while AFK:*\n" + "\n".join(f"• {p}" for p in pings)
        try:
            await client.chat_postEphemeral(channel=body["container"]["channel_id"], user=uid, text=text)
        except Exception:
            pass
