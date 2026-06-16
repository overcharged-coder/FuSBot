import asyncio
import time
import random
import math
import json
import os
import re
from mentions import mentions_fusbot
from ai_interject import ai_interject_line
from collections import defaultdict, deque, Counter
from typing import Any, Awaitable, Dict, Deque, List, Tuple, Optional, Callable

_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001F5FF"
    "\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF"
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FAFF"
    "☀-⛿"
    "✀-➿"
    "]",
    flags=re.UNICODE,
)

DEBUG = True

def hlog(*x: Any) -> None:
    if not DEBUG:
        return
    ts = time.strftime("%H:%M:%S", time.localtime())
    print(f"[BRAIN {ts}]", *x)

def _now() -> float:
    return time.time()

_word_re = re.compile(r"\w+")
_space_re = re.compile(r"\s+")

def _norm(t: str) -> str:
    return _space_re.sub(" ", (t or "").lower().strip())

def _words(t: str) -> List[str]:
    return _word_re.findall((t or "").lower())

IGNORE_PREFIXES = ("!", "/", ".")

STATE_LURKING = "lurking"
STATE_ENGAGED = "engaged"
STATE_LEADING = "leading"
STATE_WITHDRAWING = "withdrawing"

BASE_REACT_MENTION = 0.23
BASE_REACT_PASSIVE = 0.09
BASE_INTERRUPT_PROB = 0.085
MAX_INTERRUPT_PROB = 0.64
HARD_MIN_GAP_CHANNEL = 7.5
HARD_MIN_GAP_USER = 10.5
SOFT_COOLDOWN_CHANNEL = 18.0
SOFT_COOLDOWN_USER = 24.0
GUILD_EMOJI_HALF_LIFE = 24 * 3600
FATIGUE_WINDOW_SEC = 240.0
FATIGUE_STEP = 0.045
MAX_FATIGUE_PENALTY = 0.34
CULTURE_MEMORY_MAX = 320
CULTURE_HALF_LIFE_SEC = 3200.0
CONTEXT_WINDOW = 14
CONTEXT_ACTIVE_SEC = 70.0
REACTION_DIVERSITY_WINDOW = 22
REACTION_REPEAT_PENALTY = 0.22
READING_WPM = (190, 330)
READING_MIN = 0.14
READING_MAX = 2.3
TYPE_BASE = (0.28, 1.0)
TYPE_PER_CHAR = (0.009, 0.025)
TYPE_MAX = 6.4
TYPE_HESITATION_CHANCE = 0.26
TYPE_HESITATION_RANGE = (0.14, 0.95)
REGRET_CHANCE = 0.012
REGRET_DELAY_RANGE = (4.0, 10.0)
SPEAK_COOLDOWN_BASE = 70.0
EMBARRASSMENT_HALF_LIFE = 195.0
SELF_REFLECT_EVERY = 240.0
PERSIST_EVERY = 180.0
MAX_CHANNEL_BOLDNESS = 1.35
MIN_CHANNEL_BOLDNESS = 0.55

STANCE_BUCKETS = {"agree": "agree", "hype": "agree", "funny": "agree", "disbelief": "disagree"}

LOW_EFFORT = {
    "hi","hey","hello","yo","sup","ok","okay","k","kk","lol","lmao","nah","bruh","yup","nope","bet",
    "true","facts","real","fr","frfr","same","exactly","100%","yep","yup","yeah","mm","mhm","aight",
    "word","sure","idk","i dunno","ight","👍","💀","😭","😂","🤣"
}

FUNNY_KEYS = [
    "lol","lmao","lmfao","rofl","😂","😭","💀","🤣","😹",
    "dead","im dead","i'm dead","im crying","i'm crying","crying","im weak","help",
    "bro","bruh","wtf","what the hell","this killed me","i cant","i can't","who let him cook",
]

HYPE_KEYS = [
    "lets go","let's go","lfg","fire","so fire","goat","the goat","crazy","insane","holy","W","big W",
    "clean","smooth","perfect","elite","top tier","cook","cooked","this goes hard","hard af","this slaps",
]

SAD_KEYS = [
    "sad","im sad","i'm sad","tired","im tired","exhausted","burnt out","drained",
    "upset","cry","crying","depressed","pain","lonely","alone","anxious","stressed",
    "miserable","this sucks","life sucks","cant do this","rough day","bad day","not okay",
]

ACK_KEYS = [
    "thanks","thx","ty","thank you","appreciate","got it","gotcha","ok","okay","cool",
    "sounds good","makes sense","fair","bet","noted","all good","alright","for sure","yep","mm","mhm",
]

AGREE_KEYS = [
    "true","facts","real","fr","frfr","same","exactly","100%","literally","on god","ong",
    "thats right","that's right","you right","u right","correct","absolutely","definitely",
]

DISBELIEF_KEYS = [
    "no way","no shot","cap","bs","bullshit","fake","sure buddy","nah","be fr","be serious",
    "you lying","ur lying","theres no way","there's no way","calling cap","not a chance","yeah right",
]

CONFUSED_KEYS = ["wdym", "what do you mean", "huh", "wait what", "what", "im confused", "i'm confused", "lost me", "hold on", "wait", "??"]
VENT_KEYS = ["im done", "i'm done", "this sucks", "cant do this", "i can't do this", "so annoying", "im tired", "i'm tired", "rough", "hate this"]
TEASE_KEYS = ["bro", "bruh", "be serious", "ain't no way", "you wild", "ur cooked", "you're cooked", "nahhh", "crazy work"]
INVITE_KEYS = ["thoughts", "what do you think", "look at this", "listen", "check this", "bro listen"]
STORY_KEYS = ["so basically", "earlier", "today i", "yesterday", "one time", "bro so", "so then"]

# Slack emoji names (no colons)
DEFAULT_BUCKETS = {
    "ack":      ["+1", "ok_hand", "white_check_mark", "ballot_box_with_check", "saluting_face"],
    "see":      ["eyes", "face_with_peeking_eye", "brain", "memo"],
    "funny":    ["joy", "sob", "skull", "rofl", "joy_cat"],
    "hype":     ["fire", "100", "rocket", "raised_hands", "sparkles"],
    "sad":      ["pensive", "people_hugging", "heart", "disappointed", "smiling_face_with_tear"],
    "question": ["question", "thinking_face", "face_with_monocle", "thought_balloon"],
    "agree":    ["white_check_mark", "100", "handshake", "+1", "saluting_face"],
    "disbelief":["baseball", "flushed", "raised_eyebrow", "neutral_face", "roll_eyes"],
}

def _has_any(text: str, keys: List[str]) -> bool:
    t = (text or "").lower()
    return any(k in t for k in keys)

def _is_question(content: str) -> bool:
    if not content:
        return False
    t = content.lower()
    if "?" in content and len(content) > 7:
        return True
    if len(t) < 6:
        return False
    return any(t.startswith(k + " ") for k in ("why","how","what","when","where","who","which","wait","hold up"))

def _low_effort(text: str) -> bool:
    t = _norm(text)
    if not t:
        return True
    if t in {"hi","hey","hello","yo","sup"}:
        return False
    if len(t) <= 3:
        return True
    return t in LOW_EFFORT

MENTION_ROAST_KEYS = {"roast","cook","flame","destroy","smoke","pack","clown","violate"}
MENTION_SOCIAL_KEYS = {"yo","hey","hi","sup","bro","listen","look","thoughts","opinion"}

def _strip_fusbot_refs(text: str) -> str:
    t = text or ""
    t = re.sub(r"<@[A-Z0-9]+>", "", t)
    t = re.sub(r"\bfusbot\b", "", t, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", t).strip()

def _mention_intent(content: str) -> str:
    stripped = _strip_fusbot_refs(content or "")
    t = _norm(stripped)
    words = set(_words(t))
    if not t:
        return "social_ping"
    if words & MENTION_ROAST_KEYS:
        return "roast_request"
    if _is_question(t):
        return "chat_question"
    if t in {"yo","hey","hi","sup","bro","what","wdym","huh"}:
        return "social_ping"
    if words & MENTION_SOCIAL_KEYS:
        return "social_ping"
    if len(t) >= 5:
        return "chat_question"
    return "social_ping"

def _circadian_penalty() -> float:
    lt = time.localtime()
    hour = lt.tm_hour
    wday = lt.tm_wday
    if 2 <= hour <= 6:
        return 0.13
    if hour <= 1:
        return 0.08
    if wday >= 5 and hour >= 23:
        return 0.07
    return 0.0

def _clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x

def _sigmoid(x: float) -> float:
    if x < -60: return 0.0
    if x > 60: return 1.0
    return 1.0 / (1.0 + math.exp(-x))


class BrainStore:
    def __init__(self, path: str):
        self.path = path
        self.last_save = 0.0

    def load(self) -> Dict[str, Any]:
        if not self.path or not os.path.exists(self.path):
            return {}
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def save(self, data: Dict[str, Any]) -> None:
        if not self.path:
            return
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
            os.replace(tmp, self.path)
            self.last_save = _now()
        except Exception:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass


class HumanBrain:
    def __init__(self, persist_path: str = "human_brain_state.json", is_roast_mode=None):
        self.store = BrainStore(persist_path)
        self._social_momentum: Dict[str, Deque[int]] = defaultdict(lambda: deque(maxlen=6))
        self._emoji_boredom_channel: Dict[str, Counter] = defaultdict(Counter)
        self._emoji_boredom_user: Dict[str, Counter] = defaultdict(Counter)
        self._social_bias: Dict[str, float] = defaultdict(float)
        self._rng = random.Random()
        self._topic_memory: Dict[Tuple[str, str], Tuple[float, float]] = {}
        self._last_channel_time: Dict[str, float] = {}
        self._last_user_time: Dict[str, float] = {}
        self._recent_reacts: Deque[float] = deque()
        self._stance_memory: Dict[Tuple[str, str], Tuple[str, float]] = {}
        self._recent_emojis: Deque[str] = deque(maxlen=REACTION_DIVERSITY_WINDOW)
        self._channel_msgs: Dict[str, Deque[Tuple[float, str]]] = defaultdict(lambda: deque(maxlen=CONTEXT_WINDOW))
        self._channel_culture: Dict[str, Deque[Tuple[float, str]]] = defaultdict(lambda: deque(maxlen=CULTURE_MEMORY_MAX))
        self._channel_emoji_counts: Dict[str, Counter] = defaultdict(Counter)
        self.is_roast_mode = is_roast_mode or (lambda uid: False)
        self._guild_emoji_culture: Dict[str, Counter] = defaultdict(Counter)
        self._user_engaged_memory: Dict[str, Deque[Tuple[float, str, str]]] = defaultdict(lambda: deque(maxlen=50))
        self._guild_memory: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "summary": "", "topics": {}, "inside_jokes": [], "important_members": {}, "last_active": 0.0,
        })
        self._channel_memory: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "purpose": "general",
            "purpose_scores": {"technical": 0.0, "social/funny": 0.0, "general": 1.0},
            "topics": {}, "open_loops": [], "inside_jokes": [], "last_active": 0.0,
        })
        self._guild_emoji_timestamps: Dict[str, Deque[Tuple[float, str]]] = defaultdict(lambda: deque(maxlen=2000))
        self._user_familiarity: Dict[str, int] = defaultdict(int)
        self._user_channel_affinity: Dict[Tuple[str, str], int] = defaultdict(int)
        self._user_recent_emoji: Dict[str, Deque[str]] = defaultdict(lambda: deque(maxlen=10))
        self._user_emoji_pref: Dict[str, Counter] = defaultdict(Counter)
        self._user_received_reacts: Dict[str, int] = defaultdict(int)
        self._user_given_reacts: Dict[str, int] = defaultdict(int)
        self._moods = ["neutral", "warm", "tired", "silly", "focused"]
        self._self_react_memory: Dict[str, float] = {}
        self._pending_react_back: Dict[Tuple[str, str], Tuple[float, str, str]] = {}
        self._pending_self_reacts: Deque[Tuple[float, str, str, str]] = deque()
        self._seen_messages: Deque[str] = deque(maxlen=500)
        self._current_mood = self._rng.choice(self._moods)
        self._channel_state: Dict[str, str] = defaultdict(lambda: STATE_LURKING)
        self._last_speak_time: Dict[str, float] = {}
        self._last_speak_confidence: Dict[str, float] = defaultdict(lambda: 0.56)
        self._last_channel_embarrassment: Dict[str, float] = defaultdict(float)
        self._delayed_reacts: Deque[Tuple[float, str, str, str, str, str]] = deque()
        self._react_outcomes_user: Dict[str, Deque[Tuple[float, str, int]]] = defaultdict(lambda: deque(maxlen=120))
        self._interject_outcomes_channel: Dict[str, Deque[Tuple[float, int]]] = defaultdict(lambda: deque(maxlen=120))
        self._channel_profile: Dict[str, Dict[str, float]] = defaultdict(lambda: {
            "formality": 0.45, "emoji_tolerance": 0.55, "chaos": 0.45, "boldness": 1.0
        })
        self._guild_profile: Dict[str, Dict[str, float]] = defaultdict(lambda: {"boldness": 1.0})
        self._last_reflect = _now()
        self._last_persist = _now()
        self._load()

    def mark_busy(self, channel_id: str) -> None:
        self._last_speak_time[channel_id] = _now()

    def _extract_topic(self, content: str) -> Optional[str]:
        w = _words(content)
        if len(w) < 4:
            return None
        stop = {"the","a","an","and","or","but","to","of","is","are","this","that"}
        core = [x for x in w if x not in stop]
        return core[0] if core else None

    def _load(self) -> None:
        data = self.store.load()
        if not data:
            return
        try:
            self._current_mood = data.get("mood", self._current_mood)
            for k, v in data.get("guild_profile", {}).items():
                if isinstance(v, dict):
                    self._guild_profile[k].update({kk: float(vv) for kk, vv in v.items()})
            for k, v in data.get("channel_profile", {}).items():
                if isinstance(v, dict):
                    self._channel_profile[k].update({kk: float(vv) for kk, vv in v.items()})
            for k, v in data.get("user_emoji_pref", {}).items():
                if isinstance(v, dict):
                    c = Counter()
                    for ek, ev in v.items():
                        c[ek] = int(ev)
                    self._user_emoji_pref[k] = c
            for k, v in data.get("user_familiarity", {}).items():
                try: self._user_familiarity[k] = int(v)
                except Exception: pass
            for k, v in data.get("user_received_reacts", {}).items():
                try: self._user_received_reacts[k] = int(v)
                except Exception: pass
            for k, v in data.get("user_given_reacts", {}).items():
                try: self._user_given_reacts[k] = int(v)
                except Exception: pass
            for k, v in data.get("guild_emoji_culture", {}).items():
                self._guild_emoji_culture[k] = Counter(v)
            for k, v in data.get("guild_memory", {}).items():
                if isinstance(v, dict):
                    self._guild_memory[k].update(v)
            for k, v in data.get("channel_memory", {}).items():
                if isinstance(v, dict):
                    self._channel_memory[k].update(v)
                    self._channel_memory[k].setdefault("purpose", "general")
                    self._channel_memory[k].setdefault("purpose_scores", {"technical": 0.0, "social/funny": 0.0, "general": 1.0})
            for k, v in data.get("user_engaged_memory", {}).items():
                dq = deque(maxlen=50)
                for entry in v[-50:]:
                    if isinstance(entry, (list, tuple)) and len(entry) >= 3:
                        dq.append((float(entry[0]), str(entry[1]), str(entry[2])))
                self._user_engaged_memory[k] = dq
            for k, v in data.get("emoji_boredom", {}).items():
                for e, lvl in v.items():
                    self._emoji_boredom_channel[k][e] = min(float(lvl) * 0.65, 3.5)
        except Exception:
            pass

    def _dump(self) -> Dict[str, Any]:
        return {
            "mood": self._current_mood,
            "guild_profile": {k: dict(v) for k, v in self._guild_profile.items()},
            "channel_profile": {k: dict(v) for k, v in self._channel_profile.items()},
            "guild_memory": {k: dict(v) for k, v in self._guild_memory.items()},
            "channel_memory": {k: dict(v) for k, v in self._channel_memory.items()},
            "user_emoji_pref": {k: dict(c) for k, c in self._user_emoji_pref.items()},
            "user_familiarity": {k: int(v) for k, v in self._user_familiarity.items()},
            "user_received_reacts": {k: int(v) for k, v in self._user_received_reacts.items()},
            "user_given_reacts": {k: int(v) for k, v in self._user_given_reacts.items()},
            "guild_emoji_culture": {k: dict(c) for k, c in self._guild_emoji_culture.items()},
            "user_engaged_memory": {k: list(dq) for k, dq in self._user_engaged_memory.items()},
            "emoji_boredom": self._dump_emoji_boredom(),
        }

    def _dump_emoji_boredom(self):
        out = {}
        for cid, c in self._emoji_boredom_channel.items():
            top = [(e, v) for e, v in c.items() if v >= 2.0]
            if top:
                out[cid] = dict(sorted(top, key=lambda x: -x[1])[:3])
        return out

    def _update_channel_purpose(self, channel_id: str, text: str) -> None:
        cm = self._channel_memory[channel_id]
        scores = cm.setdefault("purpose_scores", {"technical": 0.0, "social/funny": 0.0, "general": 1.0})
        tl = (text or "").lower()
        for k in scores:
            scores[k] *= 0.96
        tech_hits = sum(1 for x in ("python","code","bug","error","function","traceback","json","api","class","method","stack","database","sql","exception") if x in tl)
        social_hits = sum(1 for x in ("lol","lmao","😂","😭","💀","🤣","meme","bro","bruh","nah","wild","crazy","lmfao") if x in tl)
        q_hits = sum(1 for x in ("how do i","how can i","can someone","stuck","any idea","what should i","why is") if x in tl)
        if tech_hits: scores["technical"] += 1.2 + tech_hits * 0.35
        if social_hits: scores["social/funny"] += 1.0 + social_hits * 0.30
        if not tech_hits and not social_hits: scores["general"] += 0.5
        if q_hits and tech_hits: scores["technical"] += 0.6
        elif q_hits: scores["general"] += 0.3
        cm["purpose"] = max(scores, key=scores.get)

    def observe_semantic_memory_slack(self, uid: str, channel_id: str, workspace_id: str, text: str) -> None:
        if not text:
            return
        gm = self._guild_memory[workspace_id]
        cm = self._channel_memory[channel_id]
        gm["last_active"] = _now()
        cm["last_active"] = _now()
        gm["important_members"][uid] = gm["important_members"].get(uid, 0) + 1
        kws = [w for w in _words(text) if len(w) >= 4][:10]
        for kw in kws:
            gm["topics"][kw] = gm["topics"].get(kw, 0) + 1
            cm["topics"][kw] = cm["topics"].get(kw, 0) + 1
        self._update_channel_purpose(channel_id, text)
        tl = text.lower()
        if any(x in tl for x in ("how do i","how can i","can someone","stuck","any idea","what should i")):
            loop = text[:160]
            if loop not in cm["open_loops"]:
                cm["open_loops"].append(loop)
                cm["open_loops"] = cm["open_loops"][-12:]

    def get_guild_memory_hint(self, workspace_id: str) -> str:
        gm = self._guild_memory.get(workspace_id)
        if not gm:
            return ""
        top_topics = sorted(gm.get("topics", {}).items(), key=lambda kv: kv[1], reverse=True)[:6]
        topic_list = [k for k, _ in top_topics]
        lines = []
        if topic_list:
            lines.append(f"- workspace topics: {topic_list}")
        if gm.get("summary"):
            lines.append(f"- workspace summary: {gm['summary']}")
        return "workspace context:\n" + "\n".join(lines) + "\n" if lines else ""

    def get_channel_memory_hint(self, channel_id: str) -> str:
        cm = self._channel_memory.get(channel_id)
        if not cm:
            return ""
        top_topics = sorted(cm.get("topics", {}).items(), key=lambda kv: kv[1], reverse=True)[:6]
        topic_list = [k for k, _ in top_topics]
        lines = []
        if cm.get("purpose"):
            lines.append(f"- channel purpose: {cm['purpose']}")
        if topic_list:
            lines.append(f"- channel topics: {topic_list}")
        if cm.get("open_loops"):
            lines.append(f"- recent unresolved questions: {cm['open_loops'][-3:]}")
        return "channel context:\n" + "\n".join(lines) + "\n" if lines else ""

    def remember_user_engagement(self, user_id: str, channel_id: str, content: str) -> None:
        content = re.sub(r"\s+", " ", content).strip()
        if len(content) > 220:
            content = content[:220] + "…"
        self._user_engaged_memory[user_id].append((_now(), channel_id, content))

    def get_contextual_memory(self, user_id: str, channel_id: str, bucket: str, limit: int = 12) -> List[str]:
        dq = self._user_engaged_memory.get(user_id)
        if not dq:
            return []
        now = _now()
        scored = []
        for ts, cid, txt in dq:
            if _low_effort(txt):
                continue
            score = 0.45 if cid == channel_id else 0.0
            tl = txt.lower()
            if bucket == "funny" and _has_any(tl, FUNNY_KEYS): score += 0.30
            elif bucket == "hype" and _has_any(tl, HYPE_KEYS): score += 0.30
            elif bucket == "sad" and _has_any(tl, SAD_KEYS): score += 0.30
            elif bucket == "disbelief" and _has_any(tl, DISBELIEF_KEYS): score += 0.30
            score += max(0.0, 1.0 - (now - ts) / 1800.0)
            scored.append((score, txt))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [txt for _, txt in scored[:limit]]

    def get_user_engagement_memory(self, user_id: str, limit: int = 15) -> List[str]:
        dq = self._user_engaged_memory.get(user_id)
        if not dq:
            return []
        out = []
        seen = set()
        for _, _, txt in reversed(dq):
            norm = txt.lower()
            if norm in seen or _low_effort(txt):
                continue
            seen.add(norm)
            out.append(txt)
            if len(out) >= limit:
                break
        return list(reversed(out))

    def get_recent_channel_lines(self, channel_id: str, limit: int = 6) -> List[str]:
        dq = self._channel_msgs.get(channel_id)
        if not dq:
            return []
        out = []
        seen = set()
        for _, txt in reversed(dq):
            norm = _norm(txt)
            if not norm or norm in seen or _low_effort(txt):
                continue
            seen.add(norm)
            out.append(txt)
            if len(out) >= limit:
                break
        return list(reversed(out))

    def maybe_persist(self) -> None:
        t = _now()
        if t - self._last_persist < PERSIST_EVERY:
            return
        self._last_persist = t
        self.store.save(self._dump())

    def _fatigue_penalty(self) -> float:
        cutoff = _now() - FATIGUE_WINDOW_SEC
        while self._recent_reacts and self._recent_reacts[0] < cutoff:
            self._recent_reacts.popleft()
        return min(len(self._recent_reacts) * FATIGUE_STEP, MAX_FATIGUE_PENALTY)

    def _soft_cooldown_penalty(self, channel_id: str, user_id: str) -> float:
        t = _now()
        dc = t - self._last_channel_time.get(channel_id, 0.0)
        du = t - self._last_user_time.get(user_id, 0.0)
        pc = 0.0 if dc >= SOFT_COOLDOWN_CHANNEL else (1.0 - dc / SOFT_COOLDOWN_CHANNEL) * 0.20
        pu = 0.0 if du >= SOFT_COOLDOWN_USER else (1.0 - du / SOFT_COOLDOWN_USER) * 0.25
        return pc + pu

    def _cooldown_hard(self, channel_id: str, user_id: str) -> bool:
        t = _now()
        if t - self._last_channel_time.get(channel_id, 0.0) < HARD_MIN_GAP_CHANNEL:
            return True
        if t - self._last_user_time.get(user_id, 0.0) < HARD_MIN_GAP_USER:
            return True
        return False

    def observe_channel_message(self, channel_id: str, content: str, ts: Optional[str] = None) -> None:
        if ts is not None:
            if ts in self._seen_messages:
                return
            self._seen_messages.append(ts)
        if not content:
            return
        self._channel_msgs[channel_id].append((_now(), content))
        self._update_channel_profile_from_text(channel_id, content)

    def observe_reaction(self, channel_id: str, user_id: str, emoji: str, guild_id: Optional[str] = None) -> None:
        if not emoji:
            return
        self._culture_decay(channel_id)
        t = _now()
        self._channel_culture[channel_id].append((t, emoji))
        self._channel_emoji_counts[channel_id][emoji] += 1
        self._user_emoji_pref[user_id][emoji] += 1
        self._user_given_reacts[user_id] += 1
        if guild_id:
            self._guild_emoji_culture[guild_id][emoji] += 1
            self._guild_emoji_timestamps[guild_id].append((_now(), emoji))

    def observe_received_reaction(self, user_id: str) -> None:
        self._user_received_reacts[user_id] += 1

    def observe_reaction_outcome(self, user_id: str, emoji: str, channel_id: str, got_back: bool) -> None:
        t = _now()
        self._react_outcomes_user[user_id].append((t, emoji, 1 if got_back else 0))
        if got_back:
            self._social_momentum[channel_id].append(+1)
            self._social_bias[user_id] = _clamp(self._social_bias[user_id] + 0.04, -0.6, 0.6)
        else:
            self._social_momentum[channel_id].append(-1)
            self._social_bias[user_id] = _clamp(self._social_bias[user_id] - 0.05, -0.6, 0.6)

    def observe_reaction_back_from_event(self, reactor_id: str, message_ts: str):
        key = (reactor_id, message_ts)
        pending = self._pending_react_back.get(key)
        if not pending:
            return
        ts, emoji, cid = pending
        age = _now() - ts
        got_back = 0.6 <= age <= 25.0
        self.observe_reaction_outcome(reactor_id, emoji, cid, got_back)
        del self._pending_react_back[key]

    def observe_interject_outcome(self, channel_id: str, got_reply: bool) -> None:
        t = _now()
        self._interject_outcomes_channel[channel_id].append((t, 1 if got_reply else 0))
        self._social_momentum[channel_id].append(+1 if got_reply else -1)
        if not got_reply:
            for uid in list(self._social_bias.keys()):
                self._social_bias[uid] *= 0.985

    def _culture_decay(self, channel_id: str) -> None:
        t = _now()
        dq = self._channel_culture[channel_id]
        while dq:
            ts, emoji = dq[0]
            if t - ts <= CULTURE_HALF_LIFE_SEC:
                break
            dq.popleft()
            if self._channel_emoji_counts[channel_id][emoji] > 0:
                self._channel_emoji_counts[channel_id][emoji] -= 1
                if self._channel_emoji_counts[channel_id][emoji] <= 0:
                    del self._channel_emoji_counts[channel_id][emoji]

    def _guild_culture_decay(self, guild_id: str) -> None:
        now = _now()
        dq = self._guild_emoji_timestamps[guild_id]
        counts = self._guild_emoji_culture[guild_id]
        while dq:
            ts, emoji = dq[0]
            if now - ts <= GUILD_EMOJI_HALF_LIFE:
                break
            dq.popleft()
            if counts[emoji] > 0:
                counts[emoji] -= 1
                if counts[emoji] <= 0:
                    del counts[emoji]

    def _guild_top_emojis(self, guild_id: str, k: int = 8) -> List[str]:
        self._guild_culture_decay(guild_id)
        counts = self._guild_emoji_culture[guild_id]
        return [e for e, _ in counts.most_common(k)] if counts else []

    def _culture_top_emojis(self, channel_id: str, k: int = 8) -> List[str]:
        counts = self._channel_emoji_counts[channel_id]
        return [e for e, _ in counts.most_common(k)] if counts else []

    def _diversity_penalty(self, emoji: str) -> float:
        repeats = sum(1 for e in self._recent_emojis if e == emoji)
        return min(repeats * (REACTION_REPEAT_PENALTY / 2.0), REACTION_REPEAT_PENALTY) if repeats > 0 else 0.0

    def _maybe_shift_mood(self) -> None:
        r = self._rng.random()
        if r < 0.016: self._current_mood = self._rng.choice(self._moods)
        elif r < 0.018: self._current_mood = "tired"
        elif r < 0.020: self._current_mood = "warm"

    def _context_activity(self, channel_id: str) -> float:
        q = self._channel_msgs[channel_id]
        if len(q) < 2:
            return 0.0
        t = _now()
        recent = [ts for ts, _ in q if t - ts <= CONTEXT_ACTIVE_SEC]
        return min(len(recent) / 6.0, 1.0) if recent else 0.0

    def _reciprocity_bonus(self, user_id: str) -> float:
        given = self._user_given_reacts.get(user_id, 0)
        received = self._user_received_reacts.get(user_id, 0)
        if given <= 0:
            return 0.0
        ratio = min(received / max(given, 1), 2.0)
        return min((ratio - 0.45) * 0.075, 0.10) if ratio > 0.45 else 0.0

    def _reaction_outcome_bias(self, user_id: str, emoji: str) -> float:
        dq = self._react_outcomes_user.get(user_id)
        if not dq:
            return 0.0
        recent = list(dq)[-70:]
        hits = sum(ok for _, e, ok in recent if e == emoji)
        tot = sum(1 for _, e, _ in recent if e == emoji)
        return (hits / tot - 0.45) * 0.22 if tot > 3 else 0.0

    def _pick_bucket(self, text_l: str, content: str) -> str:
        if _is_question(content): return "question"
        if _has_any(text_l, SAD_KEYS): return "sad"
        if _has_any(text_l, FUNNY_KEYS): return "funny"
        if _has_any(text_l, HYPE_KEYS): return "hype"
        if _has_any(text_l, ACK_KEYS): return "ack"
        if _has_any(text_l, AGREE_KEYS): return "agree"
        if _has_any(text_l, DISBELIEF_KEYS): return "disbelief"
        if len(content) > 120 or len(content.strip()) <= 8: return "see"
        return "ack"

    def _mood_tweak_bucket(self, bucket: str, channel_id: Optional[str] = None) -> str:
        m = self._current_mood
        if channel_id is not None:
            emb = self._last_channel_embarrassment[channel_id]
            conf = self._last_speak_confidence[channel_id]
            if emb > 0.50:
                if bucket in ("funny","hype","disbelief","tease"): return "see"
            elif conf > 0.68:
                if bucket in ("ack","see") and self._rng.random() < 0.35: return "agree"
        if m == "tired":
            if bucket in ("funny","hype","tease"): return "see"
            return "sad" if bucket in ("sad","vent") else "see"
        if m == "warm":
            if bucket in ("ack","agree","invite"): return "agree"
            if bucket in ("sad","vent"): return "sad"
            return bucket
        if m == "silly":
            return "funny" if bucket in ("ack","agree","disbelief","tease") else bucket
        if m == "focused":
            return "ack" if bucket in ("funny","hype","tease") else bucket
        return bucket

    def _candidate_emojis(self, channel_id: str, user_id: str, bucket: str, guild_id: Optional[str] = None) -> List[str]:
        base = list(DEFAULT_BUCKETS.get(bucket, DEFAULT_BUCKETS["ack"]))
        self._culture_decay(channel_id)
        culture = self._culture_top_emojis(channel_id, k=10)
        guild_emojis = self._guild_top_emojis(guild_id, k=6) if guild_id else []
        prefs = [e for e, _ in self._user_emoji_pref[user_id].most_common(7)]
        pool = base + culture * 2 + guild_emojis + prefs
        seen = set()
        uniq = [e for e in pool if e and e not in seen and not seen.add(e)]
        return uniq[:18] if uniq else base

    def _choose_emoji(self, channel_id: str, user_id: str, bucket: str, guild_id: Optional[str] = None) -> str:
        bucket = self._mood_tweak_bucket(bucket, channel_id)
        cand = self._candidate_emojis(channel_id, user_id, bucket, guild_id)
        prof = self._channel_profile[channel_id]
        emoji_tol = _clamp(prof.get("emoji_tolerance", 0.55), 0.0, 1.0)
        weights = []
        for e in cand:
            w = 1.0
            w += min(self._user_emoji_pref[user_id].get(e, 0) * 0.055, 0.58)
            w += min(self._channel_emoji_counts[channel_id].get(e, 0) * 0.025, 0.70)
            w += self._reaction_outcome_bias(user_id, e)
            w -= self._diversity_penalty(e)
            chan_bored = self._emoji_boredom_channel[channel_id].get(e, 0)
            user_bored = self._emoji_boredom_user[user_id].get(e, 0)
            if chan_bored >= 3: w *= max(0.35, 1.0 - chan_bored * 0.12)
            if user_bored >= 4: w *= max(0.40, 1.0 - user_bored * 0.10)
            if e in self._user_recent_emoji[user_id]: w *= 0.56
            if e in self._recent_emojis: w *= 0.80
            w *= (0.78 + 0.44 * emoji_tol)
            weights.append(max(w, 0.12))
        total = sum(weights)
        r = self._rng.random() * total if total > 0 else 0.0
        acc = 0.0
        for e, w in zip(cand, weights):
            acc += w
            if r <= acc:
                return e
        return self._rng.choice(cand) if cand else "+1"

    def _mark_react(self, channel_id: str, user_id: str, emoji: str, guild_id: Optional[str] = None) -> None:
        t = _now()
        self._last_channel_time[channel_id] = t
        self._last_user_time[user_id] = t
        self._recent_reacts.append(t)
        self._recent_emojis.append(emoji)
        self._emoji_boredom_channel[channel_id][emoji] += 1
        self._emoji_boredom_user[user_id][emoji] += 1
        self._user_recent_emoji[user_id].append(emoji)
        self._user_familiarity[user_id] += 1
        self._user_channel_affinity[(user_id, channel_id)] += 1

    def _len_bonus(self, content: str) -> float:
        return min(len(content) / 260.0, 0.24)

    def _decay_emoji_boredom(self):
        for cid, c in self._emoji_boredom_channel.items():
            for e in list(c.keys()):
                c[e] *= 0.92
                if c[e] < 0.6: del c[e]
        for uid, c in self._emoji_boredom_user.items():
            for e in list(c.keys()):
                c[e] *= 0.90
                if c[e] < 0.6: del c[e]

    def _familiarity_bonus(self, user_id: str) -> float:
        return min(self._user_familiarity[user_id] * 0.010, 0.12)

    def _affinity_bonus(self, user_id: str, channel_id: str) -> float:
        return min(self._user_channel_affinity[(user_id, channel_id)] * 0.0065, 0.07)

    def _link_penalty(self, content: str) -> float:
        if ("http://" in content or "https://" in content) and len(content) < 55:
            return 0.09
        return 0.0

    def _caps_bonus(self, content: str) -> float:
        return 0.045 if len(content) > 6 and content.isupper() else 0.0

    def _channel_boldness(self, guild_id: str, channel_id: str) -> float:
        g = self._guild_profile[guild_id].get("boldness", 1.0)
        c = self._channel_profile[channel_id].get("boldness", 1.0)
        return _clamp(g * c, MIN_CHANNEL_BOLDNESS, MAX_CHANNEL_BOLDNESS)

    def p_react_slack(self, uid: str, channel_id: str, workspace_id: str, content: str, mentioned: bool) -> float:
        p = BASE_REACT_MENTION if mentioned else BASE_REACT_PASSIVE
        stance = self._stance_memory.get((uid, channel_id))
        if stance:
            st, ts = stance
            age = _now() - ts
            if age < 180.0:
                p += 0.06 if st == "agree" else 0.04
            elif age > 300.0:
                self._stance_memory.pop((uid, channel_id), None)
        topic = self._extract_topic(content)
        if topic:
            mem = self._topic_memory.get((channel_id, topic))
            if mem:
                opinion, ts = mem
                if _now() - ts < 3600:
                    p += opinion * 0.06
        mom = sum(self._social_momentum[channel_id])
        if mom >= 3: p *= 1.12
        elif mom <= -3: p *= 0.78
        bold = self._channel_boldness(workspace_id, channel_id)
        p += self._len_bonus(content)
        p += self._familiarity_bonus(uid)
        p += self._social_bias.get(uid, 0.0) * 0.08
        p += self._affinity_bonus(uid, channel_id)
        p += self._reciprocity_bonus(uid)
        p += self._context_activity(channel_id) * 0.07
        p += self._caps_bonus(content)
        p -= self._fatigue_penalty()
        p -= _circadian_penalty()
        p -= self._soft_cooldown_penalty(channel_id, uid)
        p -= self._link_penalty(content)
        prof = self._channel_profile[channel_id]
        formality = _clamp(prof.get("formality", 0.45), 0.0, 1.0)
        emoji_tol = _clamp(prof.get("emoji_tolerance", 0.55), 0.0, 1.0)
        chaos = _clamp(prof.get("chaos", 0.45), 0.0, 1.0)
        p *= (0.86 + 0.28 * bold)
        p *= (0.88 + 0.18 * emoji_tol)
        p *= (0.90 + 0.12 * chaos)
        p *= (1.06 - 0.18 * formality)
        if self._current_mood == "tired": p *= 0.80
        elif self._current_mood == "silly": p *= 1.07
        elif self._current_mood == "warm": p *= 1.04
        return _clamp(p, 0.0, 0.90)

    async def human_delay_slack(self, reply_text: str = "") -> None:
        txt = reply_text or ""
        w = max(len(_words(txt)), 1)
        wpm = self._rng.uniform(*READING_WPM)
        read_time = min(max((w / wpm) * 60.0, READING_MIN), READING_MAX)
        base = self._rng.uniform(*TYPE_BASE)
        per = self._rng.uniform(*TYPE_PER_CHAR)
        type_time = base + min(len(txt) * per, TYPE_MAX)
        total = read_time + type_time
        chunks = max(1, int(total / self._rng.uniform(1.15, 2.0)))
        remaining = total
        for _ in range(chunks):
            d = min(remaining, self._rng.uniform(0.50, 1.55))
            remaining -= d
            await asyncio.sleep(d)
            if self._rng.random() < TYPE_HESITATION_CHANCE:
                await asyncio.sleep(self._rng.uniform(*TYPE_HESITATION_RANGE))

    def _decay_embarrassment(self, channel_id: str) -> None:
        t = _now()
        last = self._last_speak_time.get(channel_id)
        if not last:
            return
        age = t - last
        if age <= 0:
            return
        self._last_channel_embarrassment[channel_id] *= math.exp(-age / EMBARRASSMENT_HALF_LIFE)

    def _update_channel_state(self, channel_id: str) -> None:
        emb = self._last_channel_embarrassment[channel_id]
        conf = self._last_speak_confidence[channel_id]
        prof = self._channel_profile[channel_id]
        bold = _clamp(prof.get("boldness", 1.0), MIN_CHANNEL_BOLDNESS, MAX_CHANNEL_BOLDNESS)
        if emb > 0.62: self._channel_state[channel_id] = STATE_WITHDRAWING
        elif conf > (0.69 - (bold - 1.0) * 0.10): self._channel_state[channel_id] = STATE_LEADING
        elif conf > 0.50: self._channel_state[channel_id] = STATE_ENGAGED
        else: self._channel_state[channel_id] = STATE_LURKING

    def _dynamic_speak_cooldown(self, channel_id: str) -> float:
        st = self._channel_state[channel_id]
        prof = self._channel_profile[channel_id]
        chaos = _clamp(prof.get("chaos", 0.45), 0.0, 1.0)
        formality = _clamp(prof.get("formality", 0.45), 0.0, 1.0)
        base = SPEAK_COOLDOWN_BASE
        if st == STATE_LEADING: base = 30.0
        elif st == STATE_ENGAGED: base = 44.0
        elif st == STATE_WITHDRAWING: base = 95.0
        base *= (0.88 + 0.30 * formality)
        base *= (1.05 - 0.25 * chaos)
        if self._current_mood == "tired": base *= 1.15
        elif self._current_mood == "silly": base *= 0.90
        return _clamp(base, 18.0, 140.0)

    def _silence_pressure(self, channel_id: str) -> float:
        q = self._channel_msgs[channel_id]
        if not q: return 0.30
        last_ts, _ = q[-1]
        age = _now() - last_ts
        if age < 5.5: return 0.0
        if age > 38.0: return 0.40
        return min((age - 5.5) / (38.0 - 5.5), 1.0) * 0.40

    def _conversation_pressure(self, channel_id: str) -> float:
        q = self._channel_msgs[channel_id]
        if len(q) < 3: return 0.0
        t = _now()
        recent = [(ts, msg) for ts, msg in q if t - ts < 50.0]
        if len(recent) < 3: return 0.0
        lengths = [len(m) for _, m in recent]
        avg_len = sum(lengths) / len(lengths)
        density = min(len(recent) / 7.0, 1.0)
        emo = 0.0
        for _, m in recent:
            ml = m.lower()
            emo += 0.06 if "??" in m else 0.0
            emo += 0.05 if "wtf" in ml else 0.0
            emo += 0.04 if "bro" in ml or "bruh" in ml else 0.0
        return min(density * 0.30 + min(avg_len / 160.0, 0.20) + min(emo, 0.22), 0.70)

    def _unanswered_question_pressure(self, channel_id: str) -> float:
        q = self._channel_msgs[channel_id]
        if not q: return 0.0
        ts, msg = q[-1]
        if not _is_question(msg): return 0.0
        age = _now() - ts
        if age < 3.8 or age > 36.0: return 0.0
        return min((age - 3.8) / (36.0 - 3.8), 1.0) * 0.55

    def _relevance_pressure_slack(self, uid: str, channel_id: str) -> float:
        sc = min(self._user_channel_affinity[(uid, channel_id)] * 0.025, 0.16)
        sc += min(self._user_familiarity[uid] * 0.018, 0.13)
        return sc

    def _confidence_decay(self, channel_id: str) -> float:
        base = self._last_speak_confidence[channel_id]
        decay = 1.0 - min(self._last_channel_embarrassment[channel_id], 0.88)
        return max(base * decay, 0.22)

    def _interject_success_bias(self, channel_id: str) -> float:
        dq = self._interject_outcomes_channel.get(channel_id)
        if not dq: return 0.0
        recent = list(dq)[-70:]
        if len(recent) < 8: return 0.0
        return (sum(v for _, v in recent) / len(recent) - 0.45) * 0.22

    def _social_risk(self, channel_id: str) -> float:
        emb = self._last_channel_embarrassment[channel_id]
        fat = self._fatigue_penalty()
        circ = _circadian_penalty()
        st = self._channel_state[channel_id]
        risk = emb * 0.70 + fat * 0.65 + circ * 0.55
        if st == STATE_WITHDRAWING: risk += 0.12
        if self._current_mood == "tired": risk += 0.08
        return _clamp(risk, 0.0, 1.0)

    def _update_channel_profile_from_text(self, channel_id: str, content: str) -> None:
        prof = self._channel_profile[channel_id]
        t = content or ""
        L = len(t)
        tl = t.lower()
        emoji_count = len(_EMOJI_RE.findall(t))
        punct = t.count("!") + t.count("?")
        caps = 1 if (L > 6 and t.isupper()) else 0
        shorty = 1 if L <= 20 else 0
        linky = 1 if ("http://" in t or "https://" in t) else 0
        slang = 1 if any(x in tl for x in ("bruh","bro","nah","fr","ong","lfg","wtf")) else 0
        laugh = 1 if any(x in tl for x in ("lol","lmao","😂","😭","💀","🤣")) else 0
        formality_target = 0.55 + 0.08*linky + 0.10*(1-shorty) - 0.12*slang - 0.08*laugh - 0.06*(emoji_count > 0)
        emoji_tol_target = 0.52 + 0.18*(emoji_count > 0) + 0.10*laugh - 0.10*(formality_target > 0.60)
        chaos_target = 0.45 + 0.12*(punct >= 2) + 0.10*slang + 0.08*laugh + 0.06*caps - 0.08*linky
        a = 0.020
        prof["formality"] = _clamp((1-a)*prof.get("formality", 0.45) + a*_clamp(formality_target, 0.0, 1.0), 0.0, 1.0)
        prof["emoji_tolerance"] = _clamp((1-a)*prof.get("emoji_tolerance", 0.55) + a*_clamp(emoji_tol_target, 0.0, 1.0), 0.0, 1.0)
        prof["chaos"] = _clamp((1-a)*prof.get("chaos", 0.45) + a*_clamp(chaos_target, 0.0, 1.0), 0.0, 1.0)

    def should_interject_probability_slack(self, uid: str, channel_id: str, workspace_id: str, content: str) -> float:
        cid = channel_id
        self._decay_embarrassment(cid)
        self._update_channel_state(cid)
        cooldown = self._dynamic_speak_cooldown(cid)
        if _now() - self._last_speak_time.get(cid, 0.0) < cooldown:
            return 0.0
        if _low_effort(content):
            return 0.0
        mom = sum(self._social_momentum[cid])
        mom_bias = 0.10 if mom >= 3 else (-0.15 if mom <= -3 else 0.0)
        cp = self._conversation_pressure(cid)
        qp = self._unanswered_question_pressure(cid)
        rp = self._relevance_pressure_slack(uid, cid)
        sp = self._silence_pressure(cid)
        pressure = cp + qp + rp + sp
        if _is_question(content): pressure += 0.38
        pressure += mom_bias
        pressure += self._social_bias.get(uid, 0.0) * 0.10
        prof = self._channel_profile[cid]
        chaos = _clamp(prof.get("chaos", 0.45), 0.0, 1.0)
        emoji_tol = _clamp(prof.get("emoji_tolerance", 0.55), 0.0, 1.0)
        formality = _clamp(prof.get("formality", 0.45), 0.0, 1.0)
        st = self._channel_state[cid]
        if st == STATE_LEADING: pressure += 0.07
        elif st == STATE_ENGAGED: pressure += 0.04
        elif st == STATE_WITHDRAWING: pressure -= 0.14
        pressure += chaos * 0.08 + emoji_tol * 0.03 - formality * 0.10
        pressure += self._interject_success_bias(cid)
        pressure -= self._fatigue_penalty() + _circadian_penalty() + self._last_channel_embarrassment[cid] * 0.62
        if self._current_mood == "tired": pressure *= 0.62
        elif self._current_mood == "silly": pressure *= 1.22
        elif self._current_mood == "focused": pressure *= 0.90
        conf = self._confidence_decay(cid)
        bold = self._channel_boldness(workspace_id, cid)
        p = BASE_INTERRUPT_PROB + pressure * conf
        p *= (0.88 + 0.30 * bold)
        risk = self._social_risk(cid)
        if risk > 0.72: p *= 0.55
        elif risk > 0.55: p *= 0.78
        return _clamp(p, 0.0, MAX_INTERRUPT_PROB)

    async def maybe_react_slack(self, uid: str, channel_id: str, workspace_id: str, content: str, ts: str, mentioned: bool, client) -> Optional[Dict[str, Any]]:
        if content and content[0] in IGNORE_PREFIXES:
            return None
        if self._cooldown_hard(channel_id, uid):
            return None
        if not content or _low_effort(content):
            return None
        self._maybe_shift_mood()
        self._update_channel_state(channel_id)
        p = self.p_react_slack(uid, channel_id, workspace_id, content, mentioned)
        if self._rng.random() > p:
            bucket = self._pick_bucket(content.lower(), content)
            topic = self._extract_topic(content)
            if topic and bucket in ("agree","disbelief","sad","hype"):
                delta = {"agree":+0.15,"hype":+0.20,"disbelief":-0.20,"sad":-0.10}.get(bucket, 0.0)
                key = (channel_id, topic)
                old, _ = self._topic_memory.get(key, (0.0, 0.0))
                self._topic_memory[key] = (_clamp(old + delta, -1.0, 1.0), _now())
            return None

        bucket = self._pick_bucket(content.lower(), content)
        emoji = self._choose_emoji(channel_id, uid, bucket, workspace_id)
        prof = self._channel_profile[channel_id]
        formality = _clamp(prof.get("formality", 0.45), 0.0, 1.0)
        if formality > 0.68 and bucket in ("funny","hype","disbelief") and self._rng.random() < 0.55:
            bucket = "ack"
            emoji = self._choose_emoji(channel_id, uid, bucket, workspace_id)

        try:
            await client.reactions_add(channel=channel_id, timestamp=ts, name=emoji)
            stance = STANCE_BUCKETS.get(bucket)
            if stance:
                self._stance_memory[(uid, channel_id)] = (stance, _now())
            self._mark_react(channel_id, uid, emoji, workspace_id)
            self.remember_user_engagement(uid, channel_id, content)
            self._pending_react_back[(uid, ts)] = (_now(), emoji, channel_id)
        except Exception:
            pass
        return None

    def mark_interjected(self, channel_id: str, success_hint: Optional[bool] = None) -> None:
        t = _now()
        self._last_speak_time[channel_id] = t
        self._decay_embarrassment(channel_id)
        conf = self._confidence_decay(channel_id)
        prof = self._channel_profile[channel_id]
        chaos = _clamp(prof.get("chaos", 0.45), 0.0, 1.0)
        formality = _clamp(prof.get("formality", 0.45), 0.0, 1.0)
        boost = self._rng.uniform(0.04, 0.10)
        if success_hint is True: boost += 0.05
        elif success_hint is False: boost -= 0.03
        boost *= (0.95 + 0.18 * chaos) * (1.02 - 0.18 * formality)
        self._last_speak_confidence[channel_id] = _clamp(conf + boost, 0.22, 0.88)
        emb_add = self._rng.uniform(0.06, 0.16)
        if success_hint is False: emb_add += 0.10
        if success_hint is True: emb_add -= 0.03
        self._last_channel_embarrassment[channel_id] = _clamp(
            self._last_channel_embarrassment[channel_id] + emb_add, 0.0, 1.2
        )
        self._update_channel_state(channel_id)

    def self_reflect(self) -> None:
        t = _now()
        if t - self._last_reflect < SELF_REFLECT_EVERY:
            return
        self._last_reflect = t
        avg_fat = self._fatigue_penalty()
        mood = self._current_mood
        for uid in list(self._social_bias.keys()):
            self._social_bias[uid] *= 0.97
            if abs(self._social_bias[uid]) < 0.02:
                del self._social_bias[uid]
        if avg_fat > 0.26 and mood != "tired" and self._rng.random() < 0.42:
            self._current_mood = "tired"
        if avg_fat < 0.12 and mood == "tired" and self._rng.random() < 0.35:
            self._current_mood = self._rng.choice(["neutral","warm","focused"])
        for cid, dq in list(self._interject_outcomes_channel.items()):
            recent = list(dq)[-60:]
            if len(recent) < 10: continue
            rate = sum(v for _, v in recent) / len(recent)
            prof = self._channel_profile[cid]
            b = prof.get("boldness", 1.0)
            if rate > 0.58: b = _clamp(b + 0.04, MIN_CHANNEL_BOLDNESS, MAX_CHANNEL_BOLDNESS)
            elif rate < 0.38: b = _clamp(b - 0.05, MIN_CHANNEL_BOLDNESS, MAX_CHANNEL_BOLDNESS)
            prof["boldness"] = b


class InterjectTemplates:
    def __init__(self):
        self.neutral = ["yeah that makes sense","honestly fair","i was thinking the same","that tracks","lowkey agree","true though","not wrong","valid point","i see what you mean"]
        self.question = ["wait why though","how did that happen","what made you think that","can you explain that a bit","what do you mean exactly","wait how","what's the context","how so"]
        self.funny = ["nahhh 💀","bro 😭","this is wild","i'm crying","no way 😭","why is this funny","that's insane","this took me out"]
        self.hype = ["nah that's huge","that's fire","W","big W","let him cook","that's clean","goes hard","built different"]
        self.sad = ["damn that sucks","sorry you're dealing with that","that's rough","hope it gets better","that's a lot","i feel that","sending good vibes"]
        self.disbelief = ["no shot","ain't no way","cap","that can't be real","you're kidding","nahhhh","that's crazy if true"]

    def pick(self, bucket: str, rng: random.Random) -> str:
        pool = getattr(self, bucket, None) or self.neutral
        return rng.choice(pool)


class SignalStack:
    def __init__(self):
        self.neg_words = {"bad","worse","worst","sad","tired","exhausted","upset","angry","mad","depressed","lonely","anxious","stressed","overwhelmed","miserable"}
        self.pos_words = {"good","great","awesome","nice","amazing","love","happy","excited","fire","clean","perfect","goat","elite","solid"}

    def score(self, text: str) -> Dict[str, float]:
        t = text.lower()
        w = _words(t)
        s: Dict[str, float] = defaultdict(float)
        s["length"] = min(len(text) / 220.0, 1.0)
        s["questions"] = t.count("?")
        s["exclaim"] = t.count("!")
        s["emoji"] = sum(1 for c in text if ord(c) > 10000)
        s["laugh"] = sum(1 for k in ("lol","lmao","😂","😭","💀","🤣") if k in t)
        s["neg"] = sum(1 for x in w if x in self.neg_words)
        s["pos"] = sum(1 for x in w if x in self.pos_words)
        s["caps"] = 1.0 if len(text) > 6 and text.isupper() else 0.0
        s["confused"] = 1.0 if _has_any(t, CONFUSED_KEYS) else 0.0
        s["vent"] = 1.0 if _has_any(t, VENT_KEYS) else 0.0
        s["tease"] = 1.0 if _has_any(t, TEASE_KEYS) else 0.0
        s["invite"] = 1.0 if _has_any(t, INVITE_KEYS) else 0.0
        s["story"] = 1.0 if _has_any(t, STORY_KEYS) else 0.0
        return s

    def bucket(self, text: str) -> str:
        s = self.score(text)
        if s["confused"] > 0: return "confused"
        if s["questions"] > 0 and s["invite"] > 0: return "invite"
        if s["questions"] > 0: return "question"
        if s["vent"] > 0: return "vent"
        if s["neg"] > 0 and s["pos"] == 0: return "sad"
        if s["laugh"] > 0: return "funny"
        if s["tease"] > 0: return "tease"
        if s["story"] > 0: return "story"
        if s["pos"] > 0 and s["exclaim"] > 0: return "hype"
        if s["caps"] > 0: return "disbelief"
        return "neutral"


class InterjectionEngine:
    def __init__(self, brain: HumanBrain):
        self.brain = brain
        self.templates = InterjectTemplates()
        self.signals = SignalStack()
        self.confused = ["wait what","huh","hold on 😭","wdym","i'm lost already","wait explain"]
        self.vent = ["nah that's rough","yeah i'd be annoyed too","that would irritate me too","okay yeah that sucks","rough one fr"]
        self.tease = ["bro 😭","you're cooked","nahhh","crazy work","be serious"]
        self.invite = ["ok wait let me see","hold on","lowkey i see it","wait i get what you mean","alright fair"]
        self.story = ["ok keep going","wait no finish this","im listening","nah continue","where is this going"]

    def _shape_line(self, text: str, bucket: str) -> str:
        t = (text or "").strip()
        if not t: return t
        if len(t) > 90:
            t = t[:90].rsplit(" ", 1)[0].strip()
        if self.brain._rng.random() < 0.35:
            t = t.rstrip(".!?")
        if self.brain._rng.random() < 0.70:
            t = t[:1].lower() + t[1:] if t else t
        if bucket in {"funny","confused","tease"} and self.brain._rng.random() < 0.22:
            parts = t.split()
            if len(parts) >= 2:
                t = " ".join(parts[:2])
        return t

    async def maybe_interject_slack(self, uid: str, channel_id: str, workspace_id: str, content: str, say) -> Optional[str]:
        if self.brain.is_roast_mode(uid):
            return None
        if len(content) <= 1:
            return None
        if _now() - self.brain._last_speak_time.get(channel_id, 0) < 6.0:
            return None
        p = self.brain.should_interject_probability_slack(uid, channel_id, workspace_id, content)
        roll = self.brain._rng.random()
        hlog("INTERJECT check", "p=", round(p,3), "roll=", round(roll,3))
        if roll > p:
            return None
        bucket = self.signals.bucket(content)
        user_mem = self.brain.get_contextual_memory(uid, channel_id, bucket, limit=8)
        channel_mem = self.brain.get_recent_channel_lines(channel_id, limit=4)
        mem_lines = user_mem + [x for x in channel_mem if x not in user_mem]
        text = await ai_interject_line(bucket, content, mem_lines)
        recent_lines = self.brain.get_recent_channel_lines(channel_id, limit=5)
        if len(recent_lines) >= 4:
            if sum(1 for x in recent_lines if len(x) > 20) >= 4 and self.brain._rng.random() < 0.28:
                return None
        if not text:
            text = self.templates.pick(bucket, self.brain._rng)
        text = self._shape_line(text, bucket)
        await self.brain.human_delay_slack(text)
        try:
            self.brain.mark_busy(channel_id)
            await say(text)
            self.brain.observe_channel_message(channel_id, text)
            self.brain.mark_interjected(channel_id, success_hint=None)
            return text
        except Exception:
            self.brain.mark_interjected(channel_id, success_hint=False)
            return None


class OutcomeTracker:
    def __init__(self, brain: HumanBrain):
        self.brain = brain
        self._pending_interjects: Dict[str, float] = {}

    def process_timeouts(self):
        now = _now()
        expired = [cid for cid, ts in self._pending_interjects.items() if now - ts > 30.0]
        for cid in expired:
            self.brain.observe_interject_outcome(cid, False)
            del self._pending_interjects[cid]

    def note_interject(self, channel_id: str):
        self._pending_interjects[channel_id] = _now()

    def observe_message_slack(self, uid: str, channel_id: str):
        if channel_id not in self._pending_interjects:
            return
        age = _now() - self._pending_interjects[channel_id]
        if age < 1.0:
            return
        self.brain.observe_interject_outcome(channel_id, True)
        del self._pending_interjects[channel_id]


class BrainRuntime:
    def __init__(
        self,
        client,
        chat_fn: Callable,
        roast_fn: Callable,
        get_roast_mode: Callable,
        persist_path: str = "human_brain_state.json",
        is_roast_mode=None,
    ):
        self.client = client
        self.chat_fn = chat_fn
        self.roast_fn = roast_fn
        self.get_roast_mode = get_roast_mode
        self.brain = HumanBrain(persist_path=persist_path, is_roast_mode=is_roast_mode)
        self.interjector = InterjectionEngine(self.brain)
        self.outcomes = OutcomeTracker(self.brain)
        self._task_started = False
        self._running = True

    async def on_message_slack(self, uid: str, channel_id: str, team_id: str, text: str, ts: str, bot_user_id: str, say) -> Optional[str]:
        content = (text or "").strip()
        if not content:
            return None

        mentioned = mentions_fusbot(content) or (bot_user_id and f"<@{bot_user_id}>" in content)

        if content and not content[0] in IGNORE_PREFIXES:
            self.brain.observe_channel_message(channel_id, content, ts)

        await self.brain.maybe_react_slack(uid, channel_id, team_id, content, ts, mentioned, self.client)

        if mentioned:
            intent = _mention_intent(content)
            mode = self.get_roast_mode(uid)

            if intent == "social_ping":
                if self.brain._rng.random() < 0.25:
                    reply = random.choice(["yo", "sup", "what's up", "yeah?", "hm?"])
                    await self.brain.human_delay_slack(reply)
                    self.brain.mark_busy(channel_id)
                    await say(reply)
                    return reply
                return None

            if intent == "roast_request" and mode:
                reply = await self.roast_fn(content, uid, mode)
            else:
                reply = await self.chat_fn(content, uid, channel_id, team_id)

            if reply:
                await self.brain.human_delay_slack(reply)
                self.brain.mark_busy(channel_id)
                await say(reply)
            return reply

        reply = await self.interjector.maybe_interject_slack(uid, channel_id, team_id, content, say)
        if reply is not None:
            self.outcomes.note_interject(channel_id)
        self.outcomes.observe_message_slack(uid, channel_id)
        self.brain.self_reflect()
        self.brain.maybe_persist()
        return reply

    async def background_loop(self):
        while self._running:
            try:
                if int(_now()) % 15 == 0:
                    self.brain._decay_emoji_boredom()
                self.outcomes.process_timeouts()
                self.brain.self_reflect()
                self.brain.maybe_persist()
            except Exception:
                pass
            await asyncio.sleep(1.2)

    def start(self):
        if self._task_started:
            return
        self._task_started = True
        asyncio.ensure_future(self.background_loop())
