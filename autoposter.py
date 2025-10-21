from atproto import Client
import os
import time
from datetime import datetime, timedelta, timezone

# Bluesky feed (deze vervangt de lijst)
FEED_URI = "at://did:plc:jaka644beit3x4vmmg6yysw7/app.bsky.feed.generator/aaaprg6dqhaii"

# Configuratie
MAX_PER_RUN = 50
MAX_PER_USER = 5
HOURS_BACK = 3            # alleen posts uit de laatste 3 uur
SPREAD_MINUTES = 30       # totale tijdsduur waarin de reposts worden verspreid

def log(msg: str):
    """Print logregel met tijdstempel"""
    now = datetime.now(timezone.utc).strftime("[%H:%M:%S]")
    print(f"{now} {msg}")

def parse_time(record, post):
    """Probeer timestamp te vinden"""
    for attr in ["createdAt", "indexedAt", "created_at", "timestamp"]:
        val = getattr(record, attr, None) or getattr(post, attr, None)
        if val:
            try:
                return datetime.fromisoformat(val.replace("Z", "+00:00"))
            except Exception:
                continue
    return None

def main():
    username = os.environ["BSKY_USERNAME"]
    password = os.environ["BSKY_PASSWORD"]
    client = Client()
    client.login(username, password)
    log(f"✅ Ingelogd als {username}")

    # Ophalen van feed
    try:
        log("🔎 Ophalen feed...")
        feed = client.app.bsky.feed.get_feed({"feed": FEED_URI, "limit": 100})
        items = feed.feed
        log(f"🕒 {len(items)} posts opgehaald.")
    except Exception as e:
        log(f"⚠️ Fout bij ophalen feed: {e}")
        return

    # Inladen repost-log
    repost_log = "reposted.txt"
    done = set()
    if os.path.exists(repost_log):
        with open(repost_log, "r") as f:
            done = set(f.read().splitlines())

    all_posts = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=HOURS_BACK)

    for item in items:
        post = item.post
        record = post.record
        uri = post.uri
        cid = post.cid
        handle = getattr(post.author, "handle", "onbekend")

        # Skip reposts of replies
        if hasattr(item, "reason") and item.reason is not None:
            continue
        if getattr(record, "reply", None):
            continue
        if uri in done:
            continue

        created_dt = parse_time(record, post)
        if not created_dt or created_dt < cutoff:
            continue

        all_posts.append({
            "handle": handle,
            "uri": uri,
            "cid": cid,
            "created": created_dt,
        })

    log(f"📊 {len(all_posts)} posts worden verwerkt (max {MAX_PER_RUN}).")

    # Oudste eerst
    all_posts.sort(key=lambda x: x["created"])

    reposted = 0
    liked = 0
    per_user_count = {}
    posts_to_do = all_posts[:MAX_PER_RUN]

    # Bereken vertraging (gelijk verdeeld over 30 minuten)
    delay = (SPREAD_MINUTES * 60) / max(1, len(posts_to_do))
    log(f"🕐 Vertraging ingesteld op ongeveer {round(delay,1)} seconden tussen reposts.")

    for post in posts_to_do:
        if reposted >= MAX_PER_RUN:
            break

        handle = post["handle"]
        uri = post["uri"]
        cid = post["cid"]

        per_user_count[handle] = per_user_count.get(handle, 0)
        if per_user_count[handle] >= MAX_PER_USER:
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
            log(f"🔁 Gerepost @{handle}: {uri}")
            done.add(uri)
            reposted += 1
            per_user_count[handle] += 1

            # Like direct na repost
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

            # Wachten tot volgende repost (gelijkmatig over 30 min)
            time.sleep(delay)

        except Exception as e:
            log(f"⚠️ Fout bij repost @{handle}: {e}")

    # Log opslaan
    with open(repost_log, "w") as f:
        f.write("\n".join(done))

    log(f"✅ Klaar! ({reposted} reposts, {liked} likes)")
    log(f"🧮 Totaal bekeken: {len(items)}, nieuw gerepost: {reposted}")
    log(f"⏰ Run beëindigd om {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")

if __name__ == "__main__":
    main()