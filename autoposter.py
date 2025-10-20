from atproto import Client
import os
import time
from datetime import datetime, timedelta, timezone

# 🔗 Bluesky-feed (feed generator, geen lijst)
FEED_URI = "at://did:plc:jaka644beit3x4vmmg6yysw7/app.bsky.feed.generator/aaaprg6dqhaii"

# Gebruiker zonder repostlimiet (optioneel)
EXEMPT_HANDLE = "bleuskybeauty.bsky.social"

# Config
MAX_PER_RUN = 50
MAX_PER_USER = 5
HOURS_BACK = 2  # laatste 2 uur

def log(msg: str):
    now = datetime.now(timezone.utc).strftime("[%H:%M:%S]")
    print(f"{now} {msg}")

def parse_time(record, post):
    for attr in ["createdAt", "indexedAt", "created_at", "timestamp"]:
        val = getattr(record, attr, None) or getattr(post, attr, None)
        if val:
            try:
                return datetime.fromisoformat(val.replace("Z", "+00:00"))
            except Exception:
                continue
    return None

def main():
    username = os.environ["BSKY_USERNAME"]
    password = os.environ["BSKY_PASSWORD"]

    client = Client()
    client.login(username, password)
    log(f"✅ Ingelogd als {username}")
    log("🔎 Ophalen feed...")

    try:
        feed = client.app.bsky.feed.get_feed({"feed": FEED_URI, "limit": 100})
    except Exception as e:
        log(f"⚠️ Fout bij ophalen feed: {e}")
        return

    items = feed.feed
    log(f"🕒 {len(items)} posts opgehaald.")

    repost_log = "reposted.txt"
    done = set()
    if os.path.exists(repost_log):
        with open(repost_log, "r") as f:
            done = set(f.read().splitlines())

    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=HOURS_BACK)

    posts = []
    for item in items:
        post = item.post
        record = post.record
        uri = post.uri
        cid = post.cid
        handle = post.author.handle

        # Skip reposts/replies
        if hasattr(item, "reason") and item.reason is not None:
            continue
        if getattr(record, "reply", None):
            continue
        if uri in done:
            continue

        created = parse_time(record, post)
        if not created:
            continue
        if created < cutoff_time:
            continue

        posts.append({
            "handle": handle,
            "uri": uri,
            "cid": cid,
            "created": created,
        })

    posts.sort(key=lambda x: x["created"])
    log(f"📊 {len(posts)} posts worden verwerkt (max {MAX_PER_RUN}).")

    reposted = 0
    liked = 0
    per_user = {}

    for p in posts[:MAX_PER_RUN]:
        if reposted >= MAX_PER_RUN:
            break

        handle, uri, cid = p["handle"], p["uri"], p["cid"]
        if handle != EXEMPT_HANDLE:
            per_user[handle] = per_user.get(handle, 0)
            if per_user[handle] >= MAX_PER_USER:
                continue

        try:
            client.app.bsky.feed.repost.create(
                repo=client.me.did,
                record={
                    "subject": {"uri": uri, "cid": cid},
                    "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )
            log(f"🔁 Gerepost @{handle}: {uri}")
            reposted += 1
            per_user[handle] = per_user.get(handle, 0) + 1
            done.add(uri)
            # direct opslaan om dubbel te vermijden
            with open(repost_log, "a") as f:
                f.write(uri + "\n")

            time.sleep(2)

            try:
                client.app.bsky.feed.like.create(
                    repo=client.me.did,
                    record={
                        "subject": {"uri": uri, "cid": cid},
                        "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    },
                )
                log(f"❤️ Geliked @{handle}")
                liked += 1
                time.sleep(1)
            except Exception as e:
                log(f"⚠️ Fout bij liken @{handle}: {e}")

        except Exception as e:
            log(f"⚠️ Fout bij repost @{handle}: {e}")

    log(f"✅ Klaar! ({reposted} reposts, {liked} likes)")
    log(f"🧮 Totaal bekeken: {len(items)}, nieuw gerepost: {reposted}")
    log(f"⏰ Run beëindigd om {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")

if __name__ == "__main__":
    main()