from atproto import Client
import os
import time
from datetime import datetime, timedelta, timezone

# Configuratie
FEED_URI = "at://did:plc:jaka644beit3x4vmmg6yysw7/app.bsky.feed.generator/aaaprg6dqhaii"
MAX_PER_RUN = 50
SPREAD_MINUTES = 30  # spreid reposts over 30 minuten

def log(msg):
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
    posts = feed.feed
    log(f"🕒 {len(posts)} posts opgehaald.")

    repost_log = "reposted.txt"
    done = set()
    if os.path.exists(repost_log):
        with open(repost_log, "r") as f:
            done = set(f.read().splitlines())

    new_posts = []
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=2)

    for item in posts:
        post = item.post
        uri = post.uri
        cid = post.cid
        record = post.record
        handle = post.author.handle

        if hasattr(item, "reason") and item.reason is not None:
            continue
        if getattr(record, "reply", None):
            continue
        if uri in done:
            continue

        created = getattr(record, "createdAt", None) or getattr(post, "indexedAt", None)
        if not created:
            continue
        created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
        if created_dt < cutoff_time:
            continue

        new_posts.append({
            "handle": handle,
            "uri": uri,
            "cid": cid,
            "created": created_dt
        })

    new_posts.sort(key=lambda x: x["created"])  # oudste eerst

    to_post = new_posts[:MAX_PER_RUN]
    log(f"📊 {len(to_post)} posts worden verwerkt (max {MAX_PER_RUN}).")

    if to_post:
        delay = (SPREAD_MINUTES * 60) / len(to_post)
    else:
        delay = 0

    reposted = 0
    liked = 0

    for post in to_post:
        handle = post["handle"]
        uri = post["uri"]
        cid = post["cid"]

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
            done.add(uri)

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
            except Exception as e_like:
                log(f"⚠️ Fout bij liken @{handle}: {e_like}")

            time.sleep(delay)
        except Exception as e:
            log(f"⚠️ Fout bij repost @{handle}: {e}")

    with open(repost_log, "w") as f:
        f.write("\n".join(done))

    log(f"✅ Klaar! ({reposted} reposts, {liked} likes)")
    log(f"⏰ Run beëindigd om {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")

if __name__ == "__main__":
    main()