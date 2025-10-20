from atproto import Client
import os
import time
from datetime import datetime, timedelta, timezone

# Bluesky-lijst met accounts
LIST_URI = "at://did:plc:jaka644beit3x4vmmg6yysw7/app.bsky.graph.list/3m3iga6wnmz2p"

# Gebruiker zonder repostlimiet
EXEMPT_HANDLE = "bleuskybeauty.bsky.social"

# Config
MAX_PER_RUN = 50
MAX_PER_USER = 5
HOURS_BACK = 24  # enkel laatste dag (24 uur)

def log(msg: str):
    """Print logregel met tijdstempel"""
    now = datetime.now(timezone.utc).strftime("[%H:%M:%S]")
    print(f"{now} {msg}")

def parse_time(record, post):
    """Probeert de juiste datum/tijd te bepalen"""
    for attr in ["createdAt", "indexedAt", "created_at", "timestamp"]:
        val = getattr(record, attr, None) or getattr(post, attr, None)
        if val:
            try:
                return datetime.fromisoformat(val.replace("Z", "+00:00"))
            except Exception:
                continue
    return None

def load_done(path):
    if not os.path.exists(path):
        return set()
    with open(path, "r") as f:
        return set(line.strip() for line in f if line.strip())

def append_done(path, uri):
    with open(path, "a") as f:
        f.write(uri + "\n")

def main():
    username = os.environ["BSKY_USERNAME"]
    password = os.environ["BSKY_PASSWORD"]

    client = Client()
    client.login(username, password)
    log(f"✅ Ingelogd als {username}")

    # Ophalen lijst met gebruikers
    try:
        members = client.app.bsky.graph.get_list({"list": LIST_URI}).items
        log(f"📋 {len(members)} gebruikers gevonden.")
    except Exception as e:
        log(f"⚠️ Fout bij ophalen lijst: {e}")
        return

    repost_log = "reposted.txt"
    done = load_done(repost_log)
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=HOURS_BACK)

    all_posts = []

    # Feeds ophalen
    for member in members:
        handle = member.subject.handle
        log(f"🔎 Check feed @{handle}")
        try:
            feed = client.app.bsky.feed.get_author_feed({"actor": handle, "limit": 10})
            for item in feed.feed:
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

                created_dt = parse_time(record, post)
                if not created_dt or created_dt < cutoff_time:
                    continue

                all_posts.append({
                    "handle": handle,
                    "uri": uri,
                    "cid": cid,
                    "created": created_dt,
                })
        except Exception as e:
            log(f"⚠️ Fout bij ophalen feed @{handle}: {e}")

    log(f"🕒 {len(all_posts)} totale posts verzameld (voor filtering).")

    # Sorteer oudste eerst
    all_posts.sort(key=lambda x: x["created"])

    reposted = 0
    liked = 0
    per_user_count = {}
    posts_to_do = all_posts[:MAX_PER_RUN]

    log(f"📊 {len(posts_to_do)} posts na filtering, max {MAX_PER_RUN} zal gepost worden.")

    for post in posts_to_do:
        if reposted >= MAX_PER_RUN:
            break

        handle = post["handle"]
        uri = post["uri"]
        cid = post["cid"]

        if handle != EXEMPT_HANDLE:
            per_user_count[handle] = per_user_count.get(handle, 0)
            if per_user_count[handle] >= MAX_PER_USER:
                continue

        try:
            # Repost uitvoeren
            client.app.bsky.feed.repost.create(
                repo=client.me.did,
                record={
                    "subject": {"uri": uri, "cid": cid},
                    "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )
            append_done(repost_log, uri)
            done.add(uri)
            reposted += 1
            per_user_count[handle] = per_user_count.get(handle, 0) + 1
            log(f"🔁 Gerepost @{handle}: {uri}")
            time.sleep(2)

            # Like uitvoeren
            try:
                client.app.bsky.feed.like.create(
                    repo=client.me.did,
                    record={
                        "subject": {"uri": uri, "cid": cid},
                        "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    },
                )
                liked += 1
                log(f"❤️ Geliked @{handle}: {uri}")
                time.sleep(1)
            except Exception as e_like:
                log(f"⚠️ Fout bij liken @{handle}: {e_like}")

        except Exception as e:
            log(f"⚠️ Fout bij repost @{handle}: {e}")

    log(f"✅ Klaar met run! ({reposted} reposts, {liked} likes)")
    log(f"🧮 Samenvatting: {len(all_posts)} bekeken, {reposted} nieuw gerepost.")
    log(f"⏰ Run beëindigd om {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")

if __name__ == "__main__":
    main()