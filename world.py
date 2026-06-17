import datetime

from economy import get_user
from economy_shared import state, save_state


def auction_root():
    return state.setdefault("auction_house_v1", {"next_id": 1, "listings": []})


def clean_listings():
    root = auction_root(); now = datetime.datetime.utcnow(); kept = []
    for listing in root.get("listings", []):
        dt = None
        try:
            dt = datetime.datetime.fromisoformat(listing.get("expires_at", "")) if listing.get("expires_at") else None
        except Exception:
            dt = None
        if dt and dt <= now:
            seller = get_user(str(listing["seller_id"]))
            inventory = seller.setdefault("inventory", {})
            inventory[listing["item_name"]] = int(inventory.get(listing["item_name"], 0) or 0) + int(listing["amount"])
        else:
            kept.append(listing)
    root["listings"] = kept; save_state()


def find_listing(listing_id: int):
    for listing in auction_root().get("listings", []):
        if int(listing.get("id", 0)) == int(listing_id):
            return listing
    return None


async def setup(app):

    @app.command("/fus_auction")
    async def auction_cmd(ack, command, client):
        await ack()
        uid = command["user_id"]; channel = command["channel_id"]
        parts = (command.get("text") or "").strip().split(None, 1)
        action = parts[0].lower() if parts else "browse"
        arg = parts[1].strip() if len(parts) > 1 else ""

        if action == "sell":
            sub = arg.split()
            if len(sub) < 3:
                await client.chat_postEphemeral(channel=channel, user=uid, text="usage: `/fus_auction sell <item> <amount> <price_each>`"); return
            item_name = sub[0]
            try:
                amount = int(sub[1]); price_each = int(sub[2])
                if amount < 1 or price_each < 1: raise ValueError
            except ValueError:
                await client.chat_postEphemeral(channel=channel, user=uid, text="amount and price_each must be positive integers"); return
            clean_listings(); data = get_user(uid); inventory = data.setdefault("inventory", {})
            have = int(inventory.get(item_name, 0) or 0)
            if amount > have:
                await client.chat_postEphemeral(channel=channel, user=uid, text="you dont have that many of that item"); return
            inventory[item_name] = have - amount
            if inventory[item_name] <= 0:
                inventory.pop(item_name, None)
            root = auction_root(); listing = {
                "id": root["next_id"], "seller_id": uid, "item_name": item_name, "amount": amount, "price_each": price_each,
                "created_at": datetime.datetime.utcnow().isoformat(),
                "expires_at": (datetime.datetime.utcnow() + datetime.timedelta(days=2)).isoformat(),
            }
            root["next_id"] += 1; root["listings"].append(listing); save_state()
            await client.chat_postMessage(channel=channel, text=f"listed `{amount}x {item_name}` for `{price_each}` each as listing `{listing['id']}`")

        elif action in ("browse", ""):
            clean_listings()
            all_listings = auction_root().get("listings", []); listings = all_listings[:20]
            if not listings:
                msg = ":shopping_trolley: *Auction House*\nnothing is up right now"
            else:
                lines = []
                for listing in listings:
                    total = int(listing["amount"]) * int(listing["price_each"])
                    lines.append(f"`{listing['id']}` *{listing['item_name']}* x{listing['amount']} • `{listing['price_each']}` each • total `{total}`")
                msg = (
                    f":shopping_trolley: *Auction House* — {len(all_listings)} active listing(s)\n\n"
                    + "\n".join(lines)
                    + "\n\n_use `/fus_auction buy <id>` to buy or `/fus_auction cancel <id>` to cancel your own listing_"
                )
            await client.chat_postMessage(channel=channel, text=msg[:3000])

        elif action == "buy":
            try:
                listing_id = int(arg)
            except ValueError:
                await client.chat_postEphemeral(channel=channel, user=uid, text="usage: `/fus_auction buy <listing_id>`"); return
            clean_listings(); listing = find_listing(listing_id)
            if not listing:
                await client.chat_postEphemeral(channel=channel, user=uid, text="that listing doesnt exist"); return
            if str(listing["seller_id"]) == str(uid):
                await client.chat_postEphemeral(channel=channel, user=uid, text="you cant buy your own listing"); return
            total = int(listing["amount"]) * int(listing["price_each"])
            buyer = get_user(uid); seller = get_user(str(listing["seller_id"]))
            if int(buyer.get("balance", 0) or 0) < total:
                await client.chat_postEphemeral(channel=channel, user=uid, text="not enough horsenncy"); return
            buyer["balance"] = int(buyer.get("balance", 0) or 0) - total
            seller["balance"] = int(seller.get("balance", 0) or 0) + total
            inventory = buyer.setdefault("inventory", {})
            inventory[listing["item_name"]] = int(inventory.get(listing["item_name"], 0) or 0) + int(listing["amount"])
            auction_root()["listings"] = [x for x in auction_root().get("listings", []) if int(x.get("id", 0)) != listing_id]
            save_state()
            await client.chat_postMessage(channel=channel, text=f"bought `{listing['amount']}x {listing['item_name']}` for `{total}` horsenncy from <@{listing['seller_id']}>")

        elif action == "cancel":
            try:
                listing_id = int(arg)
            except ValueError:
                await client.chat_postEphemeral(channel=channel, user=uid, text="usage: `/fus_auction cancel <listing_id>`"); return
            clean_listings(); listing = find_listing(listing_id)
            if not listing:
                await client.chat_postEphemeral(channel=channel, user=uid, text="that listing doesnt exist"); return
            if str(listing["seller_id"]) != str(uid):
                await client.chat_postEphemeral(channel=channel, user=uid, text="thats not your listing"); return
            data = get_user(uid); inventory = data.setdefault("inventory", {})
            inventory[listing["item_name"]] = int(inventory.get(listing["item_name"], 0) or 0) + int(listing["amount"])
            auction_root()["listings"] = [x for x in auction_root().get("listings", []) if int(x.get("id", 0)) != listing_id]
            save_state()
            await client.chat_postMessage(channel=channel, text=f"listing `{listing_id}` canceled and items returned")

        else:
            await client.chat_postEphemeral(channel=channel, user=uid, text="actions: `sell <item> <amount> <price>` | `browse` | `buy <id>` | `cancel <id>`")
