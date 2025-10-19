from atproto import Client
import os
import time
from datetime import datetime

LIST_URI = "at://did:plc:jaka644beit3x4vmmg6yysw7/app.bsky.graph.list/3m3iga6wnmz2p"
EXEMPT_HANDLE = "bleuskybeauty.bsky.social"

def log(msg: str):
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{now}] {msg}")

def extract_created_at(post):
    """Probeer het tijdveld uit verschillende mogelijke locaties te halen (inclusief dict-records)."""
    record = getattr(post.post, "record", None)
    possible_fields = []

    # record kan object of dict zijn
    if record:
        if isinstance(record, dict):
            possible_fields.extend([
                record.get("createdAt"),
                record.get("indexedAt"),
                record.get("_created_at")
            ])
        else:
            possible_fields.extend([
                getattr(record, "createdAt", None),
                getattr(record, "indexedAt", None),
                getattr(record, "_created_at", None)
            ])

    possible_fields.extend([
        getattr(post.post, "createdAt", None),
        getattr(post.post, "indexedAt", None),
        getattr(post, "indexedAt", None),
        getattr(post.post, "_created_at", None)
    ])

    for field in possible_fields:
        if field:
            return field
    return None


def main():
    username = os.environ["BSKY_USERNAME"]
    password = os.environ["BSKY_PASSWORD"]

    client = Client()
    client.login(username, password)
    log(f"✅ Ingelogd als: {username}")

    try:
        members = client.app.bsky.graph.get_list({"list": LIST_URI}).items
        log(f"📋 {len(members)} gebruikers in lijst gevonden.")
    except Exception as e:
        log(f"⚠️ Fout bij ophalen lijst: {e}")
        return

    repost_log = "reposted.txt"
    if os.path.exists(repost_log):
        with open(repost_log, "r") as f:
            done = set(f.read().splitlines())
    else:
        done = set()

    posts_to_check = []

    for member in members:
        handle = member.subject.handle
        try:
            feed = client.app.bsky.feed.get_author_feed({"actor": handle, "limit": 5})
            if not feed.feed:
                log(f"ℹ️ Geen posts gevonden voor @{handle}")

            for post in feed.feed:
                created_at = extract_created_at(post)
                if not created_at:
                    log(f"⚠️ Geen tijdveld gevonden voor @{handle}, skip.")
                    continue

                posts_to_check.append({
                    "handle": handle,
                    "uri": post.post.uri,
                    "cid": post.post.cid,
                    "created_at": datetime.fromisoformat(created_at.replace('Z', '+00:00')),
                    "post": post
                })
        except Exception as e:
            log(f"⚠️ Fout bij ophalen feed @{handle}: {e}")

    log(f"🕒 {len(posts_to_check)} totale posts verzameld vóór filtering.")

    if not posts_to_check:
        log("🚫 Geen posts gevonden. Controleer of gebruikers recente originele posts hebben.")
        return

    posts_to_check.sort(key=lambda x: x["created_at"], reverse=True)

    total_reposts = 0
    total_likes = 0
    posted_this_run = set()
    user_counts = {}

    for entry in posts_to_check:
        handle = entry["handle"]
        uri = entry["uri"]
        cid = entry["cid"]
        post = entry["post"]

        if hasattr(post, "reason") and post.reason is not None:
            continue
        record = post.post.record
        if isinstance(record, dict) and "reply" in record:
            continue
        if not isinstance(record, dict) and getattr(record, "reply", None):
            continue

        embed = getattr(post.post, "embed", None)
        if embed and hasattr(embed, "record"):
            rec = getattr(embed, "record", None)
            if rec and hasattr(rec, "author") and rec.author.handle != handle:
                continue

        if uri in done or uri in posted_this_run:
            continue

        limit = 3 if handle != EXEMPT_HANDLE else float("inf")
        user_counts.setdefault(handle, 0)
        if user_counts[handle] >= limit:
            continue

        try:
            client.app.bsky.feed.repost.create(
                repo=client.me.did,
                record={
                    "subject": {"uri": uri, "cid": cid},
                    "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                }
            )
            log(f"🟦 Gerepost @{handle}: {uri}")
            done.add(uri)
            posted_this_run.add(uri)
            user_counts[handle] += 1
            total_reposts += 1
            time.sleep(2)

            try:
                client.app.bsky.feed.like.create(
                    repo=client.me.did,
                    record={
                        "subject": {"uri": uri, "cid": cid},
                        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    }
                )
                log(f"❤️ Geliked @{handle}: {uri}")
                total_likes += 1
                time.sleep(1)
            except Exception as e_like:
                log(f"⚠️ Fout bij liken @{handle}: {e_like}")

        except Exception as e:
            log(f"⚠️ Fout bij repost @{handle}: {e}")

    with open(repost_log, "w") as f:
        f.write("\n".join(done))

    log(f"📊 Samenvatting: {total_reposts} reposts en {total_likes} likes uitgevoerd.")
    log(f"⏰ Run beëindigd om {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")

if __name__ == "__main__":
    main()