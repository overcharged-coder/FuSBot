import asyncio
import aiohttp
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops, ImageEnhance
import math
import random
from economy_shared import load_state

ASSETS = "badge_assets"


def clamp(x, a, b):
    return a if x < a else b if x > b else x


# ── image helpers ──────────────────────────────────────────────────────────────

def _fonts():
    try:
        return (
            ImageFont.truetype(f"{ASSETS}/fonts/Orbitron-Bold.ttf", 30),
            ImageFont.truetype(f"{ASSETS}/fonts/Inter-Regular", 16),
            ImageFont.truetype(f"{ASSETS}/fonts/JetBrainsMono-Regular.ttf", 14),
            ImageFont.truetype(f"{ASSETS}/fonts/Inter-Regular", 12),
        )
    except Exception:
        f = ImageFont.load_default()
        return f, f, f, f


def _pulse(i, speed=0.2, lo=70, hi=140):
    t = (math.sin(i * speed) + 1) * 0.5
    return int(lo + (hi - lo) * t)


def _lerp(a, b, t):
    return int(a + (b - a) * t)


def _gradient(size, c1, c2, vertical=True):
    w, h = size
    img = Image.new("RGBA", size, (0, 0, 0, 255))
    px = img.load()
    if vertical:
        for y in range(h):
            t = y / max(1, h - 1)
            for x in range(w):
                px[x, y] = tuple(_lerp(c1[j], c2[j], t) for j in range(4))
    else:
        for x in range(w):
            t = x / max(1, w - 1)
            for y in range(h):
                px[x, y] = tuple(_lerp(c1[j], c2[j], t) for j in range(4))
    return img


def _vignette(size, strength=0.55):
    w, h = size
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((-w * 0.2, -h * 0.2, w * 1.2, h * 1.2), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(int(min(w, h) * 0.12)))
    inv = ImageChops.invert(mask)
    inv = ImageEnhance.Brightness(inv).enhance(strength)
    overlay = Image.new("RGBA", size, (0, 0, 0, 255))
    overlay.putalpha(inv)
    return overlay


def _scanlines(size, offset, alpha=28, step=4):
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for y in range(offset % step, size[1], step):
        draw.line((0, y, size[0], y), fill=(0, 0, 0, alpha))
    return img


def _noise(size, seed, amount=26):
    random.seed(seed)
    w, h = size
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    px = img.load()
    for _ in range(int(w * h * 0.02)):
        x = random.randint(0, w - 1)
        y = random.randint(0, h - 1)
        v = random.randint(0, 255)
        a = random.randint(0, amount)
        px[x, y] = (v, v, v, a)
    return img.filter(ImageFilter.GaussianBlur(0.6))


def _shimmer_band(size, x, width=140, alpha=55):
    band = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(band)
    for i in range(-width, width):
        t = 1 - abs(i) / max(1, width)
        a = int(alpha * (t ** 2))
        draw.line((x + i, 0, x + i, size[1]), fill=(255, 255, 255, a))
    return band.rotate(-14, resample=Image.BICUBIC, expand=False)


def _glitch_slices(img, seed, strength=12, slices=7):
    random.seed(seed)
    w, h = img.size
    out = img.copy()
    for _ in range(slices):
        y = random.randint(0, h - 1)
        sh = random.randint(6, 22)
        y2 = min(h, y + sh)
        dx = random.randint(-strength, strength)
        strip = img.crop((0, y, w, y2))
        out.paste(strip, (dx, y))
    if strength > 0:
        r, g, b, a = out.split()
        r = ImageChops.offset(r, random.randint(-2, 2), 0)
        b = ImageChops.offset(b, random.randint(-2, 2), 0)
        out = Image.merge("RGBA", (r, g, b, a))
    return out


def _rounded_panel(size, radius=22, fill=(255, 255, 255, 16), outline=(255, 255, 255, 28)):
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=fill, outline=outline, width=1)
    return img


def _bar(draw, x, y, w, h, pct, fg, bg=(255, 255, 255, 22), radius=10):
    pct = clamp(pct, 0, 1)
    draw.rounded_rectangle((x, y, x + w, y + h), radius=radius, fill=bg)
    fw = int(w * pct)
    if fw > 0:
        draw.rounded_rectangle((x, y, x + fw, y + h), radius=radius, fill=fg)


def _core_card(display_name, uid_str, accent, subtitle, right_lines, avatar_img, bg_top, bg_bottom, glass_alpha=20):
    title_f, body_f, mono_f, small_f = _fonts()
    base = _gradient((720, 320), bg_top, bg_bottom, vertical=True)
    base = Image.alpha_composite(base, _vignette(base.size, strength=0.45))
    draw = ImageDraw.Draw(base)
    draw.rectangle((0, 0, 7, 320), fill=accent + (255,))
    glass = _rounded_panel(base.size, radius=26, fill=(255, 255, 255, glass_alpha), outline=(255, 255, 255, 22))
    base = Image.alpha_composite(base, glass)
    av = avatar_img.resize((148, 148))
    glow = av.filter(ImageFilter.GaussianBlur(11))
    tint = Image.new("RGBA", glow.size, accent + (120,))
    glow = Image.alpha_composite(glow, tint)
    base.paste(glow, (46, 86), glow)
    base.paste(av, (46, 86), av)
    draw = ImageDraw.Draw(base)
    draw.text((220, 62), display_name, fill=(240, 240, 240, 255), font=title_f)
    draw.text((220, 102), subtitle, fill=(170, 170, 170, 255), font=body_f)
    ry = 64
    for i, line in enumerate(right_lines[:6]):
        draw.text((520, ry + i * 22), line, fill=(210, 210, 210, 240), font=small_f)
    return base


def _make_gif(frames, duration=60):
    buf = BytesIO()
    frames[0].save(buf, format="GIF", save_all=True, append_images=frames[1:], duration=duration, loop=0, disposal=2, optimize=False)
    buf.seek(0)
    buf.name = "badge.gif"
    return buf


def _animated_identity(display_name, uid_str, data):
    accent = (88, 101, 242)
    avatar = data["avatar"]
    balance = data["balance"]
    right = [f"${balance}", "IDENTITY", f"ID {uid_str}"]
    frames = []
    for i in range(24):
        base = _core_card(display_name, uid_str, accent, f"ID {uid_str}", right, avatar, (12, 14, 18, 255), (20, 20, 28, 255), glass_alpha=18)
        draw = ImageDraw.Draw(base)
        p = _pulse(i, speed=0.22, lo=70, hi=150)
        aura = Image.new("RGBA", base.size, (0, 0, 0, 0))
        a = ImageDraw.Draw(aura)
        a.ellipse((34, 74, 210, 250), outline=accent + (p,), width=3)
        aura = aura.filter(ImageFilter.GaussianBlur(2))
        base = Image.alpha_composite(base, aura)
        base.alpha_composite(_scanlines(base.size, i, alpha=24, step=4))
        base.alpha_composite(_noise(base.size, seed=(int(uid_str or 0) + i) * 7, amount=18))
        frames.append(base)
    return _make_gif(frames, duration=60)


def _animated_dungeon(display_name, uid_str, data):
    d = data.get("dungeon") or {}
    floor = d.get("floor", 0)
    hp = d.get("hp", 0)
    mhp = max(1, d.get("max_hp", 1))
    sanity = d.get("sanity", 100)
    msanity = max(1, d.get("max_sanity", 100))
    rift_depth = d.get("rift_depth", 0)
    boss_kills = d.get("boss_kills", 0)
    mutations = len(d.get("mutations", []) or [])
    curses = len(d.get("curses", []) or [])
    relics = len(d.get("relics", []) or [])
    low_sanity = (sanity / msanity) < 0.3
    accent = (140, 255, 200) if not low_sanity else (255, 80, 80)
    avatar = data["avatar"]
    right = [f"FLOOR {floor}", f"RIFT {rift_depth}", f"BOSS {boss_kills}", f"RELICS {relics}", f"CURSES {curses}", f"MUT {mutations}"]
    uid_int = int(uid_str or 0)
    frames = []
    for i in range(22):
        shake = int(2 * math.sin(i * 0.9)) if low_sanity else 0
        base = _core_card(display_name, uid_str, accent, "DUNGEON RUNNER", right, avatar, (10, 16, 14, 255), (18, 22, 18, 255), glass_alpha=16)
        draw = ImageDraw.Draw(base)
        bx, by = 220, 140
        _bar(draw, bx, by, 260, 18, hp / mhp, fg=(255, 90, 90, 220), bg=(255, 255, 255, 18), radius=10)
        draw.text((bx, by - 22), f"HP {hp}/{mhp}", fill=(220, 220, 220, 235), font=_fonts()[1])
        sy = by + 44
        spct = sanity / msanity
        sfg = (140, 255, 200, 220) if spct >= 0.3 else (255, 80, 80, 220)
        _bar(draw, bx, sy, 260, 18, spct, fg=sfg, bg=(255, 255, 255, 18), radius=10)
        draw.text((bx, sy - 22), f"SANITY {sanity}/{msanity}", fill=(220, 220, 220, 235), font=_fonts()[1])
        if low_sanity:
            pulse = _pulse(i, speed=0.35, lo=20, hi=90)
            warn = Image.new("RGBA", base.size, (255, 0, 0, pulse))
            base = Image.alpha_composite(base, warn)
        base.alpha_composite(_scanlines(base.size, i, alpha=22, step=5))
        base.alpha_composite(_noise(base.size, seed=(uid_int + 991) * (i + 3), amount=16))
        if shake != 0:
            base = ImageChops.offset(base, shake, 0)
        frames.append(base)
    return _make_gif(frames, duration=65)


def _animated_arena(display_name, uid_str, data):
    a = data.get("arena") or {}
    rating = a.get("rating", 0)
    wins = a.get("wins", 0)
    losses = a.get("losses", 0)
    streak = a.get("streak", 0)
    crowns = a.get("crowns", 0)
    tokens = a.get("tokens", 0)
    undefeated = wins > 0 and losses == 0
    accent = (255, 210, 110)
    avatar = data["avatar"]
    right = [f"RATING {rating}", f"W {wins}  L {losses}", f"STREAK {streak}", f"CROWNS {crowns}", f"TOKENS {tokens}"]
    uid_int = int(uid_str or 0)
    frames = []
    for i in range(24):
        base = _core_card(display_name, uid_str, accent, "ARENA CHAMPION", right, avatar, (16, 14, 10, 255), (26, 20, 14, 255), glass_alpha=14)
        band_x = int((i / 24) * 900) - 90
        base = Image.alpha_composite(base, _shimmer_band(base.size, band_x, width=140, alpha=48))
        if streak > 0:
            p = _pulse(i, speed=0.25, lo=12, hi=44)
            flame = Image.new("RGBA", base.size, (255, 140, 40, p))
            base = Image.alpha_composite(base, flame)
        if undefeated:
            banner = Image.new("RGBA", base.size, (0, 0, 0, 0))
            bdraw = ImageDraw.Draw(banner)
            bdraw.rounded_rectangle((220, 250, 470, 286), radius=12, fill=(20, 20, 24, 190), outline=(255, 255, 255, 40))
            bdraw.text((236, 258), "UNDEFEATED", fill=(255, 230, 150, 255), font=_fonts()[2])
            base = Image.alpha_composite(base, banner)
        base.alpha_composite(_scanlines(base.size, i, alpha=18, step=6))
        base.alpha_composite(_noise(base.size, seed=(uid_int + 2222) * (i + 5), amount=12))
        frames.append(base)
    return _make_gif(frames, duration=60)


def _animated_hacker(display_name, uid_str, data):
    h = data.get("hacker") or {}
    tier = h.get("tier", 0)
    skill = h.get("skill", 0)
    xp = h.get("xp", 0)
    rep = h.get("reputation", 0)
    trace = h.get("trace", 0)
    chaos = float(h.get("chaos_affinity", 0))
    style = (h.get("style_vector") or {})
    dominant = max(style, key=style.get).upper() if style else "UNKNOWN"
    style_colors = {"AGGRESSIVE": (255, 90, 90), "STEALTHY": (170, 120, 255), "BRUTEFORCE": (255, 70, 70), "ELEGANT": (120, 220, 255), "EXPERIMENTAL": (0, 255, 200)}
    accent = style_colors.get(dominant, (120, 220, 255))
    avatar = data["avatar"]
    right = [f"TIER {tier}", f"SKILL {skill}", f"XP {xp}", f"REP {rep}", f"TRACE {trace}", f"CHAOS {int(chaos)}%", dominant]
    base_strength = int(clamp(chaos / 8, 2, 16))
    slice_count = int(clamp(chaos / 10, 4, 10))
    warn = trace >= 10
    uid_int = int(uid_str or 0)
    frames = []
    for i in range(24):
        base = _core_card(display_name, uid_str, accent, "HACKER PROFILE", right, avatar, (10, 10, 14, 255), (18, 16, 22, 255), glass_alpha=10)
        base.alpha_composite(_scanlines(base.size, i * 2, alpha=34, step=4))
        base.alpha_composite(_noise(base.size, seed=(uid_int + 7777) * (i + 7), amount=26))
        strength = base_strength + (2 if (i % 6 == 0) else 0)
        base = _glitch_slices(base, seed=(uid_int ^ (i * 12345)) + 99, strength=strength, slices=slice_count)
        if warn:
            p = _pulse(i, speed=0.6, lo=10, hi=85)
            overlay = Image.new("RGBA", base.size, (255, 40, 40, p))
            base = Image.alpha_composite(base, overlay)
            banner = Image.new("RGBA", base.size, (0, 0, 0, 0))
            bdraw = ImageDraw.Draw(banner)
            bdraw.rounded_rectangle((220, 250, 500, 286), radius=12, fill=(0, 0, 0, 200), outline=(255, 80, 80, 110))
            bdraw.text((236, 258), "TRACE ACTIVE", fill=(255, 120, 120, 255), font=_fonts()[2])
            base = Image.alpha_composite(base, banner)
        frames.append(base)
    return _make_gif(frames, duration=55)


def _animated_void(display_name, uid_str, data):
    world = data.get("world") or {}
    d = data.get("dungeon") or {}
    v = data.get("voidmaze") or {}
    corruption = float(world.get("corruption", 0.0))
    rift_level = int(world.get("rift_level", 0) or 0)
    instability = float(world.get("rift_instability", 0.0))
    depth = int(d.get("rift_depth", 0) or v.get("depth", 0) or 0)
    clarity = int(v.get("clarity", 0) or 0)
    chaos = float((data.get("hacker") or {}).get("chaos_affinity", 0) or 0)
    accent = (140, 200, 255)
    avatar = data["avatar"]
    right = [f"RIFT LVL {rift_level}", f"DEPTH {depth}", f"CORR {corruption:.2f}", f"INST {instability:.2f}"]
    if clarity:
        right.append(f"CLARITY {clarity}")
    seed_base = (int(uid_str or 0) * 99991) ^ 0xA5A5A5
    uid_int = int(uid_str or 0)
    frames = []
    for i in range(26):
        base = _core_card(display_name, uid_str, accent, "VOID-TOUCHED", right, avatar, (10, 12, 16, 255), (14, 16, 22, 255), glass_alpha=10)
        base = ImageEnhance.Color(base).enhance(0.62)
        base = ImageEnhance.Contrast(base).enhance(1.08)
        n = _noise(base.size, seed=seed_base + i * 13, amount=int(14 + instability * 8))
        n = n.filter(ImageFilter.GaussianBlur(0.8))
        base.alpha_composite(n)
        p = _pulse(i, speed=0.14, lo=10, hi=55)
        tint = Image.new("RGBA", base.size, (40, 120, 255, int(p * clamp((corruption + 1) / 6, 0, 1))))
        base = Image.alpha_composite(base, tint)
        base = Image.alpha_composite(base, _vignette(base.size, strength=0.62))
        base.alpha_composite(_scanlines(base.size, i, alpha=14, step=7))
        drift = int(2 * math.sin(i * 0.35))
        base = ImageChops.offset(base, drift, 0)
        if chaos >= 30:
            base = _glitch_slices(base, seed=seed_base + i * 999, strength=int(clamp(chaos / 18, 2, 8)), slices=5)
        frames.append(base)
    return _make_gif(frames, duration=75)


async def _get_avatar(uid: str, client) -> Image.Image:
    try:
        info = await client.users_info(user=uid)
        profile = info["user"]["profile"]
        avatar_url = profile.get("image_192") or profile.get("image_72") or ""
        if avatar_url:
            async with aiohttp.ClientSession() as s:
                async with s.get(avatar_url) as resp:
                    buf = BytesIO(await resp.read())
                    return Image.open(buf).convert("RGBA")
    except Exception:
        pass
    img = Image.new("RGBA", (192, 192), (80, 80, 100, 255))
    return img


async def render(uid: str, display_name: str, badge: str, client) -> BytesIO:
    state = load_state()
    u = state["users"].get(str(uid), {})
    avatar = await _get_avatar(uid, client)
    data = {
        "avatar": avatar,
        "balance": u.get("balance", 0),
        "dungeon": u.get("dungeon"),
        "arena": u.get("arena"),
        "voidmaze": u.get("voidmaze"),
        "hacker": state.get("hacker_profiles", {}).get(str(uid)),
        "world": state.get("world", {}),
    }
    loop = asyncio.get_running_loop()
    if badge == "dungeon":
        return await loop.run_in_executor(None, _animated_dungeon, display_name, uid, data)
    if badge == "arena":
        return await loop.run_in_executor(None, _animated_arena, display_name, uid, data)
    if badge == "hacker":
        return await loop.run_in_executor(None, _animated_hacker, display_name, uid, data)
    if badge == "void":
        return await loop.run_in_executor(None, _animated_void, display_name, uid, data)
    return await loop.run_in_executor(None, _animated_identity, display_name, uid, data)


async def setup(app):
    @app.command("/badge")
    async def badge_cmd(ack, command, client, respond):
        await ack()
        uid = command["user_id"]
        state = load_state()
        u = state["users"].get(str(uid), {})
        available = ["identity"]
        if "dungeon" in u:
            available.append("dungeon")
        if "arena" in u:
            available.append("arena")
        if str(uid) in state.get("hacker_profiles", {}):
            available.append("hacker")
        d = u.get("dungeon", {}) or {}
        v = u.get("voidmaze", {}) or {}
        h = state.get("hacker_profiles", {}).get(str(uid), {}) or {}
        if int(d.get("rift_depth", 0) or 0) >= 20 or int(v.get("depth", 0) or 0) >= 10 or float(h.get("chaos_affinity", 0) or 0) >= 30:
            available.append("void")

        options = [{"text": {"type": "plain_text", "text": b.title()}, "value": b} for b in available]
        blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": "Select Badge", "emoji": True}},
            {"type": "actions", "elements": [
                {"type": "static_select", "placeholder": {"type": "plain_text", "text": "Pick a badge"}, "action_id": "badge_select", "options": options},
            ]},
        ]
        await respond(blocks=blocks, text="Select your badge", response_type="ephemeral")

    @app.action("badge_select")
    async def badge_select(ack, body, client):
        await ack()
        uid = body["user"]["id"]
        badge = body["actions"][0]["selected_option"]["value"]
        try:
            info = await client.users_info(user=uid)
            display_name = info["user"]["profile"].get("display_name") or info["user"]["name"]
        except Exception:
            display_name = uid

        channel = body["container"].get("channel_id") or body.get("channel", {}).get("id")
        if not channel:
            return
        try:
            buf = await render(uid, display_name, badge, client)
            await client.files_upload_v2(channel=channel, file=buf, filename="badge.gif")
        except Exception as e:
            await client.chat_postEphemeral(channel=channel, user=uid, text=f"Badge render failed: {e}")
