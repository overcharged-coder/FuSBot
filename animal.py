import aiohttp
import logging

log = logging.getLogger("animals")

ANIMAL_ENDPOINTS = {
    "cat": "https://some-random-api.com/animal/cat",
    "dog": "https://some-random-api.com/animal/dog",
    "fox": "https://some-random-api.com/animal/fox",
    "panda": "https://some-random-api.com/animal/panda",
    "red_panda": "https://some-random-api.com/animal/red_panda",
    "koala": "https://some-random-api.com/animal/koala",
    "bird": "https://some-random-api.com/animal/bird",
    "raccoon": "https://some-random-api.com/animal/raccoon",
    "kangaroo": "https://some-random-api.com/animal/kangaroo",
}

VALID_ANIMALS = sorted(ANIMAL_ENDPOINTS.keys())


async def _fetch_animal(animal: str) -> dict | None:
    url = ANIMAL_ENDPOINTS.get(animal)
    if not url:
        return None
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url) as resp:
                return await resp.json()
    except Exception:
        log.exception("Animal API failed")
        return None


async def setup(app):
    @app.command("/fus_animal")
    async def animal_cmd(ack, command, respond):
        await ack()
        text = (command.get("text") or "").strip().lower().replace(" ", "_")
        if text not in ANIMAL_ENDPOINTS:
            names = ", ".join(VALID_ANIMALS)
            await respond(text=f"Pick an animal: {names}", response_type="ephemeral")
            return

        data = await _fetch_animal(text)
        if not data:
            await respond(text="Failed to fetch animal.", response_type="ephemeral")
            return

        image = data.get("image", "")
        fact = data.get("fact", "")
        title = text.replace("_", " ").title()

        blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": title, "emoji": True}},
        ]
        if fact:
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": fact}})
        if image:
            blocks.append({"type": "image", "image_url": image, "alt_text": title})

        await respond(blocks=blocks, text=title)
