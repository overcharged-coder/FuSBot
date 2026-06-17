import datetime
import random

from economy import get_user
from economy_shared import state, save_state

try:
    from achievement import build_snapshot
except Exception:
    build_snapshot = None


class QuestBoard:
    QUEST_POOL = [
        {"id": "balance_1k", "label": "Hold 1,000 horsenncy", "key": "balance", "goal": 1000, "reward": 250},
        {"id": "balance_10k", "label": "Hold 10,000 horsenncy", "key": "balance", "goal": 10000, "reward": 900},
        {"id": "net_25k", "label": "Reach 25,000 net worth", "key": "net_worth", "goal": 25000, "reward": 1250},
        {"id": "pray_10", "label": "Reach 10 prayer points", "key": "pray_points", "goal": 10, "reward": 220},
        {"id": "inv_10", "label": "Own 10 unique inventory items", "key": "inventory_unique", "goal": 10, "reward": 300},
        {"id": "animals_10", "label": "Own 10 animals", "key": "owned_animals_count", "goal": 10, "reward": 420},
        {"id": "team_500", "label": "Reach 500 team power", "key": "team_power", "goal": 500, "reward": 650},
        {"id": "stocks_5k", "label": "Reach 5,000 portfolio value", "key": "stock_value", "goal": 5000, "reward": 500},
        {"id": "dungeon_5", "label": "Reach dungeon floor 5", "key": "dungeon_floor", "goal": 5, "reward": 500},
        {"id": "raid_1k", "label": "Deal 1,000 raid damage", "key": "raid_damage", "goal": 1000, "reward": 700},
        {"id": "arena_1200", "label": "Reach 1,200 arena rating", "key": "arena_rating", "goal": 1200, "reward": 800},
        {"id": "void_5", "label": "Reach Voidmaze depth 5", "key": "void_best_depth", "goal": 5, "reward": 650},
        {"id": "lab_5", "label": "Reach lab level 5", "key": "lab_level", "goal": 5, "reward": 650},
        {"id": "hack_5", "label": "Reach hack skill 5", "key": "hack_skill", "goal": 5, "reward": 650},
        {"id": "active_5", "label": "Be active in 5 system groups", "key": "active_modes", "goal": 5, "reward": 1200},
    ]

    @staticmethod
    def today_key():
        return datetime.datetime.utcnow().strftime("%Y-%m-%d")

    @staticmethod
    def snapshot_for(uid: str):
        if build_snapshot:
            return build_snapshot(uid)
        data = get_user(uid)
        inventory = data.get("inventory", {}) if isinstance(data.get("inventory", {}), dict) else {}
        owned_animals = data.get("owned_animals", []) if isinstance(data.get("owned_animals", []), list) else []
        team = data.get("team", []) if isinstance(data.get("team", []), list) else []
        dungeon = data.get("dungeon", {}) if isinstance(data.get("dungeon", {}), dict) else {}
        raid = data.get("raid", {}) if isinstance(data.get("raid", {}), dict) else {}
        arena = data.get("arena", {}) if isinstance(data.get("arena", {}), dict) else {}
        voidmaze = data.get("voidmaze", {}) if isinstance(data.get("voidmaze", {}), dict) else {}
        lab = data.get("lab", {}) if isinstance(data.get("lab", {}), dict) else {}
        hack = data.get("hack", {}) if isinstance(data.get("hack", {}), dict) else {}
        team_power = sum(int(animal.get("strength", 0) or 0) for animal in team if isinstance(animal, dict))
        return {
            "balance": int(data.get("balance", 0) or 0),
            "net_worth": int(data.get("balance", 0) or 0),
            "pray_points": int(data.get("pray", 0) or 0),
            "inventory_unique": sum(1 for qty in inventory.values() if int(qty or 0) > 0),
            "owned_animals_count": len(owned_animals),
            "team_power": team_power,
            "stock_value": 0,
            "dungeon_floor": int(dungeon.get("floor", 1) or 1),
            "raid_damage": int(raid.get("damage", 0) or 0),
            "arena_rating": int(arena.get("rating", 0) or 0),
            "void_best_depth": int(voidmaze.get("best_depth", 0) or 0),
            "lab_level": int(lab.get("level", 0) or 0),
            "hack_skill": int(hack.get("skill", 0) or 0),
            "active_modes": sum(1 for x in [bool(inventory), bool(owned_animals), bool(team), bool(arena), bool(voidmaze), bool(lab), bool(hack)] if x),
        }

    @staticmethod
    def state_root():
        return state.setdefault("quest_progress_v1", {})

    @classmethod
    def user_state(cls, uid: str):
        root = cls.state_root()
        today = cls.today_key()
        if uid not in root or root[uid].get("day") != today:
            rng = random.Random(f"{uid}:{today}:fusquests")
            picks = rng.sample(cls.QUEST_POOL, k=min(3, len(cls.QUEST_POOL)))
            root[uid] = {"day": today, "quest_ids": [q["id"] for q in picks], "claimed": []}
            save_state()
        return root[uid]

    @classmethod
    def board_for(cls, uid: str):
        user_state = cls.user_state(uid)
        lookup = {q["id"]: q for q in cls.QUEST_POOL}
        snapshot = cls.snapshot_for(uid)
        board = []
        for idx, quest_id in enumerate(user_state.get("quest_ids", []), start=1):
            q = lookup.get(quest_id)
            if not q:
                continue
            current = int(snapshot.get(q["key"], 0) or 0)
            done = current >= q["goal"]
            claimed = quest_id in user_state.get("claimed", [])
            pct = min(100, int(round((current / q["goal"]) * 100))) if q["goal"] > 0 else 100
            board.append({"index": idx, "id": quest_id, "label": q["label"], "current": current, "goal": q["goal"], "reward": q["reward"], "done": done, "claimed": claimed, "percent": pct})
        return board

    @classmethod
    def claim(cls, uid: str, index: int):
        board = cls.board_for(uid)
        if index < 1 or index > len(board):
            return False, "that quest slot doesnt exist"
        quest = board[index - 1]
        if quest["claimed"]:
            return False, "that quest is already claimed"
        if not quest["done"]:
            return False, "you havent finished that quest yet"
        user_state = cls.user_state(uid)
        user_state.setdefault("claimed", []).append(quest["id"])
        data = get_user(uid)
        data["balance"] = int(data.get("balance", 0) or 0) + quest["reward"]
        save_state()
        return True, quest


async def setup(app):

    @app.command("/fus_quests")
    async def quests_cmd(ack, command, client):
        await ack()
        import re as re_mod
        uid = command["user_id"]; channel = command["channel_id"]
        text = (command.get("text") or "").strip()
        parts = text.split(None, 1)
        action = parts[0].lower() if parts else ""
        arg = parts[1].strip() if len(parts) > 1 else ""

        if action == "claim":
            try:
                slot = int(arg if arg else "0")
            except ValueError:
                await client.chat_postEphemeral(channel=channel, user=uid, text="usage: `/fus_quests claim <slot>` (1, 2, or 3)"); return
            ok, result = QuestBoard.claim(uid, slot)
            if not ok:
                await client.chat_postEphemeral(channel=channel, user=uid, text=result); return
            await client.chat_postMessage(channel=channel, text=f":tada: *quest claimed!*\n*{result['label']}*\nreward: `{result['reward']}` horsenncy")

        else:
            target_id = uid; mention = f"<@{uid}>"
            m = re_mod.search(r"<@([A-Z0-9]+)>", text)
            if m: target_id = m.group(1); mention = f"<@{target_id}>"
            board = QuestBoard.board_for(target_id); today = QuestBoard.today_key()
            complete_count = sum(1 for q in board if q["done"]); claimed_count = sum(1 for q in board if q["claimed"])
            lines = []
            for quest in board:
                status = ":white_check_mark: claimed" if quest["claimed"] else ":large_green_circle: done" if quest["done"] else ":large_yellow_circle: in progress"
                lines.append(f"`{quest['index']}` *{quest['label']}*\n{status} • `{quest['current']}` / `{quest['goal']}` • reward `{quest['reward']}`")
            board_text = "\n\n".join(lines) if lines else "no quests rolled"
            msg = (
                f":scroll: *{mention}'s Daily Quests*\n"
                f"day `{today}` • completed `{complete_count}` / `{len(board)}` • claimed `{claimed_count}` / `{len(board)}`\n\n"
                f"{board_text}\n\n_use `/fus_quests claim <slot>` to claim a finished quest_"
            )
            await client.chat_postMessage(channel=channel, text=msg[:3000])
