from atproto import Client
import os
import time
from datetime import datetime, timedelta, timezone

# Bluesky-feed die gerepost moet worden
FEED_URI = "at://did:plc:jaka644beit3x4vmmg6yysw7/app.bsky.feed.generator/aaaprg6dqhaii"

# Gebruiker zonder limiet
EXEMPT_HANDLE = "bleuskybeauty.bsky.social"

# Configuratie
MAX_PER_RUN = 50
MAX_PER_USER = 5
HOURS_BACK = 24  # laatste 24 uur

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

    repost_log = "reposted.txt"
    done = set()
    if os.path.exists(repost_log):
        with open(repost_log, "r") as f:
            done = set(f.read().splitlines())

    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=HOURS_BACK)
    all_posts = []

    log("🔎 Ophalen feed...")
    try:
        feed_data = client.app.bsky.feed.get_feed({"feed": FEED_URI, "limit": 100})
        for item in feed_data.feed:
            post = item.post
            record = post.record
            uri = post.uri
            cid = post.cid
            handle = post.author.handle

            if hasattr(item, "reason") and item.reason is not None:
                continue
            if getattr(record, "reply", None):
                continue
            if uri in done:
                continue

            created_dt = parse_time(record, post)
            if not created_dt or created_dt < cutoff_time:
                continue

            all_posts.append({
                "handle": handle,
                "uri": uri,
                "cid": cid,
                "created": created_dt,
            })
    except Exception as e:
        log(f"⚠️ Fout bij ophalen feed: {e}")
        return

    log(f"🕒 {len(all_posts)} posts opgehaald.")
    all_posts.sort(key=lambda x: x["created"])  # oudste eerst

    reposted = 0
    liked = 0
    per_user_count = {}
    posts_to_do = all_posts[:MAX_PER_RUN]
    log(f"📊 {len(posts_to_do)} posts worden verwerkt (max {MAX_PER_RUN}).")

    for post in posts_to_do:
        handle = post["handle"]
        uri = post["uri"]
        cid = post["cid"]

        if reposted >= MAX_PER_RUN:
            break

        if handle != EXEMPT_HANDLE:
            per_user_count[handle] = per_user_count.get(handle, 0)
            if per_user_count[handle] >= MAX_PER_USER:
                continue

        try:
            # Repost
            client.app.bsky.feed.repost.create(
                repo=client.me.did,
                record={
                    "subject": {"uri": uri, "cid": cid},
                    "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )
            log(f"🔁 Gerepost @{handle}: {uri}")
            done.add(uri)
            reposted += 1
            per_user_count[handle] = per_user_count.get(handle, 0) + 1
            time.sleep(2)

            # Like
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
            except Exception as e_like:
                log(f"⚠️ Fout bij liken @{handle}: {e_like}")
        except Exception as e:
            log(f"⚠️ Fout bij repost @{handle}: {e}")

    with open(repost_log, "w") as f:
        f.write("\n".join(done))

    log(f"✅ Klaar! ({reposted} reposts, {liked} likes)")
    log(f"🧮 Totaal bekeken: {len(all_posts)}, nieuw gerepost: {reposted}")
    log(f"⏰ Run beëindigd om {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")

if __name__ == "__main__":
    main()