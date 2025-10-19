from atproto import Client
import os
from datetime import datetime

LIST_URI = "at://did:plc:jaka644beit3x4vmmg6yysw7/app.bsky.graph.list/3m3iga6wnmz2p"

def log(msg):
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{now}] {msg}")

def main():
    username = os.environ["BSKY_USERNAME"]
    password = os.environ["BSKY_PASSWORD"]

    client = Client()
    client.login(username, password)
    log(f"✅ Ingelogd als: {username}")

    members = client.app.bsky.graph.get_list({"list": LIST_URI}).items
    log(f"📋 {len(members)} gebruikers in lijst gevonden.")

    for member in members:
        handle = member.subject.handle
        log(f"🔎 Check feed @{handle}")

        feed = client.app.bsky.feed.get_author_feed({"actor": handle, "limit": 5})
        for i, post in enumerate(feed.feed, start=1):
            record = post.post.record
            uri = post.post.uri
            created = getattr(record, "createdAt", None)
            embed = getattr(post.post, "embed", None)
            embed_type = getattr(embed, "$type", "❌ geen embed")
            log(f"{i}. @{handle} → {uri}")
            log(f"   🕒 createdAt: {created}")
            log(f"   🎞️ embed type: {embed_type}")
            if hasattr(post.post, "indexed_at"):
                log(f"   ⏱️ indexed_at: {post.post.indexed_at}")
            if hasattr(post.post, "indexedAt"):
                log(f"   ⏱️ indexedAt: {post.post.indexedAt}")

    log("✅ Klaar met testrun!")

if __name__ == "__main__":
    main()