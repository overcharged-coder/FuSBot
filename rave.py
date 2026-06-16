import asyncio
import logging
import math
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import aiohttp
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip, ColorClip, ImageClip
from PIL import Image, ImageDraw, ImageFont
import numpy as np

log = logging.getLogger("rave")

DATA = Path("data/rave")
ASSETS = DATA / "assets"
UPLOADS = DATA / "uploads"

DATA.mkdir(parents=True, exist_ok=True)
ASSETS.mkdir(exist_ok=True)
UPLOADS.mkdir(exist_ok=True)

FONT_URL = "https://github.com/matomo-org/travis-scripts/raw/master/fonts/Verdana.ttf"
FONT = ASSETS / "Verdana.ttf"
CRAB_TEMPLATE = ASSETS / "crab_template.mp4"
QUEUE = asyncio.Semaphore(2)
MAX_MB = 8


class Mode(str, Enum):
    TEMPLATE = "Crab Rave"
    BUILD = "Build"


class Base(str, Enum):
    PULSE = "Pulse"
    CHECKER = "Checker"
    STROBE = "Strobe"
    GRADIENT = "Gradient"
    UPLOAD = "Upload"


class Anim(str, Enum):
    STATIC = "Static"
    BOUNCE = "Bounce"


@dataclass
class Cfg:
    mode: Mode = Mode.TEMPLATE
    base: Base = Base.PULSE
    anim: Anim = Anim.BOUNCE
    top: str = "TOP TEXT"
    bottom: str = "BOTTOM TEXT"
    font: int = 56
    dur: float = 15.4
    fps: int = 24
    bpm: int = 128
    upload: str = ""


def _now_ms() -> str:
    return str(int(time.time() * 1000))


def text_clip(txt, font_path, fontsize, color, duration, pos):
    font = ImageFont.truetype(font_path, fontsize)
    dummy = Image.new("RGBA", (1, 1))
    d = ImageDraw.Draw(dummy)
    w, h = d.textbbox((0, 0), txt, font=font)[2:]
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.text((0, 0), txt, font=font, fill=color)
    return ImageClip(np.array(img)).set_duration(duration).set_position(pos)


async def _ensure_font():
    if not FONT.exists():
        async with aiohttp.ClientSession() as s:
            async with s.get(FONT_URL) as r:
                FONT.write_bytes(await r.read())
    if not CRAB_TEMPLATE.exists():
        raise RuntimeError("Missing crab_template.mp4 in data/rave/assets/")


def render(uid: str, cfg: Cfg, preview: bool) -> Path:
    dur = 6 if preview else cfg.dur
    size = (854, 480) if preview else (1280, 720)

    if cfg.mode == Mode.TEMPLATE:
        clip = VideoFileClip(str(CRAB_TEMPLATE)).subclip(0, dur).resize(size)
    elif cfg.base == Base.UPLOAD:
        if not cfg.upload:
            raise ValueError("No upload key set")
        path = UPLOADS / f"{uid}_{cfg.upload}"
        if not path.exists():
            raise FileNotFoundError(f"Upload not found: {path}")
        clip = VideoFileClip(str(path)).loop(duration=dur).resize(height=size[1])
    else:
        clip = ColorClip(size, color=(10, 10, 10), duration=dur)

    def pos_top(t):
        dy = 30 * math.sin(2 * math.pi * cfg.bpm / 60 * t) if cfg.anim == Anim.BOUNCE else 0
        return ("center", int(size[1] * 0.08 + dy))

    def pos_bottom(t):
        dy = 30 * math.sin(2 * math.pi * cfg.bpm / 60 * t) if cfg.anim == Anim.BOUNCE else 0
        return ("center", int(size[1] * 0.80 + dy))

    top = text_clip(cfg.top.upper(), str(FONT), cfg.font, "white", dur, pos_top)
    bottom = text_clip(cfg.bottom.upper(), str(FONT), cfg.font, "white", dur, pos_bottom)
    comp = CompositeVideoClip([clip, top, bottom], size=size)
    out = DATA / f"{uid}_{_now_ms()}.mp4"
    comp.write_videofile(str(out), fps=cfg.fps, preset="superfast", logger=None)
    comp.close()
    clip.close()
    return out


_sessions: dict[str, dict] = {}


def _cfg_from_session(uid: str) -> Cfg:
    s = _sessions.get(uid, {})
    return Cfg(
        mode=Mode(s.get("mode", Mode.TEMPLATE.value)),
        base=Base(s.get("base", Base.PULSE.value)),
        anim=Anim(s.get("anim", Anim.BOUNCE.value)),
        top=s.get("top", "TOP TEXT"),
        bottom=s.get("bottom", "BOTTOM TEXT"),
        upload=s.get("upload", ""),
    )


def _session_blocks(uid: str, status: str = "Idle") -> list[dict]:
    cfg = _cfg_from_session(uid)
    return [
        {"type": "header", "text": {"type": "plain_text", "text": "Rave Builder", "emoji": True}},
        {"type": "section", "fields": [
            {"type": "mrkdwn", "text": f"*Mode*\n{cfg.mode.value}"},
            {"type": "mrkdwn", "text": f"*Base*\n{cfg.base.value}"},
            {"type": "mrkdwn", "text": f"*Anim*\n{cfg.anim.value}"},
            {"type": "mrkdwn", "text": f"*Status*\n{status}"},
        ]},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*Text*\n{cfg.top} / {cfg.bottom}"}},
        {"type": "actions", "block_id": "rave_controls", "elements": [
            {"type": "static_select", "placeholder": {"type": "plain_text", "text": "Mode"}, "action_id": "rave_mode",
             "options": [{"text": {"type": "plain_text", "text": m.value}, "value": m.value} for m in Mode]},
            {"type": "static_select", "placeholder": {"type": "plain_text", "text": "Base"}, "action_id": "rave_base",
             "options": [{"text": {"type": "plain_text", "text": b.value}, "value": b.value} for b in Base]},
            {"type": "static_select", "placeholder": {"type": "plain_text", "text": "Anim"}, "action_id": "rave_anim",
             "options": [{"text": {"type": "plain_text", "text": a.value}, "value": a.value} for a in Anim]},
        ]},
        {"type": "actions", "block_id": "rave_render", "elements": [
            {"type": "button", "text": {"type": "plain_text", "text": "Set Text"}, "action_id": "rave_set_text"},
            {"type": "button", "text": {"type": "plain_text", "text": "Set Upload Key"}, "action_id": "rave_set_upload"},
            {"type": "button", "text": {"type": "plain_text", "text": "Preview"}, "action_id": "rave_preview", "style": "primary"},
            {"type": "button", "text": {"type": "plain_text", "text": "Render"}, "action_id": "rave_render_btn", "style": "primary"},
        ]},
    ]


async def setup(app):
    @app.command("/rave")
    async def rave_cmd(ack, command, client):
        await ack()
        uid = command["user_id"]; channel = command["channel_id"]
        parts = (command.get("text") or "").strip().split(None, 1)
        sub = parts[0].lower() if parts else ""
        arg = parts[1].strip() if len(parts) > 1 else ""

        if sub == "bg":
            upload_key = arg
            if not upload_key:
                await client.chat_postEphemeral(channel=channel, user=uid, text="Usage: `/rave bg <upload_key>` — share a video file and set its key here.")
                return
            _sessions.setdefault(uid, {})["upload"] = upload_key
            await client.chat_postEphemeral(channel=channel, user=uid, text=f"Upload key set to `{upload_key}`.")

        else:
            try:
                await _ensure_font()
            except RuntimeError as e:
                await client.chat_postEphemeral(channel=channel, user=uid, text=str(e))
                return
            _sessions[uid] = {}
            await client.chat_postMessage(channel=channel, blocks=_session_blocks(uid), text="Rave Builder")

    @app.action("rave_mode")
    async def rave_mode(ack, body, client):
        await ack()
        uid = body["user"]["id"]
        val = body["actions"][0]["selected_option"]["value"]
        _sessions.setdefault(uid, {})["mode"] = val
        msg_ts = body["container"]["message_ts"]
        channel = body["container"]["channel_id"]
        await client.chat_update(channel=channel, ts=msg_ts, blocks=_session_blocks(uid), text="Rave Builder")

    @app.action("rave_base")
    async def rave_base(ack, body, client):
        await ack()
        uid = body["user"]["id"]
        val = body["actions"][0]["selected_option"]["value"]
        _sessions.setdefault(uid, {})["base"] = val
        msg_ts = body["container"]["message_ts"]
        channel = body["container"]["channel_id"]
        await client.chat_update(channel=channel, ts=msg_ts, blocks=_session_blocks(uid), text="Rave Builder")

    @app.action("rave_anim")
    async def rave_anim(ack, body, client):
        await ack()
        uid = body["user"]["id"]
        val = body["actions"][0]["selected_option"]["value"]
        _sessions.setdefault(uid, {})["anim"] = val
        msg_ts = body["container"]["message_ts"]
        channel = body["container"]["channel_id"]
        await client.chat_update(channel=channel, ts=msg_ts, blocks=_session_blocks(uid), text="Rave Builder")

    @app.action("rave_set_text")
    async def rave_set_text(ack, body, client):
        await ack()
        uid = body["user"]["id"]
        s = _sessions.get(uid, {})
        await client.views_open(
            trigger_id=body["trigger_id"],
            view={
                "type": "modal", "callback_id": "rave_text_modal", "title": {"type": "plain_text", "text": "Set Text"},
                "submit": {"type": "plain_text", "text": "Save"},
                "private_metadata": body["container"]["message_ts"] + "|" + body["container"]["channel_id"],
                "blocks": [
                    {"type": "input", "block_id": "top_block", "label": {"type": "plain_text", "text": "Top Text"}, "element": {"type": "plain_text_input", "action_id": "top_input", "initial_value": s.get("top", "TOP TEXT")}},
                    {"type": "input", "block_id": "bottom_block", "label": {"type": "plain_text", "text": "Bottom Text"}, "element": {"type": "plain_text_input", "action_id": "bottom_input", "initial_value": s.get("bottom", "BOTTOM TEXT")}},
                ],
            }
        )

    @app.view("rave_text_modal")
    async def rave_text_modal(ack, body, client):
        await ack()
        uid = body["user"]["id"]
        vals = body["view"]["state"]["values"]
        top = vals["top_block"]["top_input"]["value"] or "TOP TEXT"
        bottom = vals["bottom_block"]["bottom_input"]["value"] or "BOTTOM TEXT"
        _sessions.setdefault(uid, {}).update({"top": top, "bottom": bottom})
        meta = body["view"].get("private_metadata", "")
        parts = meta.split("|", 1)
        if len(parts) == 2:
            msg_ts, channel = parts
            await client.chat_update(channel=channel, ts=msg_ts, blocks=_session_blocks(uid), text="Rave Builder")

    @app.action("rave_set_upload")
    async def rave_set_upload(ack, body, client):
        await ack()
        uid = body["user"]["id"]
        s = _sessions.get(uid, {})
        await client.views_open(
            trigger_id=body["trigger_id"],
            view={
                "type": "modal", "callback_id": "rave_upload_modal", "title": {"type": "plain_text", "text": "Set Upload Key"},
                "submit": {"type": "plain_text", "text": "Save"},
                "private_metadata": body["container"]["message_ts"] + "|" + body["container"]["channel_id"],
                "blocks": [
                    {"type": "input", "block_id": "key_block", "label": {"type": "plain_text", "text": "Upload Key"}, "element": {"type": "plain_text_input", "action_id": "key_input", "initial_value": s.get("upload", "")}},
                ],
            }
        )

    @app.view("rave_upload_modal")
    async def rave_upload_modal(ack, body, client):
        await ack()
        uid = body["user"]["id"]
        vals = body["view"]["state"]["values"]
        key = vals["key_block"]["key_input"]["value"] or ""
        _sessions.setdefault(uid, {})["upload"] = key.strip()
        meta = body["view"].get("private_metadata", "")
        parts = meta.split("|", 1)
        if len(parts) == 2:
            msg_ts, channel = parts
            await client.chat_update(channel=channel, ts=msg_ts, blocks=_session_blocks(uid), text="Rave Builder")

    async def _do_render(uid: str, channel: str, msg_ts: str, preview: bool, client):
        cfg = _cfg_from_session(uid)
        if cfg.base == Base.UPLOAD and not cfg.upload:
            await client.chat_postEphemeral(channel=channel, user=uid, text="Set an upload key first.")
            return
        async with QUEUE:
            await client.chat_update(channel=channel, ts=msg_ts, blocks=_session_blocks(uid, "Rendering..."), text="Rendering...")
            try:
                out = await asyncio.to_thread(render, uid, cfg, preview)
            except Exception as e:
                await client.chat_update(channel=channel, ts=msg_ts, blocks=_session_blocks(uid, "Error"), text="Render failed")
                await client.chat_postEphemeral(channel=channel, user=uid, text=f"Render failed: {e}")
                return
            try:
                await client.files_upload_v2(channel=channel, file=str(out), filename=out.name)
                os.remove(out)
            except Exception:
                pass
            _sessions.pop(uid, None)

    @app.action("rave_preview")
    async def rave_preview(ack, body, client):
        await ack()
        uid = body["user"]["id"]
        channel = body["container"]["channel_id"]
        msg_ts = body["container"]["message_ts"]
        asyncio.ensure_future(_do_render(uid, channel, msg_ts, True, client))

    @app.action("rave_render_btn")
    async def rave_render(ack, body, client):
        await ack()
        uid = body["user"]["id"]
        channel = body["container"]["channel_id"]
        msg_ts = body["container"]["message_ts"]
        asyncio.ensure_future(_do_render(uid, channel, msg_ts, False, client))
