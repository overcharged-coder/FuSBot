import datetime
from slack_utils import header_block, section_block, divider_block, context_block

TOPIC_ALIASES = {
    "start": "start", "beginner": "start", "new": "start", "getting started": "start", "getting-started": "start",
    "economy": "economy", "money": "economy", "cash": "economy",
    "adventure": "adventure", "games": "adventure", "combat": "adventure", "grind": "adventure",
    "deep": "deep", "systems": "deep",
    "ai": "ai", "roast": "ai", "code": "ai", "hack": "ai",
    "admin": "admin", "setup": "admin", "mod": "admin", "moderation": "admin",
    "fun": "fun", "misc": "fun", "extras": "fun",
    "all": "all",
}


def normalize_topic(topic: str | None) -> str:
    text = (topic or "start").strip().lower()
    return TOPIC_ALIASES.get(text, "start")


def make_blocks(topic: str, user_id: str) -> list[dict]:
    topic = normalize_topic(topic)

    if topic == "economy":
        return [
            header_block("help • economy"),
            section_block("money, items, stocks, trading, and progression basics"),
            {"type": "section", "text": {"type": "mrkdwn", "text": "*Core Money*\n`/balance` see your horsenncy\n`/daily` claim free money\n`/recommend` or `/whatsnext` get your best next move\n`/work` do jobs\n`/give` send money to someone\n`/pray` gain prayer points\n`/leaderboard` richest players"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": "*Risk and Gambling*\n`/blackjack`\n`/coinflip`\n`/crime`\n`/slots`"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": "*Items, Market, and Player Trading*\n`/shop`\n`/buy`\n`/inventory`\n`/use`\n`/stocks`\n`/stocks_buy`\n`/stocks_sell`\n`/auction browse`\n`/auction sell`\n`/auction buy`"}},
            context_block("easy starter route: /daily → /work → /shop or /stocks"),
        ]

    if topic == "adventure":
        return [
            header_block("help • adventure"),
            section_block("creatures, teams, combat, and your core grinding routes"),
            {"type": "section", "text": {"type": "mrkdwn", "text": "*Creature Loop*\n`/hunt` get creatures\n`/fish` get fish and sea monsters\n`/team list` see your team\n`/team add` add a creature\n`/team remove` remove one\n`/battle` fight monsters"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": "*Big Progression Modes*\n`/dungeon` evolving dungeon run\n`/voidmaze` cosmic roguelite\n`/arena` auto-battler ladder\n`/lab` research lab"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": "*Account and Progress Tracking*\n`/profile`\n`/recommend` or `/whatsnext`\n`/achievements`\n`/quests`\n`/titles`\n`/collections`"}},
            context_block("easy starter route: /hunt or /fish → /team list → /battle → /dungeon"),
        ]

    if topic == "deep":
        return [
            header_block("help • deep systems"),
            section_block("the heavier systems once you want more than quick commands"),
            {"type": "section", "text": {"type": "mrkdwn", "text": "*Account Layer*\n`/profile` overview\n`/achievements` unlock board\n`/quests` daily goals\n`/quests_claim` claim rewards\n`/titles` unlocked titles\n`/title_equip` equip a title\n`/collections` account-wide collection progress"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": "*Social Layer*\n`/guild create`\n`/guild join`\n`/guild leave`\n`/guild info`\n`/guild deposit`\n`/guild upgrade`"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": "*High-Depth Modes*\n`/dungeon`\n`/voidmaze`\n`/arena`\n`/lab`\n`/hack`"}},
            context_block("this is the layer that ties the rest of the bot together"),
        ]

    if topic == "ai":
        return [
            header_block("help • ai and utility"),
            section_block("roast ai, codepad, hacking, images, and lichess"),
            {"type": "section", "text": {"type": "mrkdwn", "text": "*Roast AI*\n`/roast`\n`/data`\n`/autor`\n`/roastmode`\n`/stoproast`"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": "*Codepad and Hacking*\n`/code_new`\n`/code_edit`\n`/code_view`\n`/code_list`\n`/code_delete`\n`/code_run`\n`/hack`\n`/hack_chaos`\n`/hack_profile`\n`/hack_targets`\n`/hack_chaos_state`"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": "*Other AI and Live Stuff*\n`/img`\n`/lichess`\n`/lichess_game`\n`/lichess_stream`"}},
            context_block("good starter route: /roast or /code_list"),
        ]

    if topic == "admin":
        return [
            header_block("help • admin"),
            section_block("server onboarding and moderation tools"),
            {"type": "section", "text": {"type": "mrkdwn", "text": "*Server Setup*\n`/setup view`\n`/setup channel`\n`/setup tips`\n`/setup post`\n`/setup reset`"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": "*AutoMod*\n`/automod`\n`/automod_reset`\n`/automod_punishment`\n`/automod_slurs`\n`/automod_spam`\n`/automod_filters`\n`/automod_settings`"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": "*Recommended Order*\n1. run `/setup channel`\n2. run `/setup post`\n3. run `/help start` yourself and check the flow\n4. turn on automod only if you want it"}},
            context_block("admins should start with /setup view"),
        ]

    if topic == "fun":
        return [
            header_block("help • fun and extras"),
            section_block("side commands, casual stuff, and social commands"),
            {"type": "section", "text": {"type": "mrkdwn", "text": "*Casual Commands*\n`/afk`\n`/animal`\n`/badge`\n`/emojimixup`\n`/aki`\n`/img`"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": "*Interactive Games*\n`/battleship`\n`/battleship_resume`\n`/battleship_forfeit`\n`/battleship_stats`\n`/battleship_leaderboard`\n`/monopoly_start`\n`/monopoly_resume`\n`/monopoly_stop`"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": "*Extra Builders*\n`/rave`\n`/ravebg`"}},
            context_block("these are the side dishes, not the main grind"),
        ]

    if topic == "all":
        return [
            header_block("help • topic map"),
            section_block("use `/help <topic>` with one of these categories"),
            {"type": "section", "fields": [
                {"type": "mrkdwn", "text": "*Topics*\n`start`\n`economy`\n`adventure`\n`deep`\n`ai`\n`admin`\n`fun`\n`all`"},
                {"type": "mrkdwn", "text": "*Fast Examples*\n`/help start`\n`/help economy`\n`/help adventure`\n`/help deep`\n`/help ai`\n`/help admin`\n`/help fun`"},
            ]},
            {"type": "section", "text": {"type": "mrkdwn", "text": "*Best New User Route*\n`/profile` → `/recommend` → `/daily` → `/work` → `/help economy` → `/help adventure`"}},
            context_block("start with /help start if you're new"),
        ]

    return [
        header_block("help • getting started"),
        section_block(f"hey <@{user_id}>, this bot does a lot — here's the clean way to start without staring at the slash menu."),
        {"type": "section", "text": {"type": "mrkdwn", "text": "*First Commands to Try*\n`/profile` see your account\n`/balance` check your money\n`/recommend` or `/whatsnext` get your best next move\n`/daily` claim free horsenncy\n`/work` earn more\n`/help economy` or `/help adventure`"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": "*Popular Routes*\n*money route* — `/daily` → `/work` → `/shop` or `/stocks`\n*creature route* — `/hunt` or `/fish` → `/team list` → `/battle`\n*deep route* — `/dungeon` or `/voidmaze` or `/arena`\n*ai route* — `/roast` or `/code_list` → `/hack`\n*stuck?* — `/recommend` or `/whatsnext`"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": "*Help Topics*\n`/help economy`\n`/help adventure`\n`/help deep`\n`/help ai`\n`/help admin`\n`/help fun`"}},
    ]


STARTER_ROUTES = {
    "money": {
        "title": "money route",
        "desc": "fast start for economy and progression",
        "steps": ["/profile", "/recommend", "/daily", "/work", "/whatsnext", "/shop", "/help economy"],
    },
    "battle": {
        "title": "battle route",
        "desc": "build a team and start fighting things",
        "steps": ["/profile", "/recommend", "/hunt", "/team list", "/battle", "/whatsnext", "/help adventure"],
    },
    "ai": {
        "title": "ai route",
        "desc": "jump into the bot's ai side first",
        "steps": ["/recommend", "/roast", "/roastmode", "/code_list", "/hack", "/whatsnext", "/help ai"],
    },
}


def make_start_blocks(route_key: str, user_id: str) -> list[dict]:
    if route_key == "home":
        return [
            header_block("start here"),
            section_block(f"hey <@{user_id}> — pick the path you want and i'll give you the fastest route"),
            {"type": "section", "text": {"type": "mrkdwn", "text": "*available paths*\n:moneybag: money\n:crossed_swords: battle\n:robot_face: ai"}},
            {"type": "actions", "block_id": "start_route", "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "money", "emoji": True}, "action_id": "start_money", "value": "money"},
                {"type": "button", "text": {"type": "plain_text", "text": "battle", "emoji": True}, "action_id": "start_battle", "value": "battle", "style": "danger"},
                {"type": "button", "text": {"type": "plain_text", "text": "ai", "emoji": True}, "action_id": "start_ai", "value": "ai", "style": "primary"},
            ]},
        ]
    data = STARTER_ROUTES[route_key]
    steps = "\n".join(f"{i+1}. `{step}`" for i, step in enumerate(data["steps"]))
    return [
        header_block(data["title"]),
        section_block(data["desc"]),
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*do these in order*\n{steps}"}},
        context_block("finish this path first, then branch out"),
    ]


async def setup(app):
    @app.command("/help")
    async def help_cmd(ack, command, respond):
        await ack()
        topic = (command.get("text") or "").strip() or None
        uid = command["user_id"]
        blocks = make_blocks(topic, uid)
        await respond(blocks=blocks, text="Help")

    @app.command("/start")
    async def start_cmd(ack, command, respond):
        await ack()
        uid = command["user_id"]
        blocks = make_start_blocks("home", uid)
        await respond(blocks=blocks, text="Start here")

    async def _handle_start_route(ack, body, respond):
        await ack()
        uid = body["user"]["id"]
        route = body["actions"][0]["value"]
        if route not in STARTER_ROUTES:
            return
        blocks = make_start_blocks(route, uid)
        await respond(replace_original=True, blocks=blocks, text=STARTER_ROUTES[route]["title"])

    app.action("start_money")(_handle_start_route)
    app.action("start_battle")(_handle_start_route)
    app.action("start_ai")(_handle_start_route)
