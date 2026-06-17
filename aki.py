import logging
import asyncio
import akinator

log = logging.getLogger("aki")

ANSWER_MAP = {"yes": "y", "no": "n", "idk": "i", "probably": "p", "probably_not": "pn"}

_games: dict[str, akinator.AsyncAkinator] = {}


def _aki_blocks(uid: str, question: str) -> list[dict]:
    return [
        {"type": "section", "text": {"type": "mrkdwn", "text": f":brain: *Akinator*\n{question}"}},
        {"type": "actions", "elements": [
            {"type": "button", "text": {"type": "plain_text", "text": "Yes"}, "action_id": "aki_yes", "style": "primary", "value": uid},
            {"type": "button", "text": {"type": "plain_text", "text": "No"}, "action_id": "aki_no", "style": "danger", "value": uid},
            {"type": "button", "text": {"type": "plain_text", "text": "I don't know"}, "action_id": "aki_idk", "value": uid},
            {"type": "button", "text": {"type": "plain_text", "text": "Probably"}, "action_id": "aki_prob", "value": uid},
            {"type": "button", "text": {"type": "plain_text", "text": "Probably not"}, "action_id": "aki_probn", "value": uid},
        ]},
    ]


async def _handle_answer(body, client, answer: str):
    uid = body["actions"][0]["value"]
    actor = body["user"]["id"]
    if actor != uid:
        return
    game = _games.get(uid)
    if not game:
        return
    channel = body["container"]["channel_id"]
    ts = body["container"]["message_ts"]
    try:
        await game.answer(answer)
    except Exception:
        log.exception("Akinator answer failed")
        _games.pop(uid, None)
        await client.chat_update(channel=channel, ts=ts, text=":x: Game ended due to an error.", blocks=[])
        return

    if game.finished:
        _games.pop(uid, None)
        name = game.name_proposition
        desc = game.description_proposition or ""
        photo = game.photo or ""
        blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": f":dart: *I guess...*\n*{name}*\n{desc}"}}]
        if photo:
            blocks.append({"type": "image", "image_url": photo, "alt_text": name})
        await client.chat_update(channel=channel, ts=ts, blocks=blocks, text=f"Akinator: {name}")
    else:
        blocks = _aki_blocks(uid, str(game))
        await client.chat_update(channel=channel, ts=ts, blocks=blocks, text="Akinator")


async def setup(app):

    @app.command("/fus_aki")
    async def aki_cmd(ack, command, client):
        await ack()
        uid = command["user_id"]
        channel = command["channel_id"]
        game = akinator.AsyncAkinator()
        try:
            await game.start_game()
        except Exception:
            log.exception("Akinator start_game failed")
            await client.chat_postEphemeral(channel=channel, user=uid, text=":x: Failed to start Akinator.")
            return
        _games[uid] = game
        blocks = _aki_blocks(uid, str(game))
        await client.chat_postMessage(channel=channel, blocks=blocks, text="Akinator")

    @app.action("aki_yes")
    async def aki_yes(ack, body, client):
        await ack()
        await _handle_answer(body, client, ANSWER_MAP["yes"])

    @app.action("aki_no")
    async def aki_no(ack, body, client):
        await ack()
        await _handle_answer(body, client, ANSWER_MAP["no"])

    @app.action("aki_idk")
    async def aki_idk(ack, body, client):
        await ack()
        await _handle_answer(body, client, ANSWER_MAP["idk"])

    @app.action("aki_prob")
    async def aki_prob(ack, body, client):
        await ack()
        await _handle_answer(body, client, ANSWER_MAP["probably"])

    @app.action("aki_probn")
    async def aki_probn(ack, body, client):
        await ack()
        await _handle_answer(body, client, ANSWER_MAP["probably_not"])
