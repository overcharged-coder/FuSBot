from economy import get_user

try:
    from achievement import build_snapshot
except Exception:
    build_snapshot = None


def rarity_counts(animals):
    counts = {}
    if not isinstance(animals, list):
        return counts
    for animal in animals:
        if isinstance(animal, dict):
            rarity = str(animal.get("rarity") or animal.get("tier") or "unknown").lower()
        else:
            rarity = "unknown"
        counts[rarity] = counts.get(rarity, 0) + 1
    return counts


def compact_dict_lines(d: dict, limit: int = 12):
    if not d:
        return "none"
    items = sorted(d.items(), key=lambda x: (-x[1], x[0]))[:limit]
    return "\n".join(f"• {k}: `{v}`" for k, v in items)


async def setup(app):
    pass
