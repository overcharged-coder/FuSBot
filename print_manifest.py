"""Run this and paste the output into:
api.slack.com/apps → your app → App Manifest → (switch to JSON) → paste → Save Changes
"""
import json

COMMANDS = [
    # Roast
    ("/roast", "Roast someone", "@user or message"),
    ("/data", "View memory profile", "[@user]"),
    ("/autor", "Toggle auto-roast", "on | off"),
    ("/roastmode", "Set or stop roast mode", "fast | deep | adjustable | off"),
    # Help & onboarding
    ("/help", "Help guide", "[start | topic]"),
    ("/recommend", "Get activity recommendation", ""),
    # Economy
    ("/balance", "Check balance", "[@user]"),
    ("/daily", "Claim daily reward", ""),
    ("/work", "Work for horsenncy", ""),
    ("/give", "Send horsenncy", "@user <amount>"),
    ("/coinflip", "Flip a coin bet", "<amount> [heads|tails]"),
    ("/pray", "Pray for a boost", ""),
    ("/leaderboard", "Top balances", ""),
    ("/slots", "Play the slots", "<amount>"),
    ("/blackjack", "Play blackjack", "<amount>"),
    ("/crime", "Commit a crime", ""),
    ("/shop", "Browse the shop", ""),
    ("/buy", "Buy a shop item", "<item> [amount]"),
    ("/inventory", "View inventory", "[@user]"),
    ("/use", "Use an item", "<item>"),
    ("/stocks", "Stocks — view, buy, sell", "[buy|sell SYMBOL amount]"),
    # Creatures & battle
    ("/animal", "Random animal fact", ""),
    ("/hunt", "Hunt for animals", ""),
    ("/fish", "Go fishing", ""),
    ("/battle", "Battle a monster", "[@user]"),
    ("/team", "Manage your team", "list | add <name> | remove <name>"),
    # Profile & progression
    ("/profile", "View profile, achievements, collections", "[@user | achievements | collections]"),
    ("/quests", "Quest board + claim", "[@user | claim <slot>]"),
    ("/titles", "View / equip titles", "[@user | equip <title>]"),
    ("/badge", "View badges", "[@user]"),
    # Deep modes
    ("/dungeon", "Enter the dungeon", ""),
    ("/voidmaze", "Enter the void maze", ""),
    ("/arena", "Arena — enter, buy upgrade, set team", "[buy <item> | setteam <names>]"),
    ("/lab", "Enter the lab", ""),
    # Hack & code
    ("/hack", "Hack — run, profile, targets, chaos", "<target> | profile | targets | state | chaos <target>"),
    ("/code", "Codepad — new, edit, view, run, delete", "new|edit|view|list|delete|run <file>"),
    # Games
    ("/battleship", "Start battleship", "[@opponent | ai [easy|normal|hard|god]]"),
    ("/bs", "Battleship actions", "place|fire|status|forfeit|resume|stats|leaderboard"),
    ("/monopoly", "Monopoly — start, stop, resume", "[start [@opponent] | stop | resume]"),
    # Social systems
    ("/guild", "Guild — create, join, leave, info, deposit, upgrade", "create|join|leave|info|deposit|upgrade"),
    ("/auction", "Auction house — sell, browse, buy, cancel", "sell|browse|buy|cancel"),
    ("/setup", "Workspace setup", "view|channel|tips|post|reset"),
    # Lichess
    ("/lichess", "Lichess — status, last game, stream", "[game | stream]"),
    # AutoMod
    ("/automod", "AutoMod — all settings", "on|off|reset|punishment|slurs|spam|filters|settings"),
    # Fun
    ("/aki", "Play Akinator", ""),
    ("/emojimixup", "Emoji mixup game", ""),
    ("/rave", "Rave builder + background", "[bg <upload_key>]"),
    ("/img", "Generate an image", "<prompt>"),
    ("/afk", "Set AFK status", "[message]"),
]

manifest = {
    "display_information": {
        "name": "FuSBot",
        "description": "Full server bot — economy, RPG, roast AI, games and more",
        "background_color": "#1a1a2e",
    },
    "features": {
        "bot_user": {"display_name": "FuSBot", "always_online": True},
        "slash_commands": [
            {"command": cmd, "description": desc, "usage_hint": hint, "should_escape": False}
            for cmd, desc, hint in COMMANDS
        ],
    },
    "oauth_config": {
        "scopes": {
            "bot": [
                "chat:write", "chat:write.public", "commands",
                "channels:history", "groups:history", "im:history",
                "mpim:history", "reactions:read", "files:write",
            ]
        }
    },
    "settings": {
        "event_subscriptions": {
            "bot_events": [
                "message.channels", "message.groups",
                "message.im", "message.mpim", "reaction_added",
            ]
        },
        "interactivity": {"is_enabled": True},
        "org_deploy_enabled": False,
        "socket_mode_enabled": True,
        "token_rotation_enabled": False,
    },
}

print(f"Total commands: {len(COMMANDS)}")
print(json.dumps(manifest, indent=2))
