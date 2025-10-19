from atproto import Client
import os
import time
from datetime import datetime, timedelta

# Bluesky-lijst (waaruit gerepost wordt)
LIST_URI = "at://did:plc:jaka644beit3x4vmmg6yysw7/app.bsky.graph.list/3m3iga6wnmz2p"

# Gebruiker zonder repostlimiet
EXEMPT_HANDLE = "bleuskybeauty.bsky.social"

# Configuratie
MAX_PER_USER = 5       # max aantal reposts per gebruiker per run
MAX_TOTAL = 25         # max totaal per run
MAX_AGE_DAYS = 7       # posts ouder dan 7 dagen overslaan


def log(msg: str):
    """Tijdstempel bij elke logregel"""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{now}] {msg}")


def main():
    username = os.environ["BSKY_USERNAME"]
    password = os.environ["BSKY_PASSWORD"]

    client = Client()
    client.login(username, password)
    log(f"✅ Ingelogd als: {username}")

    try:
        members = client.app.bsky.graph.get_list({"list": LIST_URI}).items
        log(f"📋 {len(members)} gebruikers in lijst gevonden.")
    except Exception as e:
        log(f"⚠️ Fout bij ophalen lijst: {e}")
        return

    # gelezen reposts
    repost_log = "reposted.txt"
    if os.path.exists(repost_log):
        with open(repost_log, "r") as f:
            done = set(f.read().splitlines())
    else:
        done = set()

    all_posts = []
    now = datetime.utcnow()

    # Verzamel recente posts van alle leden
    for member in members:
        handle = member.subject.handle
        try:
            feed = client.app.bsky.feed.get_author_feed({"actor": handle, "limit": 10})
            for item in feed.feed:
                post = item.post
                record = post.record
                uri = post.uri
                cid = post.cid

                # Sla reposts en replies over
                if hasattr(item, "reason") and item.reason is not None:
                    continue
                if getattr(record, "reply", None):
                    continue

                # Tijd van post
                created_at = getattr(record, "createdAt", None) or getattr(post, "indexed_at", None)
                if not created_at:
                    continue

                try:
                    created_dt = datetime.strptime(created_at[:19], "%Y-%m-%dT%H:%M:%S")
                except Exception:
                    continue

                # Alleen jonger dan 7 dagen
                if (now - created_dt) > timedelta(days=MAX_AGE_DAYS):
                    continue

                # Sla reeds geposte over
                if uri in done:
                    continue

                all_posts.append({
                    "handle": handle,
                    "uri": uri,
                    "cid": cid,
                    "created_at": created_dt
                })
        except Exception:
            continue

    # Sorteer op tijd (nieuwste eerst)
    all_posts.sort(key=lambda p: p["created_at"], reverse=True)

    reposted_total = 0
    liked_total = 0
    user_count = {}

    for post in all_posts:
        if reposted_total >= MAX_TOTAL:
            break

        handle = post["handle"]
        uri = post["uri"]
        cid = post["cid"]

        if handle != EXEMPT_HANDLE:
            user_count.setdefault(handle, 0)
            if user_count[handle] >= MAX_PER_USER:
                continue

        try:
            client.app.bsky.feed.repost.create(
                repo=client.me.did,
                record={
                    "subject": {"uri": uri, "cid": cid},
                    "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                }
            )
            log(f"🔁 Gerepost @{handle}")
            done.add(uri)
            reposted_total += 1
            user_count[handle] = user_count.get(handle, 0) + 1
            time.sleep(2)

            # Like
            try:
                client.app.bsky.feed.like.create(
                    repo=client.me.did,
                    record={
                        "subject": {"uri": uri, "cid": cid},
                        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    }
                )
                log(f"❤️ Geliked @{handle}")
                liked_total += 1
                time.sleep(1)
            except Exception:
                pass

        except Exception:
            continue

    # Update logbestand
    with open(repost_log, "w") as f:
        f.write("\n".join(done))

    log(f"✅ Klaar met run! ({reposted_total} reposts, {liked_total} likes)")
    log(f"⏰ Run beëindigd om {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")


if __name__ == "__main__":
    main()