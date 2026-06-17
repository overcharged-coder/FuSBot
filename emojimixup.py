import aiohttp
import asyncio
import json
import random
import io
import time
from pathlib import Path

DISCOVERY_DATES = ["20201001","20210218","20210521","20210831","20220203","20220823"]
MAX_HISTORY = 25
MAX_FAVORITES = 50

_BASE = Path(__file__).parent
_EMOJIS_FILE = _BASE / "emojis.txt"
_MIXUP_PATH = _BASE / "mixup_emojis.json"
_DATA_PATH = _BASE / "emojimixup_data.json"

_emojis: list[str] = []
_mixups: dict[str, str] = {}
_data: dict = {"history": {}, "favorites": {}}
_lock = asyncio.Lock()
_session: aiohttp.ClientSession | None = None
_sessions_state: dict[str, dict] = {}


def _codepoints(e: str) -> str:
    return "_".join(hex(ord(c))[2:] for c in e)


def _key(a: str, b: str) -> str:
    return "_".join(sorted([a, b]))


def _load():
    global _emojis, _mixups, _data
    if _EMOJIS_FILE.exists():
        _emojis = _EMOJIS_FILE.read_text(encoding="utf-8").splitlines()
    if _MIXUP_PATH.exists():
        _mixups = json.loads(_MIXUP_PATH.read_text(encoding="utf-8"))
    if _DATA_PATH.exists():
        _data = json.loads(_DATA_PATH.read_text(encoding="utf-8"))


def _save_data():
    _DATA_PATH.write_text(json.dumps(_data, ensure_ascii=False, indent=2), encoding="utf-8")


def _save_mixups():
    _MIXUP_PATH.write_text(json.dumps(_mixups, ensure_ascii=False, indent=2), encoding="utf-8")


async def _get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession()
    return _session


async def _discover_mix(a: str, b: str) -> str | None:
    cp1, cp2 = _codepoints(a), _codepoints(b)
    sess = await _get_session()
    for d in DISCOVERY_DATES:
        for x, y in [(cp1, cp2), (cp2, cp1)]:
            url = f"https://www.gstatic.com/android/keyboard/emojikitchen/{d}/u{x}/u{x}_u{y}.png"
            async with sess.get(url) as r:
                if r.status == 200:
                    async with _lock:
                        _mixups[_key(a, b)] = f"{d}/u{x}/u{x}_u{y}.png"
                        _save_mixups()
                    return url
    return None


async def _get_mix_bytes(a: str, b: str) -> tuple[bytes, str] | None:
    k = _key(a, b)
    if k in _mixups:
        url = f"https://www.gstatic.com/android/keyboard/emojikitchen/{_mixups[k]}"
    else:
        url = await _discover_mix(a, b)
        if not url:
            return None
    sess = await _get_session()
    async with sess.get(url) as r:
        return await r.read(), url


def _record_history(uid: str, a: str, b: str, url: str):
    _data.setdefault("history", {}).setdefault(uid, [])
    _data["history"][uid].insert(0, {"a": a, "b": b, "url": url, "ts": time.time()})
    _data["history"][uid] = _data["history"][uid][:MAX_HISTORY]
    _save_data()


def _add_favorite(uid: str, a: str, b: str) -> bool:
    k = _key(a, b)
    _data.setdefault("favorites", {}).setdefault(uid, [])
    if k in _data["favorites"][uid]:
        return False
    _data["favorites"][uid].insert(0, k)
    _data["favorites"][uid] = _data["favorites"][uid][:MAX_FAVORITES]
    _save_data()
    return True


def _mix_blocks(uid: str, a: str, b: str, image_url: str | None = None) -> list[dict]:
    blocks: list[dict] = [
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*{a} + {b}*"}},
    ]
    if image_url:
        blocks.append({"type": "image", "image_url": image_url, "alt_text": f"{a}+{b}"})
    blocks.append({"type": "actions", "elements": [
        {"type": "button", "text": {"type": "plain_text", "text": "🔀 Remix"}, "action_id": "emj_remix", "value": uid},
        {"type": "button", "text": {"type": "plain_text", "text": "↔️ Swap"}, "action_id": "emj_swap", "value": uid},
        {"type": "button", "text": {"type": "plain_text", "text": "🎲 Random Left"}, "action_id": "emj_rand_left", "value": uid},
        {"type": "button", "text": {"type": "plain_text", "text": "🎲 Random Right"}, "action_id": "emj_rand_right", "value": uid},
        {"type": "button", "text": {"type": "plain_text", "text": "⭐ Favorite"}, "action_id": "emj_favorite", "value": uid},
    ]})
    return blocks


async def _do_mix(client, uid: str, channel: str, ts: str | None, a: str, b: str):
    result = await _get_mix_bytes(a, b)
    if not result:
        if ts:
            await client.chat_update(channel=channel, ts=ts, text=":x: No mix found for those emojis.")
        else:
            await client.chat_postMessage(channel=channel, text=":x: No mix found.")
        return
    data_bytes, url = result
    _record_history(uid, a, b, url)
    _sessions_state[uid] = {"e1": a, "e2": b}
    if ts:
        await client.chat_update(channel=channel, ts=ts, blocks=_mix_blocks(uid, a, b, url), text=f"{a}+{b}")
    else:
        buf = io.BytesIO(data_bytes)
        await client.files_upload_v2(channel=channel, file=buf, filename="emoji.png", initial_comment=f"*{a} + {b}*")
        result2 = await client.chat_postMessage(channel=channel, blocks=_mix_blocks(uid, a, b, url), text=f"{a}+{b}")


async def setup(app):
    _load()

    @app.command("/fus_emojimixup")
    async def emojimixup(ack, command, client):
        await ack()
        uid = command["user_id"]; channel = command["channel_id"]
        args = (command.get("text") or "").split()
        if len(args) < 2:
            return await client.chat_postEphemeral(channel=channel, user=uid, text="Usage: `/fus_emojimixup emoji1 emoji2`")
        a, b = args[0], args[1]
        if not _emojis:
            return await client.chat_postEphemeral(channel=channel, user=uid, text=":x: emojis.txt not found.")
        if a not in _emojis or b not in _emojis:
            return await client.chat_postEphemeral(channel=channel, user=uid, text=":x: Unsupported emoji.")
        asyncio.ensure_future(_do_mix(client, uid, channel, None, a, b))

    @app.action("emj_remix")
    async def emj_remix(ack, body, client):
        await ack()
        uid = body["actions"][0]["value"]
        if body["user"]["id"] != uid: return
        channel = body["container"]["channel_id"]; ts = body["container"]["message_ts"]
        if not _emojis: return
        for _ in range(20):
            a, b = random.sample(_emojis, 2)
            result = await _get_mix_bytes(a, b)
            if result:
                data_bytes, url = result
                _record_history(uid, a, b, url)
                _sessions_state[uid] = {"e1": a, "e2": b}
                await client.chat_update(channel=channel, ts=ts, blocks=_mix_blocks(uid, a, b, url), text=f"{a}+{b}")
                return
        await client.chat_postEphemeral(channel=channel, user=uid, text=":x: No valid mix found.")

    @app.action("emj_swap")
    async def emj_swap(ack, body, client):
        await ack()
        uid = body["actions"][0]["value"]
        if body["user"]["id"] != uid: return
        s = _sessions_state.get(uid, {})
        a, b = s.get("e2",""), s.get("e1","")
        if not a or not b: return
        channel = body["container"]["channel_id"]; ts = body["container"]["message_ts"]
        asyncio.ensure_future(_do_mix(client, uid, channel, ts, a, b))

    @app.action("emj_rand_left")
    async def emj_rand_left(ack, body, client):
        await ack()
        uid = body["actions"][0]["value"]
        if body["user"]["id"] != uid: return
        s = _sessions_state.get(uid, {}); b_emoji = s.get("e2","")
        if not b_emoji or not _emojis: return
        channel = body["container"]["channel_id"]; ts = body["container"]["message_ts"]
        for _ in range(20):
            a = random.choice(_emojis)
            result = await _get_mix_bytes(a, b_emoji)
            if result:
                data_bytes, url = result
                _record_history(uid, a, b_emoji, url)
                _sessions_state[uid] = {"e1": a, "e2": b_emoji}
                await client.chat_update(channel=channel, ts=ts, blocks=_mix_blocks(uid, a, b_emoji, url), text=f"{a}+{b_emoji}")
                return
        await client.chat_postEphemeral(channel=channel, user=uid, text=":x: No valid mix found.")

    @app.action("emj_rand_right")
    async def emj_rand_right(ack, body, client):
        await ack()
        uid = body["actions"][0]["value"]
        if body["user"]["id"] != uid: return
        s = _sessions_state.get(uid, {}); a_emoji = s.get("e1","")
        if not a_emoji or not _emojis: return
        channel = body["container"]["channel_id"]; ts = body["container"]["message_ts"]
        for _ in range(20):
            b = random.choice(_emojis)
            result = await _get_mix_bytes(a_emoji, b)
            if result:
                data_bytes, url = result
                _record_history(uid, a_emoji, b, url)
                _sessions_state[uid] = {"e1": a_emoji, "e2": b}
                await client.chat_update(channel=channel, ts=ts, blocks=_mix_blocks(uid, a_emoji, b, url), text=f"{a_emoji}+{b}")
                return
        await client.chat_postEphemeral(channel=channel, user=uid, text=":x: No valid mix found.")

    @app.action("emj_favorite")
    async def emj_favorite(ack, body, client):
        await ack()
        uid = body["actions"][0]["value"]
        actor = body["user"]["id"]
        if actor != uid: return
        s = _sessions_state.get(uid, {})
        a, b = s.get("e1",""), s.get("e2","")
        if not a or not b: return
        ok = _add_favorite(uid, a, b)
        channel = body["container"]["channel_id"]
        await client.chat_postEphemeral(channel=channel, user=uid, text=":star: Saved!" if ok else "Already saved.")
