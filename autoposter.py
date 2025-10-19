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
HOURS_BACK = 4  # ⏰ Alleen posts van de laatste 4 uur

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

    # Repostlog laden
    repost_log = "reposted.txt"
    done = set()
    if os.path.exists(repost_log):
        with open(repost_log, "r") as f:
            done = set(f.read().splitlines())

    all_posts = []
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=HOURS_BACK)

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

                # Reposts en replies overslaan
                if hasattr(item, "reason") and item.reason is not None:
                    continue
                if getattr(record, "reply", None):
                    continue

                # Skip dubbele of eerder geposte
                if uri in done:
                    continue

                # Tijd ophalen
                created_dt = parse_time(record, post)
                if not created_dt:
                    log(f"   ⚪ @{handle} → SKIP: geen tijd gevonden ({uri})")
                    continue

                # Filter op datum
                if created_dt < cutoff_time:
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

    # Sorteer op tijd (oudste eerst)
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

        # Per-gebruiker limiet
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
            log(f"🔁 Gerepost @{handle}: {uri}")
            done.add(uri)
            reposted += 1
            per_user_count[handle] = per_user_count.get(handle, 0) + 1
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
                log(f"❤️ Geliked @{handle}: {uri}")
                liked += 1
                time.sleep(1)
            except Exception as e_like:
                log(f"⚠️ Fout bij liken @{handle}: {e_like}")

        except Exception as e:
            log(f"⚠️ Fout bij repost @{handle}: {e}")

    # Logbestand bijwerken
    with open(repost_log, "w") as f:
        f.write("\n".join(done))

    log(f"✅ Klaar met run! ({reposted} reposts, {liked} likes)")
    log(f"🧮 Samenvatting: {len(all_posts)} bekeken, {reposted} nieuw gerepost.")
    log(f"⏰ Run beëindigd om {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")

if __name__ == "__main__":
    main()