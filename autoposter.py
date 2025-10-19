from atproto import Client
import os
import time
from datetime import datetime, timedelta, timezone

# Bluesky-lijst waaruit wordt gepost
LIST_URI = "at://did:plc:jaka644beit3x4vmmg6yysw7/app.bsky.graph.list/3m3iga6wnmz2p"

# Gebruiker zonder repostlimiet
EXEMPT_HANDLE = "bleuskybeauty.bsky.social"

# Configuratie
MAX_PER_RUN = 50        # ← verhoogd van 25 naar 50
MAX_PER_USER = 5
DAYS_BACK = 7


def log(msg: str):
    """Print logregel met tijdstempel"""
    now = datetime.now(timezone.utc).strftime("[%H:%M:%S]")
    print(f"{now} {msg}")


def get_created_time(post):
    """Probeer op meerdere manieren de createdAt-tijd te vinden"""
    record = getattr(post, "record", None)
    if not record:
        return None

    # Probeer verschillende plekken waar createdAt kan staan
    created = (
        getattr(record, "createdAt", None)
        or getattr(post, "createdAt", None)
        or getattr(record, "value", {}).get("createdAt", None)
        or getattr(post.record, "value", {}).get("createdAt", None)
        or getattr(post, "indexedAt", None)
    )

    if not created:
        return None

    try:
        return datetime.fromisoformat(created.replace("Z", "+00:00"))
    except Exception:
        return None


def main():
    username = os.environ["BSKY_USERNAME"]
    password = os.environ["BSKY_PASSWORD"]

    client = Client()
    client.login(username, password)
    log(f"✅ Ingelogd als {username}")

    try:
        members = client.app.bsky.graph.get_list({"list": LIST_URI}).items
        log(f"📋 {len(members)} gebruikers gevonden.")
    except Exception as e:
        log(f"⚠️ Fout bij ophalen lijst: {e}")
        return

    # Repostlog laden
    repost_log = "reposted.txt"
    if os.path.exists(repost_log):
        with open(repost_log, "r") as f:
            done = set(f.read().splitlines())
    else:
        done = set()

    all_posts = []
    cutoff_time = datetime.now(timezone.utc) - timedelta(days=DAYS_BACK)

    # Posts verzamelen
    for member in members:
        handle = member.subject.handle
        log(f"🔎 Check feed @{handle}")

        try:
            feed = client.app.bsky.feed.get_author_feed({"actor": handle, "limit": 20})
            for item in feed.feed:
                post = item.post
                uri = post.uri
                cid = post.cid
                record = post.record

                # Skip reposts of replies
                if hasattr(item, "reason") and item.reason is not None:
                    log(f"  ⚪ @{handle} → SKIP: is repost ({uri})")
                    continue
                if getattr(record, "reply", None):
                    log(f"  ⚪ @{handle} → SKIP: is reply ({uri})")
                    continue
                if uri in done:
                    log(f"  ⚪ @{handle} → SKIP: al gerepost ({uri})")
                    continue

                created_dt = get_created_time(post)
                if not created_dt:
                    log(f"  ⚪ @{handle} → SKIP: geen tijd gevonden ({uri})")
                    continue

                if created_dt < cutoff_time:
                    log(f"  ⚪ @{handle} → SKIP: ouder dan {DAYS_BACK} dagen ({uri})")
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

    # Beperk tot max 50 per run
    posts_to_do = all_posts[:MAX_PER_RUN]
    log(f"📊 {len(posts_to_do)} posts geselecteerd voor repost (max {MAX_PER_RUN}).")

    reposted = 0
    liked = 0
    per_user_count = {}

    for post in posts_to_do:
        handle = post["handle"]
        uri = post["uri"]
        cid = post["cid"]

        if reposted >= MAX_PER_RUN:
            break

        if handle != EXEMPT_HANDLE:
            if per_user_count.get(handle, 0) >= MAX_PER_USER:
                log(f"  ⚪ @{handle} → limiet van {MAX_PER_USER} bereikt, overslaan.")
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
            per_user_count[handle] = per_user_count.get(handle, 0) + 1
            time.sleep(2)

            # Like
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

    # Repost-log bijwerken
    with open(repost_log, "w") as f:
        f.write("\n".join(done))

    log(f"✅ Klaar met run! ({reposted} reposts, {liked} likes)")
    log(f"🧮 Samenvatting: {len(all_posts)} bekeken, {reposted} nieuw gerepost.")
    log(f"⏰ Run beëindigd om {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")

if __name__ == "__main__":
    main()