from atproto import Client
import os
import time
from datetime import datetime, timedelta, timezone

# Feed URI (van je lijst-feed)
FEED_URI = "at://did:plc:jaka644beit3x4vmmg6yysw7/app.bsky.feed.generator/aaaprg6dqhaii"

# Config
MAX_PER_RUN = 50
HOURS_BACK = 4  # kijkt naar laatste 4 uur

def log(msg: str):
    """Print logregel met tijdstempel"""
    now = datetime.now(timezone.utc).strftime("[%H:%M:%S]")
    print(f"{now} {msg}")

def main():
    username = os.environ["BSKY_USERNAME"]
    password = os.environ["BSKY_PASSWORD"]

    client = Client()
    client.login(username, password)
    log(f"✅ Ingelogd als {username}")

    log("🔎 Ophalen feed...")
    feed = client.app.bsky.feed.get_feed({"feed": FEED_URI, "limit": 100})
    items = feed.feed
    log(f"🕒 {len(items)} posts opgehaald.")

    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=HOURS_BACK)

    new_posts = []
    for item in items:
        post = item.post
        record = post.record
        uri = post.uri
        cid = post.cid
        handle = post.author.handle

        # probeer tijd te lezen
        created = getattr(record, "createdAt", None) or getattr(post, "indexedAt", None)
        if not created:
            continue
        created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))

        if created_dt >= cutoff_time:
            new_posts.append({
                "uri": uri,
                "cid": cid,
                "handle": handle,
                "created": created_dt
            })

    log(f"📊 {len(new_posts)} posts worden verwerkt (max {MAX_PER_RUN}).")

    reposted = 0
    liked = 0
    for post in sorted(new_posts, key=lambda x: x["created"]):
        if reposted >= MAX_PER_RUN:
            break
        uri, cid, handle = post["uri"], post["cid"], post["handle"]
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
            time.sleep(2)

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
            log(f"⚠️ Fout bij posten @{handle}: {e}")

    log(f"✅ Klaar! ({reposted} reposts, {liked} likes)")
    log(f"⏰ Run beëindigd om {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")

if __name__ == "__main__":
    main()