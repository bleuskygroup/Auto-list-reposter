from atproto import Client
import os
import time
from datetime import datetime, timedelta, timezone

# 🔧 Config
FEED_URI = "at://did:plc:jaka644beit3x4vmmg6yysw7/app.bsky.feed.generator/aaaprg6dqhaii"
MAX_PER_RUN = 50          # maximaal aantal reposts per run
SPREAD_DURATION = 1800    # 30 minuten in seconden

def log(msg: str):
    now = datetime.now(timezone.utc).strftime("[%H:%M:%S]")
    print(f"{now} {msg}")

def parse_time(post):
    """Probeer de tijd van een post te bepalen"""
    for attr in ["createdAt", "indexedAt", "created_at", "timestamp"]:
        val = getattr(post.record, attr, None) or getattr(post, attr, None)
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
    feed = client.app.bsky.feed.get_feed({"feed": FEED_URI, "limit": 100})
    posts = feed.feed

    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=2)
    all_posts = []

    for item in posts:
        post = item.post
        record = post.record
        uri = post.uri
        cid = post.cid

        # Reposts overslaan
        if hasattr(item, "reason") and item.reason is not None:
            continue

        # Tijd ophalen
        created_dt = parse_time(post)
        if not created_dt or created_dt < cutoff_time:
            continue

        all_posts.append({
            "handle": post.author.handle,
            "uri": uri,
            "cid": cid,
            "created": created_dt,
        })

    # Oudste eerst
    all_posts.sort(key=lambda x: x["created"])
    log(f"🕒 {len(all_posts)} posts opgehaald.")
    posts_to_do = all_posts[:MAX_PER_RUN]
    log(f"📊 {len(posts_to_do)} posts worden verwerkt (max {MAX_PER_RUN}).")

    # Repostlog bijhouden
    repost_log = "reposted.txt"
    done = set()
    if os.path.exists(repost_log):
        with open(repost_log, "r") as f:
            done = set(f.read().splitlines())

    reposted = 0
    liked = 0

    for post in posts_to_do:
        uri = post["uri"]
        cid = post["cid"]
        handle = post["handle"]

        if uri in done:
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
            done.add(uri)
            reposted += 1

            # ❤️ Like direct na repost
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
            except Exception as e:
                log(f"⚠️ Fout bij liken @{handle}: {e}")

            # 🕐 Automatische spreiding over 30 minuten
            remaining = len(posts_to_do) - reposted
            if remaining > 0:
                delay_seconds = SPREAD_DURATION / len(posts_to_do)
                log(f"⏳ Wachten {int(delay_seconds)} seconden tot volgende repost...")
                time.sleep(delay_seconds)

        except Exception as e:
            log(f"⚠️ Fout bij repost @{handle}: {e}")

    with open(repost_log, "w") as f:
        f.write("\n".join(done))

    log(f"✅ Klaar! ({reposted} reposts, {liked} likes)")
    log(f"🧮 Totaal bekeken: {len(all_posts)}, nieuw gerepost: {reposted}")
    log(f"⏰ Run beëindigd om {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")

if __name__ == "__main__":
    main()