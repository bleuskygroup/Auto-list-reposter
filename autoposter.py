from atproto import Client
from datetime import datetime, timedelta, timezone
import time
import os

# 🔧 Instellingen
FEED_URI = "at://did:plc:jaka644beit3x4vmmg6yysw7/app.bsky.feed.generator/aaaprg6dqhaii"
HOURS_BACK = 2          # bekijkt posts van de laatste 2 uur
MAX_POSTS = 50
MAX_PER_USER = 5
SPREAD_MINUTES = 30     # verdeel reposts over deze tijd (30 minuten)

def main():
    username = os.getenv("BSKY_USERNAME")
    password = os.getenv("BSKY_PASSWORD")

    client = Client()
    client.login(username, password)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Ingelogd als {username}")

    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔎 Ophalen feed...")
    feed = client.app.bsky.feed.get_feed({"feed": FEED_URI})
    items = feed["feed"]

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=HOURS_BACK)

    posts = []
    for item in items:
        post = item["post"]
        author = post["author"]["handle"]
        uri = post["uri"]
        created = datetime.fromisoformat(post["record"]["createdAt"].replace("Z", "+00:00"))
        if created > cutoff:
            posts.append((author, uri, created))

    posts.sort(key=lambda x: x[2])  # oudste eerst
    total_to_post = min(len(posts), MAX_POSTS)

    print(f"[{datetime.now().strftime('%H:%M:%S')}] 📊 {total_to_post} posts worden verwerkt (max {MAX_POSTS}).")

    # Bereken automatische vertraging
    if total_to_post > 0:
        delay_per_post = (SPREAD_MINUTES * 60) / total_to_post
    else:
        delay_per_post = 0
    print(f"[{datetime.now().strftime('%H:%M:%S')}] ⏱️ Reposts worden automatisch verdeeld: {delay_per_post:.1f} seconden per post.")

    user_counts = {}
    reposted = 0
    liked = 0

    for author, uri, created in posts[:MAX_POSTS]:
        if user_counts.get(author, 0) >= MAX_PER_USER:
            continue

        try:
            client.app.bsky.feed.repost.create({
                "subject": uri,
                "createdAt": datetime.now(timezone.utc).isoformat()
            })
            reposted += 1
            user_counts[author] = user_counts.get(author, 0) + 1
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔁 Gerepost {author}: {uri}")

            client.app.bsky.feed.like.create({
                "subject": uri,
                "createdAt": datetime.now(timezone.utc).isoformat()
            })
            liked += 1
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ❤️ Geliked {author}")

            if reposted < total_to_post:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ⏳ Wachten {delay_per_post:.1f} seconden tot volgende repost...")
                time.sleep(delay_per_post)

        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ Fout bij {author}: {e}")

    print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Klaar! ({reposted} reposts, {liked} likes)")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🧮 Totaal bekeken: {len(items)}, nieuw gerepost: {reposted}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] ⏰ Run beëindigd om {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S %Z')}")

if __name__ == "__main__":
    main()