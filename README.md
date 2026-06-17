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
| `/fus_roast @user` | AI-roast someone using memory + multi-model scoring |
| `/fus_roastmode fast\|deep\|adjustable\|off` | Set roast style — `off` exits roast mode |
| `/fus_autor on\|off` | Auto-roast anyone who mentions the bot in this channel |
| `/fus_data [@user]` | View stored memory profile |

</details>

<details>
<summary><b>💰 Economy</b></summary>

| Command | Description |
|---|---|
| `/fus_balance [@user]` | Check balance |
| `/fus_daily` | Claim daily reward |
| `/fus_work` | Work a job for horsenncy |
| `/fus_give @user amount` | Transfer horsenncy |
| `/fus_pray` | Gain a prayer boost |
| `/fus_leaderboard` | Top 10 richest |
| `/fus_coinflip amount [heads\|tails]` | 50/50 gamble |
| `/fus_blackjack amount` | Full blackjack game |
| `/fus_slots amount` | 3×3 slot machine |
| `/fus_crime` | High-risk heist |

</details>

<details>
<summary><b>🛍️ Shop & Items</b></summary>

| Command | Description |
|---|---|
| `/fus_shop` | Browse all items |
| `/fus_buy item [amount]` | Purchase an item |
| `/fus_inventory [@user]` | View items |
| `/fus_use item` | Use an item |

</details>

<details>
<summary><b>📈 Stocks</b></summary>

| Command | Description |
|---|---|
| `/fus_stocks` | View market prices and your portfolio |
| `/fus_stocks buy SYMBOL amount` | Buy shares |
| `/fus_stocks sell SYMBOL amount` | Sell shares |

</details>

<details>
<summary><b>🦌 Hunting, Fishing & Battle</b></summary>

| Command | Description |
|---|---|
| `/fus_hunt` | Hunt one of 130+ creatures |
| `/fus_fish` | Fish for aquatic creatures |
| `/fus_battle [@user]` | Fight a monster or player |
| `/fus_team list\|add\|remove` | Manage your battle team |

</details>

<details>
<summary><b>🏰 Deep Modes</b></summary>

| Command | Description |
|---|---|
| `/fus_dungeon` | Enter the dungeon RPG |
| `/fus_voidmaze` | Enter the void maze roguelite |
| `/fus_arena` | Enter the auto-battler arena |
| `/fus_arena buy might\|haste\|ward\|luck` | Buy an arena upgrade with crowns |
| `/fus_arena setteam name1, name2, …` | Set your arena team (up to 5) |
| `/fus_lab` | Enter the research lab |

</details>

<details>
<summary><b>💻 Hack & Codepad</b></summary>

| Command | Description |
|---|---|
| `/fus_hack <target>` | Run a 4-phase hacking sim |
| `/fus_hack profile [@user]` | View hack stats |
| `/fus_hack targets` | List available targets |
| `/fus_hack chaos <target>` | Trigger chaos hack (max difficulty) |
| `/fus_hack state` | View current chaos resonance |
| `/fus_code new <file>` | Create a code file |
| `/fus_code edit <file>` | Edit a file via modal |
| `/fus_code view <file>` | View a file |
| `/fus_code list` | List your files |
| `/fus_code delete <file>` | Delete a file |
| `/fus_code run <file>` | Run a file |

</details>

<details>
<summary><b>🚢 Battleship</b></summary>

| Command | Description |
|---|---|
| `/fus_battleship [@user \| ai diff]` | Start a game |
| `/fus_bs place A0 r\|d` | Place your next ship |
| `/fus_bs fire B5` | Fire at a coordinate |
| `/fus_bs status` | View your boards |
| `/fus_bs forfeit` | Forfeit |
| `/fus_bs resume` | Resume a saved game |
| `/fus_bs stats [@user]` | Win/loss/ELO stats |
| `/fus_bs leaderboard` | ELO leaderboard |

</details>

<details>
<summary><b>🎩 Monopoly</b></summary>

| Command | Description |
|---|---|
| `/fus_monopoly start [@opponent]` | Start a game (vs player or AI) |
| `/fus_monopoly stop` | End the current game |
| `/fus_monopoly resume` | Resume a saved game |

</details>

<details>
<summary><b>🏛️ Guilds & Auction</b></summary>

| Command | Description |
|---|---|
| `/fus_guild create name` | Create a guild |
| `/fus_guild join id` | Join a guild |
| `/fus_guild leave` | Leave your guild |
| `/fus_guild info [id]` | View guild info |
| `/fus_guild deposit amount` | Deposit to guild bank |
| `/fus_guild upgrade` | Upgrade guild level |
| `/fus_auction sell item amount price` | List an item |
| `/fus_auction browse` | Browse listings |
| `/fus_auction buy id` | Buy a listing |
| `/fus_auction cancel id` | Cancel your listing |

</details>

<details>
<summary><b>🗺️ Quests, Profile & Titles</b></summary>

| Command | Description |
|---|---|
| `/fus_quests [@user]` | View daily quest board |
| `/fus_quests claim slot` | Claim a completed quest |
| `/fus_profile [@user]` | View full profile |
| `/fus_profile achievements [@user]` | View achievement progress |
| `/fus_profile collections [@user]` | View collector stats |
| `/fus_titles [@user]` | View unlocked titles |
| `/fus_titles equip title` | Equip a title |
| `/fus_badge [@user]` | View badges |

</details>

<details>
<summary><b>🛡️ AutoMod</b></summary>

| Command | Description |
|---|---|
| `/fus_automod` | View current settings |
| `/fus_automod on\|off` | Enable or disable automod |
| `/fus_automod reset @user` | Reset a user's offence count |
| `/fus_automod punishment level action` | Set punishment for a level |
| `/fus_automod slurs list\|add\|remove` | Manage slur filter |
| `/fus_automod spam setting value` | Configure spam thresholds |
| `/fus_automod filters name on\|off` | Toggle a filter |
| `/fus_automod settings key value` | Adjust misc settings |

</details>

<details>
<summary><b>🎉 Fun & Misc</b></summary>

| Command | Description |
|---|---|
| `/fus_aki` | Play Akinator |
| `/fus_animal` | Random animal fact |
| `/fus_emojimixup` | Mix up emoji meanings |
| `/fus_rave` | Start a rave |
| `/fus_rave bg <key>` | Set rave background video |
| `/fus_img prompt` | Generate an image |
| `/fus_afk [message]` | Set AFK status |
| `/fus_recommend` | Get a personalised activity suggestion |
| `/fus_help [topic\|start]` | Help guide — use `start` for the beginner guide |
| `/fus_setup view\|channel\|tips\|post\|reset` | Workspace setup |

</details>

---

*FuSBot — Full (Fu) Server (S) Bot*
