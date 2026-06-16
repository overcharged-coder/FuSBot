# FuSBot

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![Slack](https://img.shields.io/badge/Slack-Bolt-4A154B?logo=slack&logoColor=white)
![Socket Mode](https://img.shields.io/badge/Socket%20Mode-enabled-4A154B?logo=slack&logoColor=white)
![AI](https://img.shields.io/badge/AI-GitHub%20Models-181717?logo=github&logoColor=white)
![Deploy](https://img.shields.io/badge/Deploy-GitHub%20Actions-2088FF?logo=githubactions&logoColor=white)
![Status](https://img.shields.io/badge/status-active-brightgreen)

> **Full Server Bot** — roast AI, economy, RPG systems, auto-battler, stock market, hacking sim, and more. All slash commands.

---

## Features

| Category | Systems |
|---|---|
| 🔥 Roast AI | Multi-model roasting, memory profiles, auto-roast, spice scoring |
| 💰 Economy | Balance, daily, work, give, pray, leaderboard |
| 🎲 Gambling | Blackjack, slots, coinflip, crime |
| 🦌 Hunting & Fishing | 130+ creatures, weighted rarities, prayer buffs |
| ⚔️ Battle & Team | Monster fights, team management, evolutions |
| 📈 Stocks | Live simulated market, buy/sell, portfolio |
| 🏰 Dungeon | Floor crawler, sanity, relics, raid boss, rift dives |
| 🌀 Voidmaze | Roguelite, artifacts, anomalies, clarity system |
| 🏟️ Arena | Auto-battler, elements, ultimates, seasons, ELO ladder |
| 🧪 Lab | Research, experiments, breakthroughs, instability |
| 💻 Hack | 4-phase hacking RPG using your own code files |
| 📁 Codepad | Per-user code snippets, run in sandbox |
| 🚢 Battleship | Full game with AI (easy → god), ELO ranking |
| 🎩 Monopoly | Full game, AI opponent, SQLite persistence |
| 🏛️ Guilds | Create, join, deposit, upgrade |
| 🛒 Auction House | List, browse, buy, cancel |
| 🗺️ Quests | Daily quest board, claim rewards |
| 🏆 Achievements | 33 tracked milestones, mastery grades |
| 🎖️ Titles & Badges | Unlock and equip cosmetic titles |
| ♟️ Lichess | Live game tracking for a lichess account |
| 🛡️ AutoMod | Spam detection, slur filter, escalation ladder |
| 🎉 Fun | Akinator, animal facts, emoji mixup, rave, image gen |

---

## Setup

### 1. Slack App

Create an app at [api.slack.com/apps](https://api.slack.com/apps):

- **Socket Mode** → enable → copy `SLACK_APP_TOKEN` (`xapp-…`)
- **OAuth & Permissions** → add scopes → install to workspace → copy `SLACK_BOT_TOKEN` (`xoxb-…`)
- **Event Subscriptions** → subscribe: `message.channels`, `message.groups`, `message.im`, `message.mpim`, `reaction_added`

Required bot scopes:
```
chat:write  chat:write.public  commands
channels:history  groups:history  im:history  mpim:history
reactions:read  files:write
```

### 2. Register all slash commands

Add `SLACK_APP_ID` and `SLACK_CONFIG_TOKEN` (App-Level Token with `app_configurations:write`) to your secrets, then run once:

```bash
python register_slack_app.py
```

### 3. GitHub Secrets

Go to **Settings → Secrets → Actions** and add:

| Secret | Description |
|---|---|
| `SLACK_BOT_TOKEN` | `xoxb-…` bot token |
| `SLACK_APP_TOKEN` | `xapp-…` socket mode token |
| `GITHUB` | GitHub PAT for AI models |
| `PAT_TOKEN` | GitHub PAT for pushing state |
| `GROQ` | Groq API key *(optional)* |
| `GEMINI_API_KEY` | Gemini API key *(optional)* |
| `OPENROUTER_KEY` | OpenRouter key *(optional)* |

### 4. Run

The bot runs automatically via GitHub Actions every 6 hours. To start manually:

**Actions → Run Slack Bot → Run workflow**

Or locally:
```bash
pip install -r requirements.txt
python app.py
```

---

## How it works

The bot runs on GitHub Actions on a 6-hour cron. When the job ends, state files (`state.json`, `roast_memory.json`, SQLite DBs, etc.) are committed back to the repo automatically so nothing is lost between runs.

---

## Command Reference

<details>
<summary><b>🔥 Roast</b></summary>

| Command | Description |
|---|---|
| `/roast @user` | AI-roast someone using memory + multi-model scoring |
| `/roastmode fast\|deep\|adjustable` | Set your roast style |
| `/stoproast` | Exit roast mode |
| `/autor on\|off` | Auto-roast anyone who mentions the bot in this channel |
| `/data [@user]` | View stored memory profile |

</details>

<details>
<summary><b>💰 Economy</b></summary>

| Command | Description |
|---|---|
| `/balance [@user]` | Check balance |
| `/daily` | Claim daily reward |
| `/work` | Work a job for horsenncy |
| `/give @user amount` | Transfer horsenncy |
| `/pray` | Gain a prayer boost |
| `/leaderboard` | Top 10 richest |
| `/coinflip amount [heads\|tails]` | 50/50 gamble |
| `/blackjack amount` | Full blackjack game |
| `/slots amount` | 3×3 slot machine |
| `/crime` | High-risk heist |

</details>

<details>
<summary><b>🛍️ Shop & Items</b></summary>

| Command | Description |
|---|---|
| `/shop` | Browse all items |
| `/buy item [amount]` | Purchase an item |
| `/inventory [@user]` | View items |
| `/use item` | Use an item |

</details>

<details>
<summary><b>📈 Stocks</b></summary>

| Command | Description |
|---|---|
| `/stocks` | View market prices and your portfolio |
| `/stocks_buy SYMBOL amount` | Buy shares |
| `/stocks_sell SYMBOL amount` | Sell shares |

</details>

<details>
<summary><b>🦌 Hunting, Fishing & Battle</b></summary>

| Command | Description |
|---|---|
| `/hunt` | Hunt one of 130+ creatures |
| `/fish` | Fish for aquatic creatures |
| `/battle [@user]` | Fight a monster or player |
| `/team list\|add\|remove` | Manage your battle team |

</details>

<details>
<summary><b>🏰 Deep Modes</b></summary>

| Command | Description |
|---|---|
| `/dungeon` | Enter the dungeon RPG |
| `/voidmaze` | Enter the void maze roguelite |
| `/arena` | Enter the auto-battler arena |
| `/arena_buy item` | Buy an arena upgrade |
| `/arena_setteam names…` | Set your arena team |
| `/lab` | Enter the research lab |

</details>

<details>
<summary><b>💻 Hack & Codepad</b></summary>

| Command | Description |
|---|---|
| `/hack` | Run a 4-phase hacking sim using your code files |
| `/hack_profile [@user]` | View hack stats |
| `/hack_targets` | List available targets |
| `/hack_chaos` | Trigger global chaos event |
| `/hack_chaos_state` | View current chaos level |
| `/code_new name lang code` | Save a code snippet |
| `/code_edit name code` | Edit a snippet |
| `/code_view name` | View a snippet |
| `/code_list` | List your snippets |
| `/code_delete name` | Delete a snippet |
| `/code_run name` | Run a snippet |

</details>

<details>
<summary><b>🚢 Battleship</b></summary>

| Command | Description |
|---|---|
| `/battleship [@user \| ai diff]` | Start a game |
| `/bs_place A0 r\|d` | Place your next ship |
| `/bs_fire B5` | Fire at a coordinate |
| `/bs_status` | View your boards |
| `/bs_forfeit` | Forfeit |
| `/bs_resume` | Resume a saved game |
| `/bs_stats [@user]` | Win/loss/ELO stats |
| `/bs_leaderboard` | ELO leaderboard |

</details>

<details>
<summary><b>🎩 Monopoly</b></summary>

| Command | Description |
|---|---|
| `/monopoly_start [@opponent]` | Start a game (vs player or AI) |
| `/monopoly_stop` | End the current game |
| `/monopoly_resume` | Resume a saved game |

</details>

<details>
<summary><b>🏛️ Guilds & Auction</b></summary>

| Command | Description |
|---|---|
| `/guild_create name` | Create a guild |
| `/guild_join id` | Join a guild |
| `/guild_leave` | Leave your guild |
| `/guild_info [id]` | View guild info |
| `/guild_deposit amount` | Deposit to guild bank |
| `/guild_upgrade` | Upgrade guild level |
| `/auction_sell item amount price` | List an item |
| `/auction_browse` | Browse listings |
| `/auction_buy id` | Buy a listing |
| `/auction_cancel id` | Cancel your listing |

</details>

<details>
<summary><b>🗺️ Quests, Achievements & Profile</b></summary>

| Command | Description |
|---|---|
| `/quests [@user]` | View daily quest board |
| `/quests_claim slot` | Claim a completed quest |
| `/achievements [@user]` | View achievement progress |
| `/profile [@user]` | View full profile |
| `/collections [@user]` | View collector stats |
| `/titles [@user]` | View unlocked titles |
| `/title_equip title` | Equip a title |
| `/badge [@user]` | View badges |

</details>

<details>
<summary><b>♟️ Lichess</b></summary>

| Command | Description |
|---|---|
| `/lichess username` | View lichess profile |
| `/lichess_game game_id` | View a game |
| `/lichess_stream username` | Stream live games |

</details>

<details>
<summary><b>🛡️ AutoMod</b></summary>

| Command | Description |
|---|---|
| `/automod` | View current settings |
| `/automod_reset` | Reset config |
| `/automod_punishment warn\|mute\|kick` | Set punishment |
| `/automod_slurs on\|off` | Toggle slur filter |
| `/automod_spam on\|off` | Toggle spam detection |
| `/automod_filters` | View active filters |
| `/automod_settings` | Full settings view |

</details>

<details>
<summary><b>🎉 Fun & Misc</b></summary>

| Command | Description |
|---|---|
| `/aki` | Play Akinator |
| `/animal` | Random animal fact |
| `/emojimixup` | Mix up emoji meanings |
| `/rave` | Start a rave |
| `/img prompt` | Generate an image |
| `/afk [message]` | Set AFK status |
| `/recommend` | Get a personalised activity suggestion |
| `/whatsnext` | See what to do next |
| `/help [topic]` | Help guide |
| `/start` | Beginner guide |
| `/setup_view` | Workspace setup |

</details>

---

*FuSBot — Full (Fu) Server (S) Bot*
