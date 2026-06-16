import time
import re
import json
import os
import datetime
from collections import defaultdict, deque

AUTOMOD_FILE = "automod_config.json"
OFFENCES_FILE = "automod_offences.json"

_ADMIN_USER_IDS: set[str] = set()


def _load_json(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save_json(path: str, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


AUTOMOD_DATA = _load_json(AUTOMOD_FILE, {})


def save_automod():
    _save_json(AUTOMOD_FILE, AUTOMOD_DATA)


def load_offences():
    raw = _load_json(OFFENCES_FILE, {})
    out: dict[str, dict[str, int]] = {}
    for ws, users in raw.items():
        out[ws] = {uid: int(v) for uid, v in users.items()}
    return out


def save_offences(offences: dict[str, dict[str, int]]):
    _save_json(OFFENCES_FILE, offences)


def censor_word(w: str) -> str:
    if not w:
        return ""
    if len(w) <= 3:
        return w[0] + "*" * (len(w) - 1)
    return w[:-3] + "***"


_invite_re = re.compile(r"(?:discord\.gg|discord(?:app)?\.com\/invite)\/[A-Za-z0-9\-]+", re.I)
_url_re = re.compile(r"https?:\/\/\S+|www\.\S+", re.I)
_zalgo_re = re.compile(r"[̀-ͯ҃-҉ؐ-ًؚ-ٰٟۖ-ۜ۟-ۤۧ-۪ۨ-ۭ]+")
_ws_re = re.compile(r"\s+")
_non_alnum_space_re = re.compile(r"[^a-z0-9\s]")
_repeat_re = re.compile(r"(.)\1{2,}")


class AutoModEngine:
    def __init__(self):
        self.msg_times = defaultdict(lambda: deque(maxlen=64))
        self.msg_norms = defaultdict(lambda: deque(maxlen=16))
        self.offences: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.last_punish: dict[tuple, float] = {}
        loaded = load_offences()
        for ws, users in loaded.items():
            for uid, v in users.items():
                self.offences[ws][uid] = v

    def get_cfg(self, workspace_id: str) -> dict:
        if workspace_id not in AUTOMOD_DATA:
            AUTOMOD_DATA[workspace_id] = {}
        cfg = AUTOMOD_DATA[workspace_id]
        cfg.setdefault("enabled", False)
        cfg.setdefault("slurs", [])
        cfg.setdefault("punishments", {"1": "warn", "2": "warn", "3": "warn", "4": "warn"})
        cfg.setdefault("cooldown_seconds", 10)
        cfg.setdefault("spam", {})
        spam = cfg["spam"]
        spam.setdefault("window_seconds", 6)
        spam.setdefault("max_messages", 5)
        spam.setdefault("duplicate_count", 3)
        spam.setdefault("max_mentions", 6)
        spam.setdefault("max_links", 4)
        spam.setdefault("caps_ratio", 0.75)
        spam.setdefault("caps_min_len", 12)
        spam.setdefault("max_zalgo_marks", 12)
        spam.setdefault("repeat_char_limit", 8)
        cfg.setdefault("filters", {})
        flt = cfg["filters"]
        flt.setdefault("block_invites", False)
        flt.setdefault("block_links", False)
        save_automod()
        return cfg

    def normalize(self, text: str) -> str:
        t = text.lower()
        t = _zalgo_re.sub("", t)
        t = _non_alnum_space_re.sub("", t)
        t = _repeat_re.sub(r"\1\1", t)
        t = _ws_re.sub(" ", t).strip()
        return t

    def _count_links(self, content: str) -> int:
        return len(_url_re.findall(content))

    def _count_mentions(self, content: str) -> int:
        return len(re.findall(r"<@[A-Z0-9]+>", content)) + len(re.findall(r"<!channel>|<!here>|<!everyone>", content)) * 10

    def _caps_ratio(self, content: str) -> float:
        letters = [ch for ch in content if ch.isalpha()]
        if not letters:
            return 0.0
        return sum(1 for ch in letters if ch.isupper()) / len(letters)

    def _zalgo_marks(self, content: str) -> int:
        return len(_zalgo_re.findall(content))

    def _repeat_char_run(self, content: str) -> int:
        longest = 0; cur = 1; last = ""
        for ch in content:
            if ch == last: cur += 1
            else: longest = max(longest, cur); cur = 1; last = ch
        return max(longest, cur)

    def contains_slur(self, text: str, slurs: list) -> str | None:
        lowered = self.normalize(text)
        for s in slurs:
            if not s: continue
            if re.search(rf"\b{re.escape(s.lower())}\b", lowered):
                return s
        return None

    def _record(self, workspace_id: str, user_id: str, norm: str):
        key = (workspace_id, user_id)
        self.msg_times[key].append(time.time())
        self.msg_norms[key].append(norm)

    def _rate_spam(self, cfg: dict, workspace_id: str, user_id: str) -> bool:
        key = (workspace_id, user_id)
        window = float(cfg["spam"]["window_seconds"])
        max_msgs = int(cfg["spam"]["max_messages"])
        now = time.time()
        return sum(1 for t in self.msg_times[key] if now - t <= window) >= max_msgs

    def _duplicate_spam(self, cfg: dict, workspace_id: str, user_id: str, norm: str) -> bool:
        key = (workspace_id, user_id)
        return list(self.msg_norms[key]).count(norm) >= int(cfg["spam"]["duplicate_count"])

    def _signal_checks(self, cfg: dict, content: str) -> str | None:
        if cfg["filters"]["block_invites"] and _invite_re.search(content):
            return "invite link"
        if cfg["filters"]["block_links"] and _url_re.search(content):
            return "link"
        if self._count_mentions(content) >= int(cfg["spam"]["max_mentions"]):
            return "mention spam"
        if self._count_links(content) >= int(cfg["spam"]["max_links"]):
            return "link spam"
        if len(content) >= int(cfg["spam"]["caps_min_len"]) and self._caps_ratio(content) >= float(cfg["spam"]["caps_ratio"]):
            return "excessive caps"
        if self._zalgo_marks(content) >= int(cfg["spam"]["max_zalgo_marks"]):
            return "zalgo marks"
        if self._repeat_char_run(content) >= int(cfg["spam"]["repeat_char_limit"]):
            return "character spam"
        return None

    async def handle_message(self, workspace_id: str, user_id: str, content: str) -> str | None:
        cfg = self.get_cfg(workspace_id)
        if not cfg.get("enabled", False):
            return None
        norm = self.normalize(content)
        self._record(workspace_id, user_id, norm)
        if self._rate_spam(cfg, workspace_id, user_id):
            return await self.punish(workspace_id, user_id, "spam (rate)", cfg)
        if norm and self._duplicate_spam(cfg, workspace_id, user_id, norm):
            return await self.punish(workspace_id, user_id, "spam (duplicate)", cfg)
        sig = self._signal_checks(cfg, content)
        if sig:
            return await self.punish(workspace_id, user_id, sig, cfg)
        slur = self.contains_slur(content, cfg.get("slurs", []))
        if slur:
            return await self.punish(workspace_id, user_id, f"slur ({censor_word(slur)})", cfg)
        return None

    async def punish(self, workspace_id: str, user_id: str, reason: str, cfg: dict) -> str | None:
        now = time.time()
        cd = float(cfg.get("cooldown_seconds", 10))
        key = (workspace_id, user_id)
        if now - self.last_punish.get(key, 0.0) < cd:
            return None
        self.last_punish[key] = now
        self.offences[workspace_id][user_id] = self.offences[workspace_id].get(user_id, 0) + 1
        level = int(self.offences[workspace_id][user_id])
        save_offences({ws: dict(users) for ws, users in self.offences.items()})
        action = cfg.get("punishments", {}).get(str(level), "warn")
        return f":rotating_light: <@{user_id}> automod action level {level} — {reason}. ({action})"


ENGINE = AutoModEngine()


async def setup(app):

    @app.event("message")
    async def automod_message(event, say, client):
        uid = event.get("user")
        if not uid or event.get("bot_id") or event.get("subtype"):
            return
        workspace_id = event.get("team") or "default"
        content = event.get("text") or ""
        if not content:
            return
        result = await ENGINE.handle_message(workspace_id, uid, content)
        if result:
            try:
                await client.chat_postMessage(channel=event["channel"], text=result)
            except Exception:
                pass

    @app.command("/automod")
    async def automod_toggle(ack, command, respond):
        await ack()
        workspace_id = command.get("team_id") or "default"
        mode = (command.get("text") or "").strip().lower()
        cfg = ENGINE.get_cfg(workspace_id)
        cfg["enabled"] = mode == "on"
        save_automod()
        await respond(text=f"automod {'enabled' if cfg['enabled'] else 'disabled'}")

    @app.command("/automod_reset")
    async def automod_reset(ack, command, respond):
        await ack()
        import re as re_mod
        workspace_id = command.get("team_id") or "default"
        text = (command.get("text") or "").strip()
        m = re_mod.search(r"<@([A-Z0-9]+)>", text)
        if not m:
            return await respond(text="Usage: `/automod_reset @user`", response_type="ephemeral")
        uid = m.group(1)
        if uid in ENGINE.offences.get(workspace_id, {}):
            ENGINE.offences[workspace_id][uid] = 0
            save_offences({ws: dict(users) for ws, users in ENGINE.offences.items()})
            await respond(text=f":arrows_counterclockwise: Reset offences for <@{uid}>.")
        else:
            await respond(text=f"<@{uid}> has no recorded offences.")

    @app.command("/automod_punishment")
    async def automod_punishment(ack, command, respond):
        await ack()
        workspace_id = command.get("team_id") or "default"
        args = (command.get("text") or "").split()
        if len(args) < 2:
            return await respond(text="Usage: `/automod_punishment <level> <warn|kick|ban|timeout:minutes>`", response_type="ephemeral")
        try:
            level = int(args[0])
        except Exception:
            return await respond(text="Level must be a number.", response_type="ephemeral")
        action = args[1].lower().strip()
        valid = action in {"warn", "kick", "ban"} or (action.startswith("timeout:") and action.split(":", 1)[1].isdigit())
        if not valid:
            return await respond(text="Invalid action.", response_type="ephemeral")
        cfg = ENGINE.get_cfg(workspace_id)
        cfg["punishments"][str(level)] = action
        save_automod()
        await respond(text=f":white_check_mark: Level {level} → `{action}`")

    @app.command("/automod_slurs")
    async def automod_slurs(ack, command, respond):
        await ack()
        workspace_id = command.get("team_id") or "default"
        args = (command.get("text") or "").split(None, 1)
        action = args[0].lower() if args else "list"
        word = args[1].strip() if len(args) > 1 else None
        cfg = ENGINE.get_cfg(workspace_id)
        if action == "list":
            slurs = cfg["slurs"]
            if not slurs:
                return await respond(text="No slurs set.")
            return await respond(text="*Automod slurs:* " + ", ".join(censor_word(s) for s in slurs))
        if action == "add":
            if not word:
                return await respond(text="Provide a word.", response_type="ephemeral")
            w = word.lower().strip()
            if w in cfg["slurs"]:
                return await respond(text="Already exists.", response_type="ephemeral")
            cfg["slurs"].append(w); save_automod()
            return await respond(text=f"Added `{censor_word(w)}`.")
        if action == "remove":
            if not word:
                return await respond(text="Provide a word.", response_type="ephemeral")
            w = word.lower().strip()
            if w not in cfg["slurs"]:
                return await respond(text="Not found.", response_type="ephemeral")
            cfg["slurs"].remove(w); save_automod()
            return await respond(text=f"Removed `{censor_word(w)}`.")
        await respond(text="Actions: list, add, remove", response_type="ephemeral")

    @app.command("/automod_spam")
    async def automod_spam(ack, command, respond):
        await ack()
        workspace_id = command.get("team_id") or "default"
        args = (command.get("text") or "").split(None, 1)
        if len(args) < 2:
            return await respond(text="Usage: `/automod_spam <setting> <value>`", response_type="ephemeral")
        setting, value = args
        cfg = ENGINE.get_cfg(workspace_id)
        spam = cfg["spam"]
        if setting not in spam:
            return await respond(text=f"Valid settings: {', '.join(spam.keys())}", response_type="ephemeral")
        try:
            spam[setting] = float(value) if isinstance(spam[setting], float) else int(value)
        except Exception:
            return await respond(text="Invalid value.", response_type="ephemeral")
        save_automod()
        await respond(text=f":white_check_mark: `{setting}` = `{spam[setting]}`")

    @app.command("/automod_filters")
    async def automod_filters(ack, command, respond):
        await ack()
        workspace_id = command.get("team_id") or "default"
        args = (command.get("text") or "").split(None, 1)
        if len(args) < 2:
            return await respond(text="Usage: `/automod_filters <block_invites|block_links> <on|off>`", response_type="ephemeral")
        filter_name, mode = args
        cfg = ENGINE.get_cfg(workspace_id)
        if filter_name not in cfg["filters"]:
            return await respond(text=f"Valid filters: {', '.join(cfg['filters'].keys())}", response_type="ephemeral")
        cfg["filters"][filter_name] = mode.lower() == "on"
        save_automod()
        await respond(text=f":white_check_mark: `{filter_name}` {'enabled' if cfg['filters'][filter_name] else 'disabled'}")

    @app.command("/automod_settings")
    async def automod_settings(ack, command, respond):
        await ack()
        workspace_id = command.get("team_id") or "default"
        args = (command.get("text") or "").split(None, 1)
        if len(args) < 2:
            return await respond(text="Usage: `/automod_settings <delete|cooldown_seconds> <value>`", response_type="ephemeral")
        setting, value = args
        cfg = ENGINE.get_cfg(workspace_id)
        if setting not in {"delete", "cooldown_seconds"}:
            return await respond(text="Invalid setting.", response_type="ephemeral")
        try:
            cfg[setting] = value.lower() == "on" if setting == "delete" else int(value)
        except Exception:
            return await respond(text="Invalid value.", response_type="ephemeral")
        save_automod()
        await respond(text=f":white_check_mark: `{setting}` = `{cfg[setting]}`")
