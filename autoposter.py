from atproto import Client
import os
import time
from datetime import datetime, timedelta, timezone

# Configuratie
FEED_URI = "at://did:plc:jaka644beit3x4vmmg6yysw7/app.bsky.feed.generator/aaaprg6dqhaii"
MAX_PER_RUN = 50
MAX_PER_USER = 5
HOURS_BACK = 8

def main():
    username = os.environ["BSKY_USERNAME"]
    password = os.environ["BSKY_PASSWORD"]
    client = Client()
    client.login(username, password)

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Start autoposter")

    try:
        feed = client.app.bsky.feed.get_feed({"feed": FEED_URI, "limit": 100})
        items = feed.feed
    except Exception:
        print("Feed ophalen mislukt.")
        return

    repost_log = "reposted.txt"
    done = set()
    if os.path.exists(repost_log):
        with open(repost_log, "r") as f:
            done = set(f.read().splitlines())

    cutoff = datetime.now(timezone.utc) - timedelta(hours=HOURS_BACK)
    all_posts = []

    for item in items:
        post = item.post
        record = post.record
        uri = post.uri
        cid = post.cid
        if hasattr(item, "reason") and item.reason is not None:
            continue
        if getattr(record, "reply", None):
            continue
        if uri in done:
            continue

        created = getattr(record, "createdAt", None) or getattr(post, "indexedAt", None)
        if not created:
            continue

        try:
            created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
        except Exception:
            continue
        if created_dt < cutoff:
            continue

        all_posts.append({"uri": uri, "cid": cid, "created": created_dt})

    all_posts.sort(key=lambda x: x["created"])
    reposted = 0
    liked = 0
    per_user_count = {}

    for post in all_posts:
        if reposted >= MAX_PER_RUN:
            break
        uri, cid = post["uri"], post["cid"]
        try:
            client.app.bsky.feed.repost.create(
                repo=client.me.did,
                record={
                    "subject": {"uri": uri, "cid": cid},
                    "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )
            done.add(uri)
            reposted += 1
            time.sleep(2)
            try:
                client.app.bsky.feed.like.create(
                    repo=client.me.did,
                    record={
                        "subject": {"uri": uri, "cid": cid},
                        "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    },
                )
                liked += 1
                time.sleep(1)
            except:
                pass
        except:
            pass

    with open(repost_log, "w") as f:
        f.write("\n".join(done))

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Klaar ({reposted} reposts, {liked} likes)")

if __name__ == "__main__":
    main()