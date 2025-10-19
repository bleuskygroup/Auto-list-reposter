from atproto import Client
import os
import time
from datetime import datetime, timedelta

LIST_URI = "at://did:plc:jaka644beit3x4vmmg6yysw7/app.bsky.graph.list/3m3iga6wnmz2p"
EXEMPT_HANDLE = "bleuskybeauty.bsky.social"

MAX_POSTS_PER_RUN = 25
MAX_PER_USER = 5
MAX_AGE_DAYS = 7


def log(msg: str):
    print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] {msg}")


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

    posts_to_check = []
    cutoff = datetime.utcnow() - timedelta(days=MAX_AGE_DAYS)

    for member in members:
        handle = member.subject.handle
        log(f"🔎 Check feed @{handle}")

        try:
            feed = client.app.bsky.feed.get_author_feed({"actor": handle, "limit": 10})
        except Exception as e:
            log(f"⚠️ Fout bij ophalen feed @{handle}: {e}")
            continue

        for post in feed.feed:
            record = post.post.record
            if hasattr(post, "reason") and post.reason is not None:
                continue
            if getattr(record, "reply", None):
                continue

            uri = post.post.uri
            cid = post.post.cid
            created_at = getattr(record, "createdAt", None)
            indexed_at = getattr(post.post, "indexed_at", None)

            # Gebruik indexed_at als createdAt ontbreekt
            ts = indexed_at or created_at
            if not ts:
                continue
            try:
                dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%fZ")
            except Exception:
                continue

            if dt < cutoff:
                continue

            # Alleen posts met media (foto of video)
            embed = getattr(post.post, "embed", None)
            has_media = False
            if embed and hasattr(embed, "images"):
                has_media = True
            elif embed and hasattr(embed, "media"):
                has_media = True
            if not has_media:
                continue

            posts_to_check.append((dt, handle, uri, cid))

    # Sorteer alle posts op tijd — nieuwste eerst
    posts_to_check.sort(reverse=True, key=lambda x: x[0])
    log(f"🕒 {len(posts_to_check)} totale posts verzameld (voor filtering).")

    reposted = 0
    liked = 0
    user_counts = {}

    for dt, handle, uri, cid in posts_to_check[:MAX_POSTS_PER_RUN]:
        limit = MAX_PER_USER if handle != EXEMPT_HANDLE else 9999
        user_counts.setdefault(handle, 0)
        if user_counts[handle] >= limit:
            continue

        try:
            client.app.bsky.feed.repost.create(
                repo=client.me.did,
                record={
                    "subject": {"uri": uri, "cid": cid},
                    "createdAt": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )
            log(f"🔁 Gerepost @{handle}: {uri}")
            reposted += 1
            user_counts[handle] += 1
            time.sleep(2)

            try:
                client.app.bsky.feed.like.create(
                    repo=client.me.did,
                    record={
                        "subject": {"uri": uri, "cid": cid},
                        "createdAt": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                    },
                )
                log(f"❤️ Geliked @{handle}: {uri}")
                liked += 1
                time.sleep(1)
            except Exception as e_like:
                log(f"⚠️ Fout bij liken @{handle}: {e_like}")

        except Exception as e:
            log(f"⚠️ Fout bij repost @{handle}: {e}")

    log(f"✅ Klaar met run! ({reposted} reposts, {liked} likes)")
    log(f"⏰ Run beëindigd om {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")


if __name__ == "__main__":
    main()