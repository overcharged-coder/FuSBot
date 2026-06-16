import datetime

from economy_shared import state, save_state


def setup_root():
    return state.setdefault("server_setup_v2", {})


def workspace_setup_data():
    root = setup_root()
    key = "workspace"
    if key not in root:
        root[key] = {
            "onboarding_channel_id": None,
            "tips_enabled": True,
            "last_posted_at": None,
            "created_at": datetime.datetime.utcnow().isoformat(),
        }
        save_state()
    return root[key]


def onboarding_text(config: dict) -> str:
    tips_section = ""
    if config.get("tips_enabled", True):
        tips_section = "\n\n*Starter Tip:* new people should try `/profile`, `/daily`, `/work`, and `/help adventure` first"
    return (
        ":wave: *welcome to FuSBot*\n"
        "this bot does a lot, so here's the clean starting point before you mash `/` and get lost\n\n"
        "*Start Here:*\n"
        "`/help start` for the beginner guide\n"
        "`/profile` to see your account\n"
        "`/balance` to check money\n"
        "`/daily` and `/work` to start earning\n\n"
        "*Best Starter Routes:*\n"
        "*money* — `/daily` → `/work` → `/shop` or `/stocks`\n"
        "*creatures* — `/hunt` or `/fish` → `/team list` → `/battle`\n"
        "*deep modes* — `/dungeon` or `/voidmaze` or `/arena`\n"
        "*ai* — `/roast` or `/code_list` → `/hack`\n\n"
        "*Need More Help?*\n"
        "`/help economy` `/help adventure` `/help deep` `/help ai` `/help fun`"
        + tips_section
    )


def setup_view_text(config: dict) -> str:
    channel_text = f"<#{config['onboarding_channel_id']}>" if config.get("onboarding_channel_id") else "not set"
    return (
        ":wrench: *FuSBot Workspace Setup*\n\n"
        f"onboarding channel: {channel_text}\n"
        f"tips enabled: `{'yes' if config.get('tips_enabled', True) else 'no'}`\n"
        f"last onboarding post: `{config.get('last_posted_at') or 'never'}`\n\n"
        "*Recommended Flow:*\n"
        "1. run `/setup_channel <channel_id>`\n"
        "2. run `/setup_post`\n"
        "3. test `/help start`\n"
        "4. optionally configure automod\n\n"
        "*Useful Admin Commands:*\n"
        "`/setup_view` `/setup_channel` `/setup_tips` `/setup_post` `/setup_reset`"
    )


async def setup(app):

    @app.command("/setup_view")
    async def setup_view(ack, command, client):
        await ack()
        uid = command["user_id"]; channel = command["channel_id"]
        config = workspace_setup_data()
        await client.chat_postEphemeral(channel=channel, user=uid, text=setup_view_text(config))

    @app.command("/setup_channel")
    async def setup_channel(ack, command, client):
        await ack()
        uid = command["user_id"]; channel = command["channel_id"]
        text = (command.get("text") or "").strip()
        if not text:
            await client.chat_postEphemeral(channel=channel, user=uid, text="usage: `/setup_channel <channel_id>` — paste the channel ID"); return
        import re as re_mod
        m = re_mod.search(r"<#([A-Z0-9]+)>", text)
        channel_id = m.group(1) if m else text.strip()
        config = workspace_setup_data(); config["onboarding_channel_id"] = channel_id; save_state()
        await client.chat_postEphemeral(channel=channel, user=uid, text=f"onboarding channel set to <#{channel_id}>")

    @app.command("/setup_tips")
    async def setup_tips(ack, command, client):
        await ack()
        uid = command["user_id"]; channel = command["channel_id"]
        text = (command.get("text") or "").strip().lower()
        if text not in ("on", "off", "true", "false", "1", "0", "yes", "no"):
            await client.chat_postEphemeral(channel=channel, user=uid, text="usage: `/setup_tips on` or `/setup_tips off`"); return
        enabled = text in ("on", "true", "1", "yes")
        config = workspace_setup_data(); config["tips_enabled"] = enabled; save_state()
        await client.chat_postEphemeral(channel=channel, user=uid, text=f"onboarding tips are now `{'on' if enabled else 'off'}`")

    @app.command("/setup_post")
    async def setup_post(ack, command, client):
        await ack()
        uid = command["user_id"]; channel = command["channel_id"]
        config = workspace_setup_data()
        target_channel = config.get("onboarding_channel_id") or channel
        text = onboarding_text(config)
        await client.chat_postMessage(channel=target_channel, text=text)
        config["last_posted_at"] = datetime.datetime.utcnow().isoformat(); save_state()
        notice = "posted the onboarding guide here" if target_channel == channel else f"posted the onboarding guide in <#{target_channel}>"
        await client.chat_postEphemeral(channel=channel, user=uid, text=notice)

    @app.command("/setup_reset")
    async def setup_reset(ack, command, client):
        await ack()
        uid = command["user_id"]; channel = command["channel_id"]
        root = setup_root(); root.pop("workspace", None); save_state()
        await client.chat_postEphemeral(channel=channel, user=uid, text="workspace setup data reset")
