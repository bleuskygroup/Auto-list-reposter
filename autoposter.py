from atproto import Client
import os
import time
from datetime import datetime, timedelta

# ─── Instellingen ───────────────────────────────────────────────
LIST_URI = "at://did:plc:jaka644beit3x4vmmg6yysw7/app.bsky.graph.list/3m3iga6wnmz2p"
EXEMPT_HANDLE = "bleuskybeauty.bsky.social"
MAX_PER_USER = 5
MAX_TOTAL = 25
DAYS_BACK = 7
# ────────────────────────────────────────────────────────────────

def log(msg: str):
    """Compacte log met tijd"""
    now = datetime.utcnow().strftime("%H:%M:%S")
    print(f"[{now}] {msg}")

def main():
    username = os.environ["BSKY_USERNAME"]
    password = os.environ["BSKY_PASSWORD"]

    client = Client()
    client.login(username, password)
    log(f"✅ Ingelogd als {username}")

    # Ledenlijst ophalen
    try:
        members = client.app.bsky.graph.get_list({"list": LIST_URI}).items
        log(f"📋 {len(members)} gebruikers gevonden.")
    except Exception as e:
        log(f"⚠️ Lijstfout: {e}")
        return

    # Repostlog bijhouden
    repost_log = "reposted.txt"
    if os.path.exists(repost_log):
        with open(repost_log, "r") as f:
            done = set(f.read().splitlines())
    else:
        done = set()

    all_posts = []
    cutoff_time = datetime.utcnow() - timedelta(days=DAYS_BACK)

    # Feeds ophalen
    for m in members:
        handle = m.subject.handle
        try:
            feed = client.app.bsky.feed.get_author_feed({"actor": handle, "limit": 10})
            for post in feed.feed:
                record = getattr(post.post, "record", None)
                uri = post.post.uri
                cid = post.post.cid
                if getattr(post, "reason", None):  # repost
                    continue
                if getattr(record, "reply", None):  # reply
                    continue
                indexed_at = getattr(post.post, "indexed_at", None)
                if not indexed_at:
                    continue
                created_at = datetime.fromisoformat(indexed_at.replace("Z", "+00:00"))
                if created_at < cutoff_time:
                    continue
                if uri in done:
                    continue
                all_posts.append({
                    "handle": handle,
                    "uri": uri,
                    "cid": cid,
                    "created_at": created_at
                })
        except Exception:
            continue

    if not all_posts:
        log("🚫 Geen nieuwe posts gevonden.")
        return

    # Sorteren: nieuwste eerst
    all_posts.sort(key=lambda p: p["created_at"], reverse=True)

    reposts = 0
    likes = 0
    per_user = {}

    for post in all_posts:
        if reposts >= MAX_TOTAL:
            log("🔢 Max 25 reposts bereikt, stop.")
            break

        handle = post["handle"]
        if handle != EXEMPT_HANDLE:
            per_user.setdefault(handle, 0)
            if per_user[handle] >= MAX_PER_USER:
                continue

        uri, cid = post["uri"], post["cid"]

        try:
            client.app.bsky.feed.repost.create(
                repo=client.me.did,
                record={
                    "subject": {"uri": uri, "cid": cid},
                    "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                }
            )
            reposts += 1
            per_user[handle] = per_user.get(handle, 0) + 1
            done.add(uri)
            log(f"🔁 @{handle}")
            time.sleep(1)

            # Like direct na repost
            client.app.bsky.feed.like.create(
                repo=client.me.did,
                record={
                    "subject": {"uri": uri, "cid": cid},
                    "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                }
            )
            likes += 1
            time.sleep(0.5)

        except Exception:
            continue

    # Repostlog opslaan
    with open(repost_log, "w") as f:
        f.write("\n".join(done))

    log(f"✅ Klaar ({reposts} reposts, {likes} likes)")

if __name__ == "__main__":
    main()