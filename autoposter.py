from atproto import Client
import os
import time
from datetime import datetime, timedelta

# Bluesky-lijst (waaruit gerepost wordt)
LIST_URI = "at://did:plc:jaka644beit3x4vmmg6yysw7/app.bsky.graph.list/3m3iga6wnmz2p"

# Gebruiker zonder repostlimiet
EXEMPT_HANDLE = "bleuskybeauty.bsky.social"

# Maximale ouderdom van posts (in dagen)
MAX_AGE_DAYS = 30

# Instellingen
MAX_PER_USER = 5
MAX_TOTAL = 25


def log(msg: str):
    """Voeg tijd toe aan elke logregel"""
    now = datetime.utcnow().strftime("[%H:%M:%S]")
    print(f"{now} {msg}")


def main():
    username = os.environ["BSKY_USERNAME"]
    password = os.environ["BSKY_PASSWORD"]

    client = Client()
    client.login(username, password)
    log(f"✅ Ingelogd als {username}")

    # lijst ophalen
    try:
        members = client.app.bsky.graph.get_list({"list": LIST_URI}).items
        log(f"📋 {len(members)} gebruikers gevonden.")
    except Exception as e:
        log(f"⚠️ Fout bij ophalen lijst: {e}")
        return

    repost_log = "reposted.txt"
    if os.path.exists(repost_log):
        with open(repost_log, "r") as f:
            done = set(f.read().splitlines())
    else:
        done = set()

    cutoff = datetime.utcnow() - timedelta(days=MAX_AGE_DAYS)
    all_posts = []

    # Verzamel posts van alle gebruikers
    for member in members:
        handle = member.subject.handle
        log(f"🔎 Check feed @{handle}")

        try:
            feed = client.app.bsky.feed.get_author_feed({"actor": handle, "limit": 10})
            for post in feed.feed:
                record = post.post.record
                uri = post.post.uri
                cid = post.post.cid
                created = getattr(record, "created_at", None) or getattr(post.post, "indexed_at", None)

                # Check tijd
                if not created:
                    continue
                try:
                    created_time = datetime.strptime(created.replace("Z", ""), "%Y-%m-%dT%H:%M:%S.%f")
                except:
                    try:
                        created_time = datetime.strptime(created.replace("Z", ""), "%Y-%m-%dT%H:%M:%S")
                    except:
                        continue

                if created_time < cutoff:
                    continue

                # Skip reposts, replies of dubbele
                if hasattr(post, "reason") and post.reason:
                    continue
                if getattr(record, "reply", None):
                    continue
                if uri in done:
                    continue

                all_posts.append({
                    "handle": handle,
                    "uri": uri,
                    "cid": cid,
                    "created": created_time
                })
        except Exception as e:
            log(f"⚠️ Fout bij ophalen feed @{handle}: {e}")

    # Sorteren op tijd (nieuwste eerst)
    all_posts.sort(key=lambda x: x["created"], reverse=True)

    total_reposts = 0
    total_likes = 0
    reposted_handles = {}

    for post in all_posts:
        if total_reposts >= MAX_TOTAL:
            break

        handle = post["handle"]
        uri = post["uri"]
        cid = post["cid"]

        if handle != EXEMPT_HANDLE:
            reposted_handles.setdefault(handle, 0)
            if reposted_handles[handle] >= MAX_PER_USER:
                continue

        try:
            client.app.bsky.feed.repost.create(
                repo=client.me.did,
                record={
                    "subject": {"uri": uri, "cid": cid},
                    "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                }
            )
            log(f"🔁 Gerepost @{handle}: {uri}")
            done.add(uri)
            reposted_handles[handle] = reposted_handles.get(handle, 0) + 1
            total_reposts += 1
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
                log(f"❤️ Geliked @{handle}: {uri}")
                total_likes += 1
                time.sleep(1)
            except Exception as e_like:
                log(f"⚠️ Fout bij liken @{handle}: {e_like}")

        except Exception as e:
            log(f"⚠️ Fout bij repost @{handle}: {e}")

    # Opslaan
    with open(repost_log, "w") as f:
        f.write("\n".join(done))

    log(f"✅ Klaar met run! ({total_reposts} reposts, {total_likes} likes)")
    log(f"⏰ Run beëindigd om {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")


if __name__ == "__main__":
    main()