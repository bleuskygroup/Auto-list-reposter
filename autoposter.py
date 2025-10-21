from atproto import Client
import os
import time
from datetime import datetime, timedelta, timezone

# 🔗 Feed-URL (zoals getest)
FEED_URI = "at://did:plc:jaka644beit3x4vmmg6yysw7/app.bsky.feed.generator/aaaprg6dqhaii"

# ⚙️ Config
MAX_PER_RUN = 50
HOURS_BACK = 2   # posts van de laatste 2 uur
MAX_PER_USER = 5

def log(msg: str):
    """Print log met tijdstempel"""
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

    cutoff = datetime.now(timezone.utc) - timedelta(hours=HOURS_BACK)
    repost_log = "reposted.txt"
    done = set()
    if os.path.exists(repost_log):
        with open(repost_log, "r") as f:
            done = set(f.read().splitlines())

    filtered = []
    for item in posts:
        try:
            post = item.post
            record = post.record
            created_str = getattr(record, "createdAt", None)
            if not created_str:
                continue
            created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
            if created < cutoff:
                continue
            uri = post.uri
            cid = post.cid
            if uri in done:
                continue
            filtered.append({
                "handle": post.author.handle,
                "uri": uri,
                "cid": cid,
                "created": created,
            })
        except Exception as e:
            log(f"⚠️ Feed-item overgeslagen ({e})")

    log(f"📊 {len(filtered)} posts worden verwerkt (max {MAX_PER_RUN}).")

    filtered.sort(key=lambda x: x["created"])  # oudste eerst

    reposted = 0
    liked = 0
    per_user = {}

    for p in filtered[:MAX_PER_RUN]:
        h = p["handle"]
        uri = p["uri"]
        cid = p["cid"]
        if per_user.get(h, 0) >= MAX_PER_USER:
            continue
        try:
            client.app.bsky.feed.repost.create(
                repo=client.me.did,
                record={
                    "subject": {"uri": uri, "cid": cid},
                    "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )
            log(f"🔁 Gerepost @{h}")
            reposted += 1
            done.add(uri)
            per_user[h] = per_user.get(h, 0) + 1
            time.sleep(2)

            # Like erbij
            try:
                client.app.bsky.feed.like.create(
                    repo=client.me.did,
                    record={
                        "subject": {"uri": uri, "cid": cid},
                        "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    },
                )
                liked += 1
                log(f"❤️ Geliked @{h}")
                time.sleep(1)
            except Exception as e_like:
                log(f"⚠️ Like fout @{h}: {e_like}")
        except Exception as e:
            log(f"⚠️ Repost fout @{h}: {e}")

    with open(repost_log, "w") as f:
        f.write("\n".join(done))

    log(f"✅ Klaar! ({reposted} reposts, {liked} likes)")
    log(f"🧮 Totaal bekeken: {len(posts)}, nieuw gerepost: {reposted}")
    log(f"⏰ Run beëindigd om {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")

if __name__ == "__main__":
    main()