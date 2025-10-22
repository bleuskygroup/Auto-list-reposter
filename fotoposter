import os
import time
import requests
from datetime import datetime, timedelta, timezone
from atproto import Client

# === CONFIG ===
FEED_URI = "at://did:plc:jaka644beit3x4vmmg6yysw7/app.bsky.feed.generator/aaaaph4xy7utg"
MAX_POSTS_PER_RUN = 30
MAX_POSTS_PER_USER = 2
DELAY_BETWEEN_POSTS = 2
LOOKBACK_HOURS = 2

def log(msg: str):
    """Veilige log zonder gevoelige data"""
    now = datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] {msg}")

def login(username: str, password: str) -> Client:
    client = Client()
    client.login(username, password)
    log("🔑 Login succesvol.")
    return client

def get_feed_items(feed_uri: str):
    """Haalt feeditems op via Bluesky publieke API"""
    url = f"https://public.api.bsky.app/xrpc/app.bsky.feed.getFeed?feed={feed_uri}"
    log(f"🌐 Ophalen feed: {url}")
    try:
        response = requests.get(url, timeout=15)
        if response.status_code != 200:
            log(f"⚠️ Feed request mislukt: {response.status_code}")
            return []
        data = response.json()
        feed = data.get("feed", [])
        log(f"✅ {len(feed)} items ontvangen van feed.")
        return feed
    except Exception as e:
        log(f"⚠️ Feed ophalen mislukt: {e}")
        return []

def get_recent_posts(feed_items):
    """Filter posts van de laatste LOOKBACK_HOURS uren"""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    posts = []

    for item in reversed(feed_items):  # oudste eerst
        post_data = item.get("post", {})
        uri = post_data.get("uri")
        cid = post_data.get("cid")
        author = post_data.get("author", {}).get("did")
        record = post_data.get("record", {})
        created_at = record.get("createdAt")

        # Tijdfilter
        post_time = None
        if created_at:
            try:
                post_time = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except Exception:
                pass

        if not post_time or post_time >= cutoff:
            if uri and cid and author:
                posts.append({"uri": uri, "cid": cid, "author": author})

    return posts

def repost_and_like_feed(client: Client):
    log("📡 Ophalen feed via publieke API...")
    feed_items = get_feed_items(FEED_URI)
    posts = get_recent_posts(feed_items)
    log(f"Gevonden {len(posts)} geschikte posts voor repost binnen {LOOKBACK_HOURS} uur.")

    if not posts:
        log("⚠️ Geen geschikte posts gevonden. Misschien ouder dan 2 uur of geen nieuwe content.")
        return

    seen_uris = set()
    per_user = {}
    reposted_count = 0

    for post in posts:
        if reposted_count >= MAX_POSTS_PER_RUN:
            break

        author = post["author"]
        if per_user.get(author, 0) >= MAX_POSTS_PER_USER:
            continue
        if post["uri"] in seen_uris:
            continue

        try:
            # === Repost ===
            client.app.bsky.feed.repost.create(
                repo=client.me.did,
                record={
                    "subject": {"uri": post["uri"], "cid": post["cid"]},
                    "createdAt": client.get_current_time_iso(),
                    "$type": "app.bsky.feed.repost",
                },
            )

            # === Like ===
            client.app.bsky.feed.like.create(
                repo=client.me.did,
                record={
                    "subject": {"uri": post["uri"], "cid": post["cid"]},
                    "createdAt": client.get_current_time_iso(),
                    "$type": "app.bsky.feed.like",
                },
            )

            reposted_count += 1
            per_user[author] = per_user.get(author, 0) + 1
            seen_uris.add(post["uri"])

            log(f"✅ Repost + like uitgevoerd ({reposted_count}/{MAX_POSTS_PER_RUN})")

            if reposted_count < MAX_POSTS_PER_RUN:
                time.sleep(DELAY_BETWEEN_POSTS)

        except Exception as e:
            log(f"⚠️ Fout bij repost/like: {e}")

    log(f"🎯 Klaar: {reposted_count} posts gerepost + geliked.")

def main():
    username = os.getenv("BSKY_USERNAME")
    password = os.getenv("BSKY_PASSWORD")

    if not username or not password:
        log("❌ Geen inloggegevens gevonden (BSKY_USERNAME/BSKY_PASSWORD).")
        return

    try:
        client = login(username, password)
    except Exception as e:
        log(f"❌ Inloggen mislukt: {e}")
        return

    repost_and_like_feed(client)

if __name__ == "__main__":
    main()