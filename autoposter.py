from atproto import Client
import os
import time
from datetime import datetime, timedelta, timezone

# FEED-URI van je Bluesky feed (deze kun je aanpassen)
FEED_URI = "at://did:plc:jaka644beit3x4vmmg6yysw7/app.bsky.feed.generator/aaaprg6dqhaii"

# Instellingen
MAX_PER_RUN = 50
HOURS_BACK = 2            # laatste 2 uur
SPREAD_MINUTES = 30       # verspreiding over 30 minuten
REPOST_LOG = "reposted.txt"

def log(msg: str):
    """Log met UTC tijd"""
    now = datetime.now(timezone.utc).strftime("[%H:%M:%S]")
    print(f"{now} {msg}")

def clean_log(done):
    """Houd log schoon (oude entries weg na 2 dagen)"""
    cutoff = datetime.now(timezone.utc) - timedelta(days=2)
    cleaned = {}
    for uri, t in done.items():
        if t > cutoff:
            cleaned[uri] = t
    return cleaned

def load_repost_log():
    if not os.path.exists(REPOST_LOG):
        return {}
    done = {}
    with open(REPOST_LOG, "r") as f:
        for line in f:
            try:
                uri, ts = line.strip().split("|")
                done[uri] = datetime.fromisoformat(ts)
            except Exception:
                continue
    return done

def save_repost_log(done):
    with open(REPOST_LOG, "w") as f:
        for uri, t in done.items():
            f.write(f"{uri}|{t.isoformat()}\n")

def main():
    username = os.environ["BSKY_USERNAME"]
    password = os.environ["BSKY_PASSWORD"]

    client = Client()
    client.login(username, password)
    log(f"✅ Ingelogd als {username}")

    log("🔎 Ophalen feed...")
    feed = client.app.bsky.feed.get_feed({"feed": FEED_URI, "limit": 100})
    posts = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=HOURS_BACK)

    for item in feed.feed:
        post = item.post
        record = post.record
        uri = post.uri
        cid = post.cid

        if hasattr(item, "reason") and item.reason is not None:
            continue
        if getattr(record, "reply", None):
            continue

        created = getattr(record, "createdAt", None)
        if not created:
            continue
        created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))

        if created_dt >= cutoff:
            posts.append({"uri": uri, "cid": cid, "created": created_dt})

    log(f"🕒 {len(posts)} posts opgehaald.")
    done = load_repost_log()
    done = clean_log(done)

    new_posts = [p for p in posts if p["uri"] not in done]
    new_posts.sort(key=lambda x: x["created"])  # oudste eerst

    posts_to_do = new_posts[:MAX_PER_RUN]
    log(f"📊 {len(posts_to_do)} posts worden verwerkt (max {MAX_PER_RUN}).")

    if not posts_to_do:
        log("✅ Geen nieuwe posts gevonden.")
        return

    # interval berekenen
    total_seconds = SPREAD_MINUTES * 60
    interval = total_seconds / max(len(posts_to_do), 1)
    log(f"⏱️ Repost-interval ingesteld op {interval:.1f} seconden per post.")

    reposted = 0
    for post in posts_to_do:
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
            done[uri] = datetime.now(timezone.utc)
            log(f"🔁 Gerepost: {uri}")
            reposted += 1

            # like toevoegen
            try:
                client.app.bsky.feed.like.create(
                    repo=client.me.did,
                    record={
                        "subject": {"uri": uri, "cid": cid},
                        "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    },
                )
                log("❤️ Geliked")
            except Exception as e:
                log(f"⚠️ Fout bij liken: {e}")

        except Exception as e:
            log(f"⚠️ Fout bij reposten: {e}")

        save_repost_log(done)
        time.sleep(interval)

    log(f"✅ Klaar! ({reposted} reposts, {reposted} likes)")
    log(f"🧮 Totaal bekeken: {len(posts)}, nieuw gerepost: {reposted}")
    log(f"⏰ Run beëindigd om {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")

if __name__ == "__main__":
    main()