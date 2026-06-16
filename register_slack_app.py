"""
Registers all slash commands, scopes, and event subscriptions for the Slack app
in one API call using the App Manifest API.

Requirements:
  1. SLACK_APP_ID     — found at api.slack.com/apps → Basic Information → App ID
  2. SLACK_CONFIG_TOKEN — a config-level token with the `app_configurations:write` scope
     Get one at: api.slack.com/apps → Your App → Basic Information
                 → App-Level Tokens → Generate Token → add scope `app_configurations:write`
     It starts with xoxe.xoxp-...

Run once:
  python register_slack_app.py
"""

import os, json, sys
import requests
from dotenv import load_dotenv

load_dotenv()

APP_ID = os.getenv("SLACK_APP_ID", "").strip()
CONFIG_TOKEN = os.getenv("SLACK_CONFIG_TOKEN", "").strip()

if not APP_ID or not CONFIG_TOKEN:
    print("ERROR: set SLACK_APP_ID and SLACK_CONFIG_TOKEN in your .env file")
    print("  SLACK_APP_ID      → api.slack.com/apps → Basic Information → App ID")
    print("  SLACK_CONFIG_TOKEN → Basic Information → App-Level Tokens → Generate with app_configurations:write")
    sys.exit(1)

COMMANDS = [
    # ── Core ──────────────────────────────────────────────────────────────────
    ("/roast",              "Roast someone",                   "@user [or message]"),
    ("/data",               "View memory profile for a user",  "[@user]"),
    ("/autor",              "Toggle auto-roast in this channel","on | off"),
    ("/roastmode",          "Set your roast mode",             "fast | deep | adjustable"),
    ("/stoproast",          "Stop roast mode",                 ""),
    ("/help",               "Show help",                       "[topic]"),
    ("/start",              "Beginner guide",                  ""),
    ("/recommend",          "Get a personalised activity recommendation", ""),
    ("/whatsnext",          "See what to do next",             ""),
    # ── Economy ───────────────────────────────────────────────────────────────
    ("/balance",            "Check your balance",              "[@user]"),
    ("/daily",              "Claim your daily reward",         ""),
    ("/work",               "Work for horsenncy",              ""),
    ("/give",               "Send horsenncy to someone",       "@user <amount>"),
    ("/coinflip",           "Flip a coin bet",                 "<amount> [heads|tails]"),
    ("/pray",               "Pray for a boost",                ""),
    ("/leaderboard",        "Top balances",                    ""),
    ("/slots",              "Play the slots",                  "<amount>"),
    ("/blackjack",          "Play blackjack",                  "<amount>"),
    ("/crime",              "Commit a crime for money",        ""),
    ("/shop",               "Browse the shop",                 ""),
    ("/buy",                "Buy a shop item",                 "<item_name> [amount]"),
    ("/inventory",          "View your inventory",             "[@user]"),
    ("/use",                "Use an inventory item",           "<item_name>"),
    # ── Stocks ────────────────────────────────────────────────────────────────
    ("/stocks",             "View stock prices",               ""),
    ("/stocks_buy",         "Buy stocks",                      "<symbol> <amount>"),
    ("/stocks_sell",        "Sell stocks",                     "<symbol> <amount>"),
    # ── Animals / Team ────────────────────────────────────────────────────────
    ("/animal",             "Get a random animal fact",        ""),
    ("/hunt",               "Hunt for animals",                ""),
    ("/fish",               "Go fishing",                      ""),
    ("/battle",             "Battle with your team",           "[@user]"),
    ("/team",               "Manage your team",                "list | add <name> | remove <name>"),
    # ── Profile / Social ──────────────────────────────────────────────────────
    ("/profile",            "View your profile",               "[@user]"),
    ("/achievements",       "View achievements",               "[@user]"),
    ("/collections",        "View your collections",           "[@user]"),
    ("/quests",             "View your quest board",           "[@user]"),
    ("/quests_claim",       "Claim a completed quest",         "<slot 1-3>"),
    ("/titles",             "View unlocked titles",            "[@user]"),
    ("/title_equip",        "Equip a title",                   "<title>"),
    ("/badge",              "View or manage badges",           "[@user]"),
    # ── Deep Modes ────────────────────────────────────────────────────────────
    ("/dungeon",            "Enter the dungeon",               ""),
    ("/voidmaze",           "Enter the void maze",             ""),
    ("/arena",              "Enter the arena",                 ""),
    ("/arena_buy",          "Buy an arena upgrade",            "<item>"),
    ("/arena_setteam",      "Set your arena team",             "<names...>"),
    ("/lab",                "Enter the lab",                   ""),
    # ── Hack ──────────────────────────────────────────────────────────────────
    ("/hack",               "Start a hack run",                ""),
    ("/hack_chaos",         "Trigger hack chaos",              ""),
    ("/hack_profile",       "View your hack profile",          "[@user]"),
    ("/hack_targets",       "List hack targets",               ""),
    ("/hack_chaos_state",   "View global chaos state",         ""),
    # ── Battleship ────────────────────────────────────────────────────────────
    ("/battleship",         "Start a battleship game",         "[@opponent | ai [easy|normal|hard|god]]"),
    ("/bs_place",           "Place your next ship",            "<colrow> [r|d]  e.g. A0 r"),
    ("/bs_fire",            "Fire at a coordinate",            "<colrow>  e.g. B5"),
    ("/bs_status",          "Show your boards",                ""),
    ("/bs_forfeit",         "Forfeit the battleship game",     ""),
    ("/bs_resume",          "Resume a saved battleship game",  ""),
    ("/bs_stats",           "View battleship stats",           "[@user]"),
    ("/bs_leaderboard",     "Battleship ELO leaderboard",      ""),
    # ── Monopoly ──────────────────────────────────────────────────────────────
    ("/monopoly_start",     "Start a monopoly game",           "[@opponent]"),
    ("/monopoly_stop",      "Stop the monopoly game here",     ""),
    ("/monopoly_resume",    "Resume a saved monopoly game",    ""),
    # ── Guilds ────────────────────────────────────────────────────────────────
    ("/guild_create",       "Create a guild",                  "<name>"),
    ("/guild_join",         "Join a guild",                    "<guild_id>"),
    ("/guild_leave",        "Leave your guild",                ""),
    ("/guild_info",         "View guild info",                 "[guild_id]"),
    ("/guild_deposit",      "Deposit into guild bank",         "<amount>"),
    ("/guild_upgrade",      "Upgrade your guild",              ""),
    # ── Auction House ─────────────────────────────────────────────────────────
    ("/auction_sell",       "List an item on the auction house","<item> <amount> <price_each>"),
    ("/auction_browse",     "Browse auction listings",         ""),
    ("/auction_buy",        "Buy an auction listing",          "<listing_id>"),
    ("/auction_cancel",     "Cancel your listing",             "<listing_id>"),
    # ── Server Setup ──────────────────────────────────────────────────────────
    ("/setup_view",         "View workspace setup",            ""),
    ("/setup_channel",      "Set the onboarding channel",      "<channel_id>"),
    ("/setup_tips",         "Toggle onboarding tips",          "on | off"),
    ("/setup_post",         "Post the onboarding guide",       ""),
    ("/setup_reset",        "Reset workspace setup",           ""),
    # ── Code ──────────────────────────────────────────────────────────────────
    ("/code_new",           "Save a new code snippet",         "<name> <language> <code>"),
    ("/code_edit",          "Edit a saved snippet",            "<name> <new_code>"),
    ("/code_view",          "View a code snippet",             "<name>"),
    ("/code_list",          "List your snippets",              ""),
    ("/code_delete",        "Delete a snippet",                "<name>"),
    ("/code_run",           "Run a code snippet",              "<name>"),
    # ── Fun ───────────────────────────────────────────────────────────────────
    ("/aki",                "Play Akinator",                   ""),
    ("/emojimixup",         "Mix up emoji meanings",           ""),
    ("/rave",               "Start a rave",                    ""),
    ("/ravebg",             "Set a rave background",           ""),
    ("/img",                "Generate an image",               "<prompt>"),
    # ── Lichess ───────────────────────────────────────────────────────────────
    ("/lichess",            "Check a lichess profile",         "<username>"),
    ("/lichess_game",       "Show a lichess game",             "<game_id>"),
    ("/lichess_stream",     "Stream lichess games",            "<username>"),
    # ── Automod ───────────────────────────────────────────────────────────────
    ("/automod",            "View automod settings",           ""),
    ("/automod_reset",      "Reset automod config",            ""),
    ("/automod_punishment", "Set punishment type",             "<warn|mute|kick>"),
    ("/automod_slurs",      "Configure slur filter",           "on | off"),
    ("/automod_spam",       "Configure spam detection",        "on | off"),
    ("/automod_filters",    "View automod filters",            ""),
    ("/automod_settings",   "View full automod settings",      ""),
    # ── AFK ───────────────────────────────────────────────────────────────────
    ("/afk",                "Set your AFK status",             "[message]"),
]

MANIFEST = {
    "display_information": {
        "name": "FuSBot",
        "description": "The all-in-one server bot",
        "background_color": "#1a1a2e",
    },
    "features": {
        "bot_user": {
            "display_name": "FuSBot",
            "always_online": True,
        },
        "slash_commands": [
            {
                "command": cmd,
                "description": desc[:2000],
                "usage_hint": hint,
                "should_escape": False,
            }
            for cmd, desc, hint in COMMANDS
        ],
    },
    "oauth_config": {
        "scopes": {
            "bot": [
                "chat:write",
                "chat:write.public",
                "commands",
                "channels:history",
                "groups:history",
                "im:history",
                "mpim:history",
                "reactions:read",
                "files:write",
            ]
        }
    },
    "settings": {
        "event_subscriptions": {
            "bot_events": [
                "message.channels",
                "message.groups",
                "message.im",
                "message.mpim",
                "reaction_added",
            ]
        },
        "interactivity": {"is_enabled": True},
        "org_deploy_enabled": False,
        "socket_mode_enabled": True,
        "token_rotation_enabled": False,
    },
}


def main():
    print(f"Updating app {APP_ID} with {len(COMMANDS)} slash commands...")
    resp = requests.post(
        "https://slack.com/api/apps.manifest.update",
        headers={
            "Authorization": f"Bearer {CONFIG_TOKEN}",
            "Content-Type": "application/json; charset=utf-8",
        },
        data=json.dumps({"app_id": APP_ID, "manifest": MANIFEST}),
    )
    data = resp.json()
    if data.get("ok"):
        print(f"Done! {len(COMMANDS)} commands registered.")
    else:
        print(f"ERROR: {data.get('error')}")
        if data.get("errors"):
            for e in data["errors"]:
                print(f"  - {e}")
        print("\nFull response:", json.dumps(data, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
