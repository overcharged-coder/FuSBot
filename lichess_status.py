import asyncio
import datetime
import json
import aiohttp

STATUS_URL = "https://raw.githubusercontent.com/Omo-star/icbmsaregoated2/main/lichess_status.json"

_cached_data = None
_cached_etag = None
_stream_sessions: dict[str, bool] = {}


async def fetch_status():
    global _cached_data, _cached_etag
    headers = {}
    if _cached_etag is not None:
        headers["If-None-Match"] = _cached_etag
    async with aiohttp.ClientSession() as session:
        async with session.get(STATUS_URL, headers=headers) as resp:
            if resp.status == 304 and _cached_data is not None:
                return _cached_data
            if resp.status != 200:
                raise ValueError(f"HTTP {resp.status}")
            data = json.loads(await resp.text())
            _cached_data = data
            _cached_etag = resp.headers.get("ETag")
            return data


def fmt_time(seconds):
    try:
        seconds = int(seconds)
        return f"{seconds//60}:{seconds%60:02d}"
    except Exception:
        return "N/A"


def fmt_moves(moves_str):
    if not moves_str:
        return "No moves found."
    moves = moves_str.split()
    out = []
    n = 1
    for i in range(0, len(moves), 2):
        w = moves[i]
        b = moves[i + 1] if i + 1 < len(moves) else "…"
        out.append(f"{n}. {w}   {b}")
        n += 1
    return "\n".join(out)


def paginate_moves(moves_str, limit=900):
    full = fmt_moves(moves_str)
    if len(full) <= limit:
        return [full]
    lines = full.split("\n")
    pages = []
    buf = []
    length = 0
    for line in lines:
        if length + len(line) + 1 > limit and buf:
            pages.append("\n".join(buf))
            buf = [line]
            length = len(line) + 1
        else:
            buf.append(line)
            length += len(line) + 1
    if buf:
        pages.append("\n".join(buf))
    return pages


def make_status_text(data: dict) -> str:
    online = data.get("online", False)
    playing = data.get("playing", False)
    rating = data.get("rating", "N/A")
    opponent = data.get("opponent", "None")
    variant = data.get("variant", "N/A")
    time_control = data.get("time_control", "N/A")
    time_left = data.get("time_left", "N/A")
    timestamp = data.get("timestamp", None)
    last_game = data.get("last_game", {})
    try:
        ts = datetime.datetime.fromisoformat(timestamp).strftime("%Y-%m-%d %H:%M:%S") if timestamp else "Unknown"
    except Exception:
        ts = "Unknown"
    lines = [
        "*Lichess Bot Status*",
        f"Online: `{online}` | Playing: `{playing}`",
        f"Rating: `{rating}` | Opponent: `{opponent}`",
        f"Variant: `{variant}` | Time: `{time_control}` | Left: `{time_left}`",
    ]
    if last_game:
        result = last_game.get("result", "Unknown")
        opp = last_game.get("opponent", "Unknown")
        rdelta = last_game.get("rating_delta", 0)
        lines.append(f"*Last Game:* result=`{result}` vs `{opp}` Δ{rdelta:+}")
    lines.append(f"_Updated: {ts}_")
    return "\n".join(lines)


_game_pages: dict[str, tuple[dict, list[str], int]] = {}


async def setup(app):

    @app.command("/lichess")
    async def lichess(ack, command, respond):
        await ack()
        try:
            data = await fetch_status()
        except Exception as e:
            return await respond(text=f":x: Failed to fetch: `{e}`", response_type="ephemeral")
        await respond(text=make_status_text(data))

    @app.command("/lichess_game")
    async def lichess_game(ack, command, client, respond):
        await ack()
        uid = command["user_id"]
        try:
            data = await fetch_status()
        except Exception as e:
            return await respond(text=f":x: Failed to fetch: `{e}`", response_type="ephemeral")
        game = data.get("last_game")
        if not game:
            return await respond(text=":warning: No last game found.", response_type="ephemeral")
        moves = game.get("moves", "")
        pages = paginate_moves(moves)
        _game_pages[uid] = (game, pages, 0)
        blocks = _game_blocks(game, pages, 0, uid)
        await respond(blocks=blocks, text="Last Game")

    def _game_blocks(game, pages, page_idx, uid):
        opponent = game.get("opponent", "Unknown")
        result = game.get("result", "Unknown")
        duration = game.get("duration", "N/A")
        bot_color = game.get("bot_color", "Unknown")
        termination = game.get("termination", "Unknown")
        rb = game.get("rating_before", "N/A")
        ra = game.get("rating_after", "N/A")
        info = f"*vs {opponent}* — Result: `{result}`\nColor: `{bot_color}` | Duration: `{fmt_time(duration)}` | Termination: `{termination}`\nRating: `{rb}` → `{ra}`"
        total = len(pages)
        move_text = pages[page_idx] if pages else "No moves"
        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": info}},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*Moves (page {page_idx+1}/{total}):*\n```\n{move_text}\n```"}},
        ]
        if total > 1:
            buttons = []
            if page_idx > 0:
                buttons.append({"type": "button", "text": {"type": "plain_text", "text": "Prev"}, "action_id": "lichess_prev", "value": uid})
            if page_idx < total - 1:
                buttons.append({"type": "button", "text": {"type": "plain_text", "text": "Next"}, "action_id": "lichess_next", "value": uid})
            if buttons:
                blocks.append({"type": "actions", "elements": buttons})
        return blocks

    @app.action("lichess_prev")
    async def lichess_prev(ack, body, client):
        await ack()
        uid = body["actions"][0]["value"]
        if uid not in _game_pages:
            return
        game, pages, idx = _game_pages[uid]
        idx = max(0, idx - 1)
        _game_pages[uid] = (game, pages, idx)
        channel = body["container"]["channel_id"]
        ts = body["container"]["message_ts"]
        blocks = _game_blocks(game, pages, idx, uid)
        await client.chat_update(channel=channel, ts=ts, blocks=blocks, text="Last Game")

    @app.action("lichess_next")
    async def lichess_next(ack, body, client):
        await ack()
        uid = body["actions"][0]["value"]
        if uid not in _game_pages:
            return
        game, pages, idx = _game_pages[uid]
        idx = min(len(pages) - 1, idx + 1)
        _game_pages[uid] = (game, pages, idx)
        channel = body["container"]["channel_id"]
        ts = body["container"]["message_ts"]
        blocks = _game_blocks(game, pages, idx, uid)
        await client.chat_update(channel=channel, ts=ts, blocks=blocks, text="Last Game")

    @app.command("/lichess_stream")
    async def lichess_stream(ack, command, client):
        await ack()
        uid = command["user_id"]
        channel = command["channel_id"]
        try:
            data = await fetch_status()
        except Exception as e:
            await client.chat_postEphemeral(channel=channel, user=uid, text=f":x: `{e}`")
            return
        result = await client.chat_postMessage(channel=channel, text=make_status_text(data), blocks=[
            {"type": "section", "text": {"type": "mrkdwn", "text": make_status_text(data)}},
            {"type": "actions", "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "Stop"}, "action_id": "lichess_stop", "style": "danger", "value": uid},
            ]},
        ])
        ts = result["ts"]
        _stream_sessions[uid] = True

        async def _stream():
            for _ in range(120):
                await asyncio.sleep(10)
                if not _stream_sessions.get(uid, False):
                    break
                try:
                    d = await fetch_status()
                except Exception:
                    continue
                try:
                    await client.chat_update(channel=channel, ts=ts, text=make_status_text(d), blocks=[
                        {"type": "section", "text": {"type": "mrkdwn", "text": make_status_text(d)}},
                        {"type": "actions", "elements": [
                            {"type": "button", "text": {"type": "plain_text", "text": "Stop"}, "action_id": "lichess_stop", "style": "danger", "value": uid},
                        ]},
                    ])
                except Exception:
                    break
            _stream_sessions.pop(uid, None)

        asyncio.ensure_future(_stream())

    @app.action("lichess_stop")
    async def lichess_stop(ack, body, client):
        await ack()
        uid = body["actions"][0]["value"]
        _stream_sessions[uid] = False
        channel = body["container"]["channel_id"]
        ts = body["container"]["message_ts"]
        await client.chat_update(channel=channel, ts=ts, text=":stop_sign: Stream stopped.", blocks=[
            {"type": "section", "text": {"type": "mrkdwn", "text": ":stop_sign: Stream stopped."}}
        ])
