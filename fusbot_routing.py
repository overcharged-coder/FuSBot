import re
from dataclasses import dataclass


_MENTION_RE = re.compile(r"<@([A-Z0-9]+)(?:\|[^>]*)?>")
_ROAST_COMMAND_RE = re.compile(
    r"^\s*(please\s+)?(roast|cook|flame|destroy|smoke|pack|clown|violate)\b\s*",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class RoastRequest:
    target_user_ids: list[str]
    prompt: str


def parse_slack_mentions(text: str) -> list[str]:
    return _MENTION_RE.findall(text or "")


def strip_slack_mentions(text: str) -> str:
    text = _MENTION_RE.sub("", text or "")
    return re.sub(r"\s+", " ", text).strip()



def _clean_roast_context(text: str) -> str:
    context = strip_slack_mentions(text)
    context = re.sub(r"\bfusbot\b", "", context, flags=re.IGNORECASE)
    context = re.sub(r"\s+", " ", context).strip()
    while True:
        cleaned = _ROAST_COMMAND_RE.sub("", context).strip()
        if cleaned == context:
            break
        context = cleaned
    return context


def build_roast_request(text: str, teller_user_id: str, bot_user_id: str = "") -> RoastRequest:
    target_ids = [
        uid for uid in parse_slack_mentions(text)
        if uid and uid != bot_user_id
    ]
    if not target_ids:
        target_ids = [teller_user_id]

    clean_prompt = _clean_roast_context(text)
    target_list = ", ".join(f"<@{uid}>" for uid in target_ids)
    target_guard = "Write one short roast addressed only to this target. Do not joke about the instruction, prompt, or roast quality."
    if clean_prompt:
        prompt = f"Target to roast: {target_list}. {target_guard} Target detail: {clean_prompt}"
    else:
        prompt = f"Target to roast: {target_list}. {target_guard}"
    return RoastRequest(target_user_ids=target_ids, prompt=prompt)


def allowed_in_workspace_channel(
    team_id: str,
    enterprise_id: str,
    channel_id: str,
    allowed_workspace_id: str,
    allowed_channel_id: str,
) -> bool:
    if not allowed_workspace_id or not allowed_channel_id:
        return True
    in_workspace = enterprise_id == allowed_workspace_id or team_id == allowed_workspace_id
    return not in_workspace or channel_id == allowed_channel_id
