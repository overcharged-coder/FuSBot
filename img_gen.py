import os
import io
import base64
import logging
import json
import aiohttp

log = logging.getLogger("imagegen")

REPLICATE_KEY = os.getenv("REPLICATE_API_TOKEN")
STABILITY_KEY = os.getenv("STABILITY_API_KEY")
SDXL_VERSION_ID: str | None = None


async def get_latest_version_id(owner: str, model: str) -> str | None:
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"https://api.replicate.com/v1/models/{owner}/{model}",
            headers={"Authorization": f"Bearer {REPLICATE_KEY}"},
            timeout=20,
        ) as r:
            if r.status != 200:
                return None
            data = await r.json()
            latest = data.get("latest_version") or {}
            return latest.get("id")


async def _gen_replicate(prompt: str):
    if not REPLICATE_KEY or not SDXL_VERSION_ID:
        return None
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://api.replicate.com/v1/predictions",
            headers={
                "Authorization": f"Bearer {REPLICATE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "wait=60",
            },
            json={"version": SDXL_VERSION_ID, "input": {"prompt": prompt, "width": 1024, "height": 1024}},
            timeout=90,
        ) as r:
            if r.status != 201:
                return None
            data = json.loads(await r.text())
            output = data.get("output")
            if not output:
                return None
            image_url = output[0]
    async with aiohttp.ClientSession() as session:
        async with session.get(image_url) as r:
            return await r.read()


async def _gen_stability(prompt: str):
    if not STABILITY_KEY:
        return None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image",
                headers={"Authorization": f"Bearer {STABILITY_KEY}", "Content-Type": "application/json"},
                json={"text_prompts": [{"text": prompt}], "width": 1024, "height": 1024, "samples": 1},
                timeout=30,
            ) as r:
                if r.status != 200:
                    return None
                data = await r.json()
                return base64.b64decode(data["artifacts"][0]["base64"])
    except Exception as e:
        log.error("Stability failed: %s", e)
        return None


IMAGE_PROVIDERS = [_gen_stability, _gen_replicate]


async def generate_image(prompt: str):
    for provider in IMAGE_PROVIDERS:
        img = await provider(prompt)
        if img:
            return img
    return None


async def setup(app):
    global SDXL_VERSION_ID
    SDXL_VERSION_ID = await get_latest_version_id("stability-ai", "sdxl")

    @app.command("/img")
    async def img_cmd(ack, command, client, respond):
        await ack()
        prompt = (command.get("text") or "").strip()
        if not prompt:
            return await respond(text="Usage: `/img <prompt>`", response_type="ephemeral")
        uid = command["user_id"]
        channel = command["channel_id"]
        await respond(text=f":hourglass: Generating image for *{prompt}*...")
        img_bytes = await generate_image(prompt)
        if not img_bytes:
            return await client.chat_postMessage(channel=channel, text=":x: Image generation failed.")
        buf = io.BytesIO(img_bytes)
        await client.files_upload_v2(channel=channel, file=buf, filename="image.png", initial_comment=f":frame_with_picture: *{prompt}*")
