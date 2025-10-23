import os
import time
from datetime import datetime, timezone
from atproto import Client

# === CONFIG ===
FEED_URI = "at://did:plc:jaka644beit3x4vmmg6yysw7/app.bsky.feed.generator/aaabcd2jy6n7s"
MAX_POSTS_PER_RUN = 30
MAX_POSTS_PER_USER = 2

def log(msg: str):
    """Minimale logging, geen gebruikersinformatie"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def main():
    username = os.getenv("BSKY_USERNAME")
    password = os.getenv("BSKY_PASSWORD")

    if not username or not password:
        log("❌ Geen inloggegevens gevonden.")
        return

    client = Client()
    client.login(username, password)
    log("✅ Ingelogd")

    try:
        feed = client.app.bsky.feed.get_feed({"feed": FEED_URI, "limit": 100})
        posts = feed.feed
        log(f"📥 {len(posts)} posts opgehaald uit feed.")
    except Exception as e:
        log(f"⚠️ Fout bij ophalen feed: {e}")
        return

    reposted = 0
    liked = 0
    per_user = {}

    for item in posts:
        if reposted >= MAX_POSTS_PER_RUN:
            break

        post = item.post
        author = getattr(post.author, "did", None)
        uri = post.uri
        cid = post.cid

        if not author or per_user.get(author, 0) >= MAX_POSTS_PER_USER:
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
            reposted += 1
            per_user[author] = per_user.get(author, 0) + 1
            time.sleep(1)

            # Like
            client.app.bsky.feed.like.create(
                repo=client.me.did,
                record={
                    "subject": {"uri": uri, "cid": cid},
                    "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )
            liked += 1
            time.sleep(1)

        except Exception:
            continue  # geen details loggen

    log(f"✅ Klaar! ({reposted} reposts, {liked} likes uitgevoerd)")
    log(f"⏰ Run beëindigd om {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")

if __name__ == "__main__":
    main()