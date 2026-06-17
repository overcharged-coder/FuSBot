from dotenv import load_dotenv
load_dotenv()

import os
import asyncio
import re
import time
import json
import datetime
from collections import defaultdict, deque

from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_sdk.web.async_client import AsyncWebClient

from openai import OpenAI
from groq import Groq
import google.generativeai as genai

from human_brain import BrainRuntime
from mentions import mentions_fusbot
from economy_shared import load_state
load_state()
from economy_shared import state, save_state
from economy import get_user
from slack_utils import parse_slack_mentions, strip_slack_mentions, slack_mention, unicode_to_slack_emoji

CHAT_HISTORY = defaultdict(lambda: deque(maxlen=10))
ACTIVE_CONVO = {}
LAST_BOT_MESSAGE = {}

def session_key(channel_id: str, user_id: str):
    return (channel_id, user_id)

MIN_DEEP_SPICE = 25

AUTO_ROAST_BOT_IDS: set[str] = set()

FOLLOWUP_SYSTEM_PROMPT = """You are a conversation intent classifier.

You will be given:
- the bot's last message
- the user's new message

Decide if the user's message is intended as a reply to the bot.

Answer ONLY one word:
YES or NO

YES if it feels like a reaction, agreement, continuation, clarification,
or response to what the bot just said — even if vague, slangy, or short.

NO if it feels unrelated or directed elsewhere.

Be human.
"""

MEMORY_FILE = "roast_memory.json"

def load_roast_memory():
    if not os.path.exists(MEMORY_FILE):
        return {"user_memory": {}, "roast_history": {}, "auto_roast": {}, "roast_mode": {}, "spice_cache": {}}
    try:
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"user_memory": {}, "roast_history": {}, "auto_roast": {}, "roast_mode": {}, "spice_cache": {}}

def save_roast_memory():
    mem = {
        "user_memory": user_memory,
        "roast_history": roast_history,
        "auto_roast": auto_roast,
        "roast_mode": roast_mode,
        "spice_cache": spice_cache
    }
    with open(MEMORY_FILE, "w") as f:
        json.dump(mem, f, indent=2)

def log(*msg):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    text = " ".join(str(x) for x in msg)
    if "<html" not in text and "<!DOCTYPE" not in text:
        print(f"[{timestamp}] {text}")

# ── LLM clients ───────────────────────────────────────────────────────────────

REAL_OPENAI_KEY = os.getenv("OPENAI_API_KEY")
openai_client = OpenAI(api_key=REAL_OPENAI_KEY) if REAL_OPENAI_KEY else None

GITHUB_API_KEY = os.getenv("GITHUB_TOKEN") or os.getenv("GITHUB_API_KEY") or os.getenv("GITHUB") or ""
github_client = (
    OpenAI(
        api_key=GITHUB_API_KEY,
        base_url="https://models.inference.ai.azure.com",
        default_headers={
            "Authorization": f"Bearer {GITHUB_API_KEY}",
            "X-Github-Api-Version": "2022-11-28",
            "Accept": "application/vnd.github+json",
        },
    )
    if GITHUB_API_KEY else None
)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

GROQ_API_KEY = os.getenv("GROQ")
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")
openrouter_client = (
    OpenAI(
        api_key=OPENROUTER_KEY,
        base_url="https://openrouter.ai/api/v1",
        default_headers={"HTTP-Referer": "https://example.com", "X-Title": "Slack Roast Bot"},
    )
    if OPENROUTER_KEY else None
)

GROQ_MODELS = ["groq:qwen/qwen3-32b", "groq:llama-3.3-70b-versatile", "groq:llama-3.1-8b-instant"]
GITHUB_MODELS = ["gpt-4o-mini", "phi-4-mini-instruct"]
GEMINI_MODELS = ["gemini-2.5-flash-lite", "gemini-2.0-flash-lite", "gemini-2.5-pro", "gemini-2.5-flash"]
OPENAI_MODELS = []
OPENROUTER_MODELS = []
NORMAL_CHAT_MODELS = [
    "groq:llama-3.1-8b-instant", "gemini-2.0-flash", "gemini-2.0-pro",
    "github:gpt-4o-mini", "openai:gpt-4o-mini", "openai:gpt-4o"
]
FOLLOWUP_MODELS = ["github:gpt-4o-mini", "microsoft/phi-3-mini-128k-instruct", "gemini-2.0-flash", "groq:llama-3.1-8b-instant"]

class Roast500Error(Exception):
    pass

def strip_reasoning(text):
    if not text:
        return ""
    for tag in ["think", "thinking", "internal", "reasoning"]:
        text = re.sub(rf"<{tag}>.*?</{tag}>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"^(Thought|Thinking|Reasoning|Internal):.*$", "", text, flags=re.IGNORECASE | re.MULTILINE)
    return text.strip()

def extract_text(model_name, resp):
    try:
        c = resp.choices[0]
        if hasattr(c, "message") and hasattr(c.message, "content") and c.message.content:
            return c.message.content
        if hasattr(c, "text") and c.text:
            return c.text
    except Exception:
        pass
    if hasattr(resp, "text") and resp.text:
        return resp.text
    if isinstance(resp, str):
        return resp
    return ""

def wrap_text(text):
    class Msg: content = text
    class Ch: message = Msg()
    class Resp: choices = [Ch()]
    return Resp()

async def safe_completion(model, messages):
    loop = asyncio.get_event_loop()

    async def run(fn):
        try:
            return await asyncio.wait_for(loop.run_in_executor(None, fn), timeout=12)
        except Exception as e:
            log(f"[TIMEOUT/ERROR:{model}] {e}")
            return None

    if model.startswith("groq:"):
        if not groq_client: return None
        actual = model.split("groq:", 1)[1]
        def call():
            try:
                r = groq_client.chat.completions.create(model=actual, messages=messages, max_tokens=250, temperature=1.0)
                return wrap_text(strip_reasoning(extract_text(model, r)))
            except Exception as e:
                log(f"[GROQ FAIL:{actual}] {e}")
                return None
        return await run(call)

    if model.startswith("gemini"):
        def call():
            try:
                sys_text = "\n\n".join(m["content"] for m in messages if m["role"] == "system").strip()
                usr_text = "\n\n".join(m["content"] for m in messages if m["role"] == "user").strip()
                client = genai.GenerativeModel(model, system_instruction=sys_text or None)
                r = client.generate_content(usr_text)
                text = r.text if hasattr(r, "text") and r.text else ""
                if not text and hasattr(r, "candidates"):
                    try: text = r.candidates[0].content.parts[0].text
                    except Exception: pass
                return wrap_text(strip_reasoning(text))
            except Exception as e:
                log(f"[GEMINI FAIL:{model}] {e}")
                return None
        return await run(call)

    if model.startswith("github:"):
        if not github_client:
            return None
        actual = model.split("github:", 1)[1]
        def call():
            try:
                r = github_client.chat.completions.create(model=actual, messages=messages, max_tokens=250, temperature=1.1)
                return wrap_text(strip_reasoning(extract_text(model, r)))
            except Exception as e:
                log(f"[GITHUB FAIL:{actual}] {e}")
                return None
        return await run(call)

    if model.startswith("openai:"):
        if not openai_client:
            return None
        actual = model.split("openai:", 1)[1]
        def call():
            try:
                r = openai_client.chat.completions.create(model=actual, messages=messages, max_tokens=250, temperature=1.0)
                return wrap_text(strip_reasoning(extract_text(model, r)))
            except Exception as e:
                log(f"[OPENAI FAIL:{actual}] {e}")
                return None
        return await run(call)

    if not openrouter_client: return None
    def call_or():
        try:
            r = openrouter_client.chat.completions.create(model=model, messages=messages, max_tokens=250, temperature=1.2)
            return wrap_text(strip_reasoning(extract_text(model, r)))
        except Exception as e:
            log(f"[OR FAIL:{model}] {e}")
            return None
    return await run(call_or)

# ── Spice / roast quality ──────────────────────────────────────────────────────

INSULT_KEYWORDS = [
    "idiot", "stupid", "dumb", "clown", "trash", "garbage", "loser", "beta",
    "cringe", "moron", "fool", "disgrace", "pathetic", "nerd", "goofy", "bottom",
    "npc", "bozo", "braindead", "clueless", "child", "kid", "mid", "washed",
    "ugly", "rat", "worm", "gremlin", "die", "kill", "fat",
]

def calculate_spiciness(text: str) -> float:
    if not text:
        return 0.0
    t = text.lower()
    score = sum(8.0 for w in INSULT_KEYWORDS if w in t)
    if "mom" in t or "mother" in t or "family" in t:
        score += 12
    if "life" in t or "exist" in t:
        score += 10
    score += min(t.count("!"), 5) * 3
    caps_ratio = sum(1 for c in text if c.isupper()) / len(text) if text else 0
    score += caps_ratio * 25
    L = len(t)
    if L < 10:
        score -= 10
    elif 20 < L < 120:
        score += 8
    return float(max(0, min(score, 100)))

NON_ROAST_PATTERNS = [
    "that's a pretty", "that's a classic", "it uses exaggeration",
    "i don't have a physical body", "i'm sorry", "roast generation failed", "as an ai",
]

def looks_like_real_roast(text: str) -> bool:
    if not text or len(text.strip()) < 8:
        return False
    t = text.strip().lower()
    if any(p in t for p in NON_ROAST_PATTERNS):
        return False
    if any(p in t for p in ["this insult", "it relies on", "the joke", "the roast"]):
        return False
    roast_markers = ["you ", "ur ", "u ", "your ", "look like", "built like", "sound like", "got the", "built "]
    return any(p in t for p in roast_markers) or calculate_spiciness(text) >= 15

async def spice_groq(text: str):
    messages = [
        {"role": "system", "content": "You are a roast-quality analyzer. Score 0-100. Output only a number. 0 if no actual insult."},
        {"role": "user", "content": text}
    ]
    if not groq_client: return None
    try:
        loop = asyncio.get_event_loop()
        resp = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: groq_client.chat.completions.create(
                model="llama-3.1-8b-instant", messages=messages, max_tokens=5, temperature=0.0
            )), timeout=4
        )
        raw = resp.choices[0].message.content.strip()
        m = re.search(r"\d{1,3}", raw)
        if m:
            return float(m.group())
    except Exception:
        pass
    return None

async def fast_spice(text: str) -> float:
    if text in spice_cache:
        return float(spice_cache[text])
    ai_score = await spice_groq(text) or 0.0
    score = max(ai_score, calculate_spiciness(text))
    spice_cache[text] = score
    save_roast_memory()
    return score

# ── API roast gathering ────────────────────────────────────────────────────────

import aiohttp

async def fetch_url(session, url, json_key=None, is_text=False):
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=4)) as r:
            if r.status >= 500:
                raise Roast500Error()
            if is_text:
                text = await r.text()
                if "<html" in text or "Internal Server Error" in text:
                    raise Roast500Error()
                return text
            j = await r.json()
            return j.get(json_key)
    except Roast500Error:
        raise
    except Exception:
        return None

async def get_openrouter_quick_roast(prompt):
    if not openrouter_client: return None
    messages = [{"role": "system", "content": ROAST_SYSTEM_PROMPT}, {"role": "user", "content": prompt}]
    try:
        resp = await asyncio.get_event_loop().run_in_executor(None, lambda: openrouter_client.chat.completions.create(
            model="meta-llama/llama-3.1-405b-instruct", messages=messages, max_tokens=60, temperature=1.25,
        ))
        return strip_reasoning(extract_text("OR:quick", resp))
    except Exception:
        return None

async def fetch_vortex_roasts(session, content: str):
    try:
        async with session.post("https://ai4free-vortex-3b-roast-api.hf.space/generate-roasts/",
                                json={"content": content}, timeout=aiohttp.ClientTimeout(total=8)) as r:
            if r.status >= 500:
                raise Roast500Error()
            data = await r.json()
            roasts = data.get("roasts")
            if isinstance(roasts, list):
                return [x.strip() for x in roasts if isinstance(x, str) and len(x.strip()) > 3]
    except Roast500Error:
        raise
    except Exception:
        pass
    return None

async def gather_api_roasts(prompt):
    try:
        async with aiohttp.ClientSession() as session:
            tasks = [
                fetch_url(session, "https://evilinsult.com/generate_insult.php?lang=en&type=json", "insult"),
                fetch_url(session, "https://insult.mattbas.org/api/insult", is_text=True),
                fetch_url(session, "https://yoinsult.com/api/insult", "insult"),
                fetch_url(session, "https://v2.jokeapi.dev/joke/Dark?type=single", "joke"),
                get_openrouter_quick_roast(prompt),
                fetch_vortex_roasts(session, prompt),
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
        candidates = []
        for r in results:
            if isinstance(r, Roast500Error):
                continue
            if isinstance(r, str) and len(r) > 3:
                candidates.append({"source": "API", "text": r.strip()})
            elif isinstance(r, list):
                for txt in r:
                    if isinstance(txt, str) and len(txt.strip()) > 3:
                        candidates.append({"source": "API_VORTEX", "text": txt.strip()})
        return candidates
    except Exception as e:
        log(f"[APIs] Error: {e}")
        return []

async def gather_all_llm_roasts(prompt, user_id):
    context = [
        {"role": "system", "content": ROAST_SYSTEM_PROMPT},
        {"role": "system", "content": build_memory_prompt(user_id)},
        {"role": "user", "content": prompt},
    ]
    tasks = []
    sources = []
    for m in GEMINI_MODELS:
        tasks.append(safe_completion(m, context)); sources.append(f"GM:{m}")
    for m in GROQ_MODELS:
        tasks.append(safe_completion(m, context)); sources.append(f"GROQ:{m.split(':', 1)[1]}")
    for m in GITHUB_MODELS:
        tasks.append(safe_completion("github:" + m, context)); sources.append(f"GITHUB:{m}")
    results = await asyncio.gather(*tasks, return_exceptions=True)
    candidates = []
    for src, resp in zip(sources, results):
        if isinstance(resp, Exception) or resp is None:
            continue
        try:
            raw = extract_text(src, resp)
            txt = strip_reasoning(raw).strip()
        except Exception:
            continue
        if not txt or len(txt) < 5:
            continue
        if not looks_like_real_roast(txt):
            continue
        candidates.append({"source": src, "text": txt})
    return candidates

def enforce_short_roast(text: str) -> str:
    sentences = re.split(r'(?<=[.!?]) +', text)
    return " ".join(sentences[:3]).strip()[:1500]

async def bot_roast(msg, uid, mode):
    try:
        user_spice = compute_user_spice(uid)
        if mode == "fast":
            candidates = await gather_api_roasts(msg)
            candidates = [c for c in candidates if isinstance(c.get("text"), str) and len(c["text"]) > 4 and c["text"][0].isalpha()]
            if not candidates:
                return "My roast APIs are offline. Try /roastmode deep."
            seen = set()
            unique = [c for c in candidates if c["text"] not in seen and not seen.add(c["text"])]
            spices = await asyncio.gather(*(fast_spice(c["text"]) for c in unique))
            return unique[max(range(len(unique)), key=lambda i: spices[i])]["text"]

        elif mode == "deep":
            llm_cands = await gather_all_llm_roasts(msg, uid)
            if not llm_cands:
                return "All LLMs failed. My circuits are fried."
            penalized = []
            for c in llm_cands:
                s_len = len(re.findall(r'[.!?]', c["text"]))
                penalized.append(0.0 if s_len > 3 else await fast_spice(c["text"]))
            best_idx = max(range(len(llm_cands)), key=lambda i: penalized[i])
            if penalized[best_idx] < MIN_DEEP_SPICE:
                return "ur roast had more setup than impact. even the ai couldn't make that hit."
            return enforce_short_roast(llm_cands[best_idx]["text"])

        elif mode == "adjustable":
            api_cands = await gather_api_roasts(msg)
            llm_cands = await gather_all_llm_roasts(msg, uid)
            candidates = [c for c in api_cands if len(c["text"]) > 4 and c["text"][0].isalpha()] + llm_cands
            if not candidates:
                return "I got nothing bro. Every AI froze."
            spices = await asyncio.gather(*(fast_spice(c["text"]) for c in candidates))
            scored = sorted(zip(spices, candidates), key=lambda x: abs(x[0] - user_spice))
            return enforce_short_roast(scored[0][1]["text"])

        return "Pick a roast mode with /roastmode fast, deep, or adjustable."
    except Roast500Error:
        return "Your roast was so powerful it caused a server error."
    except Exception as e:
        log(f"[ERROR] bot_roast: {e}")
        return "My brain just lagged mid-roast. Try again."

# ── Chat ───────────────────────────────────────────────────────────────────────

async def bot_chat(msg: str, uid: str, channel_id: str, workspace_id: str = None):
    hist_key = session_key(channel_id, uid)
    mem_lines = brain_runtime.brain.get_user_engagement_memory(uid, limit=15)
    structured_hint = build_chat_personalization_prompt(uid)
    channel_hint = brain_runtime.brain.get_channel_memory_hint(channel_id)

    memory_hint = ""
    if mem_lines:
        memory_hint = (
            "this user recently said things like:\n" + "\n".join(mem_lines) + "\n"
            "use this only to match tone and familiarity. do not reference these directly.\n"
        )

    messages = [
        {
            "role": "system",
            "content": (
                "your name is fusbot\n"
                "you are a real slack user chatting naturally\n"
                "do not mention you are a bot casually\n"
                "write one short casual response\n"
                "1 to 3 sentences max\n"
                "no capitalization unless displaying excitement\n"
                "no emojis unless they fit naturally\n"
                "no explanations\n"
                "never sound formal\n"
                "use slang too\n"
                "output only the message\n"
                f"\n{structured_hint}\n{channel_hint}\n{memory_hint}"
            ),
        },
        *CHAT_HISTORY[hist_key],
        {"role": "user", "content": msg},
    ]

    for model in NORMAL_CHAT_MODELS:
        try:
            resp = await safe_completion(model, messages)
            if resp:
                raw = extract_text(model, resp)
                text = strip_reasoning(raw)
                if text and len(text.strip()) > 1:
                    CHAT_HISTORY[hist_key].append({"role": "user", "content": msg})
                    CHAT_HISTORY[hist_key].append({"role": "assistant", "content": text})
                    return text
        except Exception as e:
            log(f"[CHAT] {model} failed: {e}")

    return "my brain lagged a bit, say that again"

# ── Follow-up detection ───────────────────────────────────────────────────────

def _normalize_yesno(text: str) -> str:
    t = (text or "").strip().upper()
    if t.startswith("YES"):
        return "YES"
    if t.startswith("NO"):
        return "NO"
    return ""

async def followup_completion(model: str, last_bot_msg: str, user_msg: str):
    messages = [
        {"role": "system", "content": FOLLOWUP_SYSTEM_PROMPT.strip()},
        {"role": "user", "content": f"BOT SAID:\n{last_bot_msg}\n\nUSER SAID:\n{user_msg}"},
    ]
    if model.startswith("gemini"):
        messages = [{"role": "user", "content": FOLLOWUP_SYSTEM_PROMPT.strip() + f"\n\nBOT SAID:\n{last_bot_msg}\n\nUSER SAID:\n{user_msg}\n\nanswer only YES or NO"}]
    resp = await safe_completion(model, messages)
    return extract_text(f"FOLLOWUP:{model}", resp) or "" if resp else ""

async def ai_is_followup(last_bot_msg: str, user_msg: str) -> bool:
    for model in FOLLOWUP_MODELS:
        try:
            raw = await followup_completion(model, last_bot_msg, user_msg)
            ans = _normalize_yesno(raw)
            if ans == "YES":
                return True
            if ans == "NO":
                return False
        except Exception:
            continue
    return False

def obvious_followup(text: str, convo: dict) -> bool:
    t = text.strip().lower()
    if t in {"wdym", "what", "huh", "why", "how", "explain", "elaborate", "?", "??"}:
        return True
    if convo and (time.time() - convo["last_ts"] <= 45):
        if len(t) <= 60 and not t.startswith(("!", "/")):
            return True
    return False

# ── User memory ───────────────────────────────────────────────────────────────

def normalize_id_keys(d):
    return {k: v for k, v in (d or {}).items()}

_memory = load_roast_memory()
user_memory = normalize_id_keys(_memory["user_memory"])
roast_history = normalize_id_keys(_memory["roast_history"])
auto_roast = normalize_id_keys(_memory["auto_roast"])
roast_mode = normalize_id_keys(_memory["roast_mode"])
spice_cache = _memory["spice_cache"]

def default_user_profile():
    return {"display_names": [], "pronouns": "", "timezone": "", "languages": [], "interests": [],
            "favorite_topics": [], "disliked_topics": [], "expertise": [], "projects": [],
            "devices_tools": [], "inside_jokes": [], "sensitive_topics": [], "important_facts": []}

def default_user_prefs():
    return {"preferred_tone": "", "preferred_length": "", "likes_code_examples": 0.0,
            "likes_direct_answers": 0.0, "likes_step_by_step": 0.0,
            "likes_brainstorming": 0.0, "joke_tolerance": 0.5, "roast_tolerance": 0.5}

def default_user_context():
    return {"active_topics": [], "topic_counts": {}, "open_loops": [],
            "recent_questions": [], "recent_messages": [], "last_seen": 0, "last_channel_id": ""}

def get_user_memory(uid: str):
    if uid not in user_memory:
        user_memory[uid] = {
            "LF": {"slang": 0.0, "formality": 0.0, "emoji_rate": 0.0, "all_caps_rate": 0.0,
                   "punct_energy": 0.0, "avg_len": 0.0, "msg_samples": []},
            "EB": {"anger": 0.0, "sadness": 0.0, "hype": 0.0, "chaos": 0.0},
            "HP": {"dark": 0.0, "mean": 0.0, "petty": 0.0, "simple": 0.0, "goofy": 0.0, "meta": 0.0},
            "IS": {"bot_mentions": 0, "roast_requests": 0, "self_roasts": 0, "escalation": 0.0},
            "SPM": {"embeddings": [], "texts": []},
            "LTS": "", "msg_count": 0, "last_summary_update": time.time(),
            "profile": default_user_profile(), "prefs": default_user_prefs(),
            "context": default_user_context(), "episodes": [],
        }
        save_roast_memory()
    mem = user_memory[uid]
    mem.setdefault("profile", default_user_profile())
    mem.setdefault("prefs", default_user_prefs())
    mem.setdefault("context", default_user_context())
    mem.setdefault("episodes", [])
    return mem

def compute_user_spice(uid: str) -> float:
    mem = get_user_memory(uid)
    hp = mem["HP"]
    hp_score = hp["dark"]*1.8 + hp["mean"]*1.5 + hp["petty"]*1.2 + hp["simple"]*0.5 + hp["goofy"]*0.3 + hp["meta"]*0.4
    eb = mem["EB"]
    eb_score = eb["anger"]*1.2 + eb["hype"]*0.8 + eb["chaos"]*0.6
    isec = mem["IS"]
    is_score = isec["roast_requests"]*0.7 + isec["escalation"]*2.0 + isec["self_roasts"]*1.0
    return float(min(100, max(0, hp_score + eb_score + is_score)))

def build_memory_prompt(uid: str):
    mem = get_user_memory(uid)
    return (
        "USER BEHAVIOR PROFILE:\n"
        f"- Long-term summary: {mem['LTS'] or 'User has a neutral personality.'}\n"
        f"- Humor Preferences: {mem['HP']}\n"
        f"- Emotional Baseline: {mem['EB']}\n"
        f"- Linguistic Style: {mem['LF']['slang']:.2f} slang, {mem['LF']['emoji_rate']:.2f} emoji use.\n"
        "\nUse all of this subtly to make the roast more personal. Do NOT mention traits directly."
    )

def build_chat_personalization_prompt(uid: str):
    mem = get_user_memory(uid)
    profile = mem["profile"]
    prefs = mem["prefs"]
    context = mem["context"]
    lines = []
    if mem.get("LTS"):
        lines.append(f"- summary: {mem['LTS']}")
    if profile["projects"]:
        lines.append(f"- active projects: {profile['projects'][:3]}")
    if context["active_topics"]:
        lines.append(f"- active topics: {context['active_topics'][:6]}")
    if prefs["preferred_length"]:
        lines.append(f"- preferred answer length: {prefs['preferred_length']}")
    return "user personalization hints:\n" + "\n".join(lines) + "\nuse subtly.\n" if lines else ""

def _push_recent(lst, item, limit):
    lst.append(item)
    if len(lst) > limit:
        del lst[:-limit]

def _push_unique_recent(lst, item, limit):
    item = (item or "").strip()
    if not item:
        return
    if item in lst:
        lst.remove(item)
    lst.append(item)
    if len(lst) > limit:
        del lst[:-limit]

def _bump_pref(d, key, amount=0.12):
    d[key] = round(min(1.0, max(0.0, d.get(key, 0.0) + amount)), 3)

def extract_keywords(text):
    words = re.findall(r"[a-zA-Z']{3,}", text.lower())
    return [w for w in words if w not in {"the", "and", "you", "but", "are", "this", "that"}]

def refresh_user_summary(uid: str):
    mem = get_user_memory(uid)
    profile = mem["profile"]
    prefs = mem["prefs"]
    context = mem["context"]
    parts = []
    if profile["projects"]:
        parts.append("often talks about " + ", ".join(profile["projects"][:3]))
    if profile["interests"]:
        parts.append("interested in " + ", ".join(profile["interests"][:4]))
    if context["active_topics"]:
        parts.append("recent topics: " + ", ".join(context["active_topics"][:5]))
    if prefs["preferred_length"]:
        parts.append(f"prefers {prefs['preferred_length']} answers")
    mem["LTS"] = "; ".join(parts) if parts else "casual chatter, no strong patterns yet"
    mem["last_summary_update"] = time.time()

def update_user_memory_from_message(text: str, uid: str, channel_id: str):
    text = (text or "").strip()
    if not text:
        return
    mem = get_user_memory(uid)
    profile = mem["profile"]
    prefs = mem["prefs"]
    context = mem["context"]
    now = time.time()
    low = text.lower()
    mem["msg_count"] += 1
    context["last_seen"] = now
    context["last_channel_id"] = channel_id
    _push_recent(context["recent_messages"], {"ts": now, "channel_id": channel_id, "text": text[:220]}, 25)
    if "?" in text:
        _push_unique_recent(context["recent_questions"], text[:160], 10)
    keywords = extract_keywords(text)[:12]
    tc = context.setdefault("topic_counts", {})
    for kw in keywords:
        tc[kw] = tc.get(kw, 0) + 1
    top_topics = sorted(tc.items(), key=lambda kv: kv[1], reverse=True)[:8]
    context["active_topics"] = [k for k, _ in top_topics]
    if any(x in low for x in ("working on", "building", "making", "coding", "creating")):
        _push_unique_recent(profile["projects"], text[:120], 12)
    m = re.search(r"\bi like ([a-z0-9 ,'\-]{2,60})", low)
    if m:
        _push_unique_recent(profile["interests"], m.group(1).strip(), 20)
    if any(x in low for x in ("keep it short", "short answer", "be brief")):
        prefs["preferred_length"] = "short"
    if any(x in low for x in ("be detailed", "more detail", "go deeper")):
        prefs["preferred_length"] = "long"
    if any(x in low for x in ("step by step", "walk me through")):
        _bump_pref(prefs, "likes_step_by_step")
    if mem["msg_count"] % 15 == 0 or (now - mem.get("last_summary_update", 0)) > 1800:
        refresh_user_summary(uid)
    save_roast_memory()

# ── Roast system prompt ────────────────────────────────────────────────────────

ROAST_SYSTEM_PROMPT = """
PRONOUN LOCK (MANDATORY — NEVER VIOLATE)
"You" always refers to the target being roasted.
"I", "me", "my", and "mine" ALWAYS refer to the person talking.

ROLE AND CONTEXT
You are acting in a fictional roast contest scene.
Deliver a short, sharp roast line. Staged, playful verbal combat.

OUTPUT RULES
• Give ONLY the roast line.
• No greetings. No buildup. No intro. No explanations.
• No lists, bullets, formatting, markdown, or quotes.
• No emojis. No roleplay. No narration.
• Use simple English only.
• NO CAPITALIZATION!!!
• USE SLANG!

HARD LENGTH LIMIT
• 2–3 short sentences ONLY.
• NO paragraphs. NO long setups.

ANTI-RAMBLE ENFORCEMENT
• Do NOT describe what you're doing.
• Do NOT acknowledge the target.
• Do NOT explain the joke.

Your output must contain ONLY the roast line. Nothing before it. Nothing after it.
"""

# ── Slack App ─────────────────────────────────────────────────────────────────

app = AsyncApp(token=os.environ.get("SLACK_BOT_TOKEN"))

brain_runtime: BrainRuntime = None  # initialized in startup


def _init_brain(client: AsyncWebClient):
    global brain_runtime
    brain_runtime = BrainRuntime(
        client=client,
        chat_fn=bot_chat,
        roast_fn=bot_roast,
        get_roast_mode=lambda uid: roast_mode.get(uid),
        is_roast_mode=lambda uid: uid in roast_mode,
    )


# ── Slash commands ─────────────────────────────────────────────────────────────

@app.command("/roast")
async def roast_cmd(ack, say, command, client):
    await ack()
    text = command.get("text", "").strip()
    user_id = command["user_id"]
    mode = roast_mode.get(user_id, "deep")

    mention_ids = parse_slack_mentions(text)
    if mention_ids:
        out = []
        clean_prompt = strip_slack_mentions(text)
        for uid in mention_ids:
            hint = clean_prompt or f"Roast them"
            response = await bot_roast(hint, uid, mode)
            out.append(f"{slack_mention(uid)} {response}")
        final = "\n".join(x for x in out if x.strip()) or "Even all the models refused to roast."
        await say(final)
        return

    if text:
        resp = await bot_roast(text, user_id, mode)
        if not resp or not resp.strip():
            resp = "Even the AI models said 'nah bro I'm good'."
        await say(f"{slack_mention(user_id)} {resp}")
        return

    await say("Use `/roast @User`, `/roast @User1 @User2`, or `/roast your text here`")


@app.command("/data")
async def data_cmd(ack, respond, command):
    await ack()
    text = command.get("text", "").strip()
    mention_ids = parse_slack_mentions(text)
    target_uid = mention_ids[0] if mention_ids else command["user_id"]

    mem = get_user_memory(target_uid)
    lf = mem["LF"]; eb = mem["EB"]; hp = mem["HP"]; isec = mem["IS"]; spm = mem["SPM"]
    summary = mem["LTS"] or "No long-term summary yet."

    text_out = (
        f"*Memory Profile for <@{target_uid}>*\n\n"
        f"*Long-Term Summary:*\n{summary}\n\n"
        f"*Linguistic Style:*\nSlang: `{lf['slang']:.2f}` | Emoji Rate: `{lf['emoji_rate']:.2f}` | "
        f"All Caps: `{lf['all_caps_rate']:.2f}` | Avg Len: `{lf['avg_len']:.2f}`\n\n"
        f"*Emotional Baseline:*\nAnger: `{eb['anger']:.2f}` | Sadness: `{eb['sadness']:.2f}` | "
        f"Hype: `{eb['hype']:.2f}` | Chaos: `{eb['chaos']:.2f}`\n\n"
        f"*Humor Preferences:*\nDark: `{hp['dark']:.2f}` | Mean: `{hp['mean']:.2f}` | "
        f"Petty: `{hp['petty']:.2f}` | Goofy: `{hp['goofy']:.2f}`\n\n"
        f"*Interaction Stats:*\nBot Mentions: `{isec['bot_mentions']}` | "
        f"Roast Requests: `{isec['roast_requests']}` | Self Roasts: `{isec['self_roasts']}`\n\n"
        f"*Memory:* `{len(spm['texts'])}` stored messages"
    )
    await respond(text_out)


@app.command("/autor")
async def autor_cmd(ack, respond, command):
    await ack()
    text = command.get("text", "").strip().lower()
    channel_id = command["channel_id"]
    if text == "on":
        auto_roast[channel_id] = True
        save_roast_memory()
        await respond("auto-roast is now on for this channel")
    elif text == "off":
        auto_roast.pop(channel_id, None)
        save_roast_memory()
        await respond("auto-roast is now off for this channel")
    else:
        await respond("Usage: `/autor on` or `/autor off`")


@app.command("/roastmode")
async def roastmode_cmd(ack, respond, command):
    await ack()
    mode_choice = command.get("text", "").strip().lower()
    user_id = command["user_id"]
    if mode_choice == "off":
        if user_id in roast_mode:
            del roast_mode[user_id]
            roast_history.pop(user_id, None)
            save_roast_memory()
            await respond("🏳️ Roast Mode Turned Off.")
        else:
            await respond("You were not in roast mode.")
    elif mode_choice in ("fast", "deep", "adjustable"):
        roast_mode[user_id] = mode_choice
        roast_history[user_id] = []
        save_roast_memory()
        await respond(f"🔥 Roast Mode: *{mode_choice.upper()}*. Use `/roastmode off` to stop.")
    else:
        await respond("Usage: `/roastmode fast|deep|adjustable|off`")


# ── Message event ─────────────────────────────────────────────────────────────

@app.event("message")
async def handle_message(event, say, client, context):
    # ignore bot messages and subtypes (edits, deletes, etc.)
    if event.get("subtype") or event.get("bot_id"):
        return

    uid = event.get("user")
    if not uid:
        return

    text = event.get("text", "").strip()
    channel_id = event.get("channel", "")
    ts = event.get("ts", "")
    team_id = event.get("team", "")
    enterprise_id = event.get("enterprise_id") or context.get("enterprise_id", "")

    skey = session_key(channel_id, uid)
    convo = ACTIVE_CONVO.get(skey)
    last_bot = LAST_BOT_MESSAGE.get(skey)

    # update user memory
    try:
        update_user_memory_from_message(text, uid, channel_id)
    except Exception as e:
        log(f"[MEMORY] update failed: {e}")

    # observe for brain
    if brain_runtime and text and not text.startswith(("/", "!")):
        brain_runtime.brain.observe_channel_message(channel_id, text, ts)
        brain_runtime.brain.observe_semantic_memory_slack(uid, channel_id, team_id, text)

    # check if bot is mentioned
    bot_user_id = context.get("bot_user_id", "")
    bot_mentioned = bool(bot_user_id and f"<@{bot_user_id}>" in text)
    alias_mentioned = mentions_fusbot(text)
    mentioned = bot_mentioned or alias_mentioned
    # in the restricted workspace, only reply freely in the designated channel
    _allowed_team = os.getenv("ALLOWED_TEAM_ID", "")
    _allowed_channel = os.getenv("ALLOWED_CHANNEL_ID", "")
    if _allowed_team and (team_id == _allowed_team or enterprise_id == _allowed_team) and channel_id != _allowed_channel:
        if not mentioned:
            return

    # auto-roast when mentioned in auto-roast channel
    if mentioned and auto_roast.get(channel_id):
        mention_ids = [u for u in parse_slack_mentions(text) if u != bot_user_id]
        target_uid = mention_ids[0] if mention_ids else uid
        prompt = strip_slack_mentions(text) or f"Roast them"
        mode = roast_mode.get(uid, "deep")
        reply = await bot_roast(prompt, target_uid, mode)
        if reply:
            await say(f"{slack_mention(target_uid)} {reply}")
            LAST_BOT_MESSAGE[skey] = reply
            ACTIVE_CONVO[skey] = {"user_id": uid, "last_ts": time.time(), "misses": 0}
        return

    # expire old conversations
    if convo and (time.time() - convo["last_ts"] > 120):
        ACTIVE_CONVO.pop(skey, None)
        LAST_BOT_MESSAGE.pop(skey, None)
        convo = None
        last_bot = None

    # follow-up detection
    if last_bot:
        is_followup = obvious_followup(text, convo)
        if not is_followup:
            is_followup = await ai_is_followup(last_bot, text)
        if is_followup:
            reply = await bot_chat(text, uid, channel_id, team_id)
            if reply:
                await say(reply)
                LAST_BOT_MESSAGE[skey] = reply
                ACTIVE_CONVO[skey] = {"user_id": uid, "last_ts": time.time(), "misses": 0}
            return

    # brain-driven response
    if brain_runtime and text and not text.startswith(("/", "!")):
        reply = await brain_runtime.on_message_slack(
            uid=uid,
            channel_id=channel_id,
            team_id=team_id,
            text=text,
            ts=ts,
            bot_user_id=bot_user_id,
            say=say,
        )
        if reply:
            LAST_BOT_MESSAGE[skey] = reply
            ACTIVE_CONVO[skey] = {"user_id": uid, "last_ts": time.time(), "misses": 0}


@app.event("reaction_added")
async def handle_reaction(event, client):
    if brain_runtime:
        brain_runtime.brain.observe_reaction(
            channel_id=event["item"]["channel"],
            user_id=event["user"],
            emoji=event["reaction"],
        )
        brain_runtime.brain.observe_reaction_back_from_event(event["user"], event["item"]["ts"])


# ── Extension loader ───────────────────────────────────────────────────────────

EXTENSIONS = [
    "recommend", "help", "server_setup", "quests", "titles",
    "collection", "guilds", "world", "achievement", "profile",
    "voidmaze", "arena", "lab", "dungeon", "economy",
    "code", "lichess_status", "hack", "automod", "afk",
    "img_gen", "aki", "animal", "badge", "emojimixup",
    "rave", "battleship", "monopoly",
]


async def load_extensions():
    for ext in EXTENSIONS:
        try:
            mod = __import__(ext)
            if hasattr(mod, "setup"):
                await mod.setup(app)
            print(f"[EXT] {ext} loaded")
        except Exception as e:
            print(f"[EXT] FAILED to load {ext}: {e}")


# ── Startup ────────────────────────────────────────────────────────────────────

async def main():
    client = AsyncWebClient(token=os.environ.get("SLACK_BOT_TOKEN"))
    _init_brain(client)
    await load_extensions()
    brain_runtime.start()
    handler = AsyncSocketModeHandler(app, os.environ.get("SLACK_APP_TOKEN"))
    print("FuSBot (Slack) starting...")
    await handler.start_async()


if __name__ == "__main__":
    asyncio.run(main())
