from atproto import Client
import os
import time
from datetime import datetime, timedelta, timezone

# 🔗 Feed-URI die de bot moet volgen
FEED_URI = "at://did:plc:jaka644beit3x4vmmg6yysw7/app.bsky.feed.generator/aaaprg6dqhaii"

# 🧩 Configuratie
MAX_PER_RUN = 50          # maximaal aantal reposts per run
MAX_PER_USER = 5          # limiet per gebruiker
HOURS_BACK = 2            # alleen posts van de laatste 2 uur

def log(msg: str):
    """Print log met UTC-tijdstempel"""
    now = datetime.now(timezone.utc).strftime("[%H:%M:%S]")
    print(f"{now} {msg}")

def main():
    username = os.environ["BSKY_USERNAME"]
    password = os.environ["BSKY_PASSWORD"]

    client = Client()
    client.login(username, password)
    log(f"✅ Ingelogd als {username}")

    log("🔎 Ophalen feed...")
    try:
        feed = client.app.bsky.feed.get_feed({"feed": FEED_URI, "limit": 100})
        posts = feed.feed
    except Exception as e:
        log(f"⚠️ Fout bij ophalen feed: {e}")
        return

    log(f"🕒 {len(posts)} posts opgehaald.")
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=HOURS_BACK)

    reposted = 0
    liked = 0
    per_user_count = {}
    recent_posts = []

    # 🔍 Filter op tijd en replies
    for item in posts:
        post = item.post
        record = post.record
        uri = post.uri
        cid = post.cid
        handle = post.author.handle

        if hasattr(item, "reason") and item.reason is not None:
            continue
        if getattr(record, "reply", None):
            continue

        created_at = getattr(record, "createdAt", None)
        if not created_at:
            continue
        try:
            created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except Exception:
            continue

        if created_dt >= cutoff_time:
            recent_posts.append({
                "handle": handle,
                "uri": uri,
                "cid": cid,
                "created": created_dt
            })

    # Oudste eerst
    recent_posts.sort(key=lambda x: x["created"])

    log(f"📊 {len(recent_posts)} posts worden verwerkt (max {MAX_PER_RUN}).")
    posts_to_do = recent_posts[:MAX_PER_RUN]

    # 🕒 Bereken interval zodat alle reposts gelijkmatig over 30 minuten worden verspreid
    if posts_to_do:
        interval = 1800 / len(posts_to_do)
    else:
        interval = 0

    log(f"⏱️ Repost-interval ingesteld op {interval:.1f} seconden per post.")

    for post in posts_to_do:
        if reposted >= MAX_PER_RUN:
            break

        handle = post["handle"]
        uri = post["uri"]
        cid = post["cid"]

        if per_user_count.get(handle, 0) >= MAX_PER_USER:
            continue

        try:
            # Repost
            client.app.bsky.feed.repost.create(
                repo=client.me.did,
                record={
                    "subject": {"uri": uri, "cid": cid},
                    "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                },
            )
            log(f"🔁 Gerepost @{handle}: {uri}")
            reposted += 1
            per_user_count[handle] = per_user_count.get(handle, 0) + 1

            # Like
            try:
                client.app.bsky.feed.like.create(
                    repo=client.me.did,
                    record={
                        "subject": {"uri": uri, "cid": cid},
                        "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                    },
                )
                log(f"❤️ Geliked @{handle}")
                liked += 1
            except Exception as e_like:
                log(f"⚠️ Fout bij liken @{handle}: {e_like}")

        except Exception as e:
            log(f"⚠️ Fout bij repost @{handle}: {e}")

        # ⏳ Vertraging tussen reposts
        if interval > 0 and reposted < len(posts_to_do):
            time.sleep(interval)

    log(f"✅ Klaar! ({reposted} reposts, {liked} likes)")
    log(f"🧮 Totaal bekeken: {len(posts)}, nieuw gerepost: {reposted}")
    log(f"⏰ Run beëindigd om {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")

if __name__ == "__main__":
    main()