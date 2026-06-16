import re

EMOJI_TO_SLACK = {
    "😂": "joy", "😭": "sob", "💀": "skull", "🤣": "rofl", "😹": "joy_cat",
    "👍": "+1", "👌": "ok_hand", "✅": "white_check_mark", "☑️": "ballot_box_with_check",
    "🫡": "saluting_face", "👀": "eyes", "🫣": "face_with_peeking_eye",
    "🧠": "brain", "📝": "memo", "🔥": "fire", "💯": "100", "🚀": "rocket",
    "🙌": "raised_hands", "✨": "sparkles", "😔": "pensive", "🫂": "people_hugging",
    "❤️": "heart", "😞": "disappointed", "🥲": "smiling_face_with_tear",
    "❓": "question", "🤔": "thinking_face", "🧐": "face_with_monocle",
    "💭": "thought_balloon", "🤝": "handshake", "🧢": "baseball",
    "😳": "flushed", "🤨": "raised_eyebrow", "😐": "neutral_face", "🙄": "roll_eyes",
    "💥": "boom", "⚡": "zap", "🌊": "ocean", "💎": "gem", "🏆": "trophy",
    "⚔️": "crossed_swords", "🛡️": "shield", "🎲": "game_die", "🎯": "dart",
    "🔮": "crystal_ball", "📊": "bar_chart", "🧪": "test_tube", "💉": "syringe",
    "🌀": "dizzy", "🕳️": "hole", "✴️": "eight_pointed_black_star",
    "🏳️": "white_flag", "🔥": "fire", "💀": "skull", "⚠️": "warning",
    "🛑": "octagonal_sign", "📌": "pushpin", "🔒": "lock", "🔓": "unlock",
    "🎰": "slot_machine", "🃏": "black_joker", "🎴": "flower_playing_cards",
    "🐾": "paw_prints", "🌿": "herb", "🦌": "deer", "🐟": "fish",
    "💤": "zzz", "👋": "wave",
}


def unicode_to_slack_emoji(emoji: str) -> str:
    return EMOJI_TO_SLACK.get(emoji, "+1")


def slack_mention(user_id: str) -> str:
    return f"<@{user_id}>"


def parse_slack_mentions(text: str) -> list[str]:
    return re.findall(r"<@([A-Z0-9]+)>", text or "")


def strip_slack_mentions(text: str) -> str:
    text = re.sub(r"<@[A-Z0-9]+>", "", text or "")
    return re.sub(r"\s+", " ", text).strip()


def header_block(text: str) -> dict:
    return {"type": "header", "text": {"type": "plain_text", "text": text[:150], "emoji": True}}


def section_block(text: str) -> dict:
    return {"type": "section", "text": {"type": "mrkdwn", "text": text[:3000]}}


def fields_block(fields: list[tuple[str, str]]) -> dict:
    return {
        "type": "section",
        "fields": [
            {"type": "mrkdwn", "text": f"*{name}*\n{val}"[:2000]}
            for name, val in fields[:10]
        ]
    }


def divider_block() -> dict:
    return {"type": "divider"}


def button_block(buttons: list[dict]) -> dict:
    elements = []
    for btn in buttons[:5]:
        elem = {
            "type": "button",
            "text": {"type": "plain_text", "text": btn["label"][:75], "emoji": True},
            "action_id": btn["action_id"],
            "value": str(btn.get("value", ""))[:2000],
        }
        if "style" in btn:
            elem["style"] = btn["style"]
        elements.append(elem)
    return {"type": "actions", "elements": elements}


def make_blocks(title: str, description: str = "", fields: list[tuple[str, str]] = None, buttons: list[dict] = None) -> list[dict]:
    blocks = []
    if title:
        blocks.append(header_block(title))
    if description:
        blocks.append(section_block(description))
    if fields:
        for i in range(0, len(fields), 10):
            blocks.append(fields_block(fields[i:i+10]))
    if buttons:
        blocks.append(divider_block())
        blocks.append(button_block(buttons))
    return blocks


def context_block(text: str) -> dict:
    return {"type": "context", "elements": [{"type": "mrkdwn", "text": text[:3000]}]}
