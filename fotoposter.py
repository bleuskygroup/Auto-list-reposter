import os
import time
import requests
from datetime import datetime, timedelta, timezone
from atproto import Client

# === CONFIG ===
FEED_URI = "at://did:plc:jaka644beit3x4vmmg6yysw7/app.bsky.feed.generator/aaaaph4xy7utg"
MAX_POSTS_PER_RUN = 30
MAX_POSTS_PER_USER = 2
LOOKBACK_HOURS = 2
SEEN_FILE = "seen_posts.txt"  # sla eerder geposte URIs op

# === SLIMME VERTRAGING ===
def calc_delay(count):
    if count <= 10:
        return 2
    elif count <= 20:
        return 5
    else:
        return 10

def log(msg):
    now = datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] {msg}")

def login():
    username = os.getenv("BSKY_USERNAME")
    password = os.getenv("BSKY_PASSWORD")
    if not username or not password:
        raise ValueError("Geen inloggegevens gevonden in secrets.")
    client = Client()
    client.login(username, password)
    return client

def get_feed_items():
    url = f"https://public.api.bsky.app/xrpc/app.bsky.feed.getFeed?feed={FEED_URI}"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json().get("feed", [])

def get_recent(posts):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    result = []
    for item in reversed(posts):
        post = item.get("post", {})
        record = post.get("record", {})
        created_at = record.get("createdAt")
        try:
            post_time = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except Exception:
            post_time = None
        if not post_time or post_time >= cutoff:
            uri = post.get("uri")
            cid = post.get("cid")
            author = post.get("author", {}).get("did")
            if uri and cid and author:
                result.append({"uri": uri, "cid": cid, "author": author})
    return result

def load_seen():
    if not os.path.exists(SEEN_FILE):
        return set()
    with open(SEEN_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        for uri in seen:
            f.write(uri + "\n")

def main():
    log("🚀 Start Bluesky fotoposter")
    try:
        client = login()
        feed_items = get_feed_items()
        posts = get_recent(feed_items)
        seen = load_seen()
        log(f"📸 {len(posts)} posts gevonden binnen {LOOKBACK_HOURS} uur")

        reposted = 0
        per_user = {}

        for post in posts:
            if reposted >= MAX_POSTS_PER_RUN:
                break
            if post["uri"] in seen:
                continue

            author = post["author"]
            if per_user.get(author, 0) >= MAX_POSTS_PER_USER:
                continue

            try:
                client.app.bsky.feed.repost.create(
                    repo=client.me.did,
                    record={
                        "subject": {"uri": post["uri"], "cid": post["cid"]},
                        "createdAt": client.get_current_time_iso(),
                        "$type": "app.bsky.feed.repost",
                    },
                )
                client.app.bsky.feed.like.create(
                    repo=client.me.did,
                    record={
                        "subject": {"uri": post["uri"], "cid": post["cid"]},
                        "createdAt": client.get_current_time_iso(),
                        "$type": "app.bsky.feed.like",
                    },
                )
                reposted += 1
                per_user[author] = per_user.get(author, 0) + 1
                seen.add(post["uri"])

                delay = calc_delay(reposted)
                log(f"✅ Reposted + liked ({reposted}) — wacht {delay}s")
                time.sleep(delay)

            except Exception as e:
                log(f"⚠️ Fout bij repost: {e}")

        save_seen(seen)
        log(f"✅ Klaar — {reposted} nieuwe posts gerepost + geliked.")

    except Exception as e:
        log(f"❌ Fout: {e}")

if __name__ == "__main__":
    main()