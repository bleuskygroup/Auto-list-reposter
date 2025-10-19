from atproto import Client
import os
import time
from datetime import datetime

# Configuratie
LIST_URI = "at://did:plc:jaka644beit3x4vmmg6yysw7/app.bsky.graph.list/3m3iga6wnmz2p"
EXEMPT_HANDLE = "bleuskybeauty.bsky.social"
REPOST_LOG = "reposted.txt"
MAX_TOTAL_REPOSTS = 25  # ⬅️ max aantal reposts per run


def log(msg: str):
    """Logt berichten met UTC-tijd."""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{now}] {msg}")


def load_log():
    if os.path.exists(REPOST_LOG):
        with open(REPOST_LOG, "r") as f:
            return set(f.read().splitlines())
    return set()


def save_log(done):
    with open(REPOST_LOG, "w") as f:
        f.write("\n".join(done))


def get_created_at(post):
    """Probeer createdAt te lezen uit post.record"""
    try:
        return getattr(post.post.record, "createdAt", None)
    except Exception:
        return None


def main():
    username = os.environ["BSKY_USERNAME"]
    password = os.environ["BSKY_PASSWORD"]

    client = Client()
    client.login(username, password)
    log(f"✅ Ingelogd als: {username}")

    # Lijst ophalen
    try:
        members = client.app.bsky.graph.get_list({"list": LIST_URI}).items
        log(f"📋 {len(members)} gebruikers in lijst gevonden.")
    except Exception as e:
        log(f"⚠️ Fout bij ophalen lijst: {e}")
        return

    done = load_log()
    all_posts = []

    # Verzamel eerst ALLE posts uit alle gebruikers
    for member in members:
        handle = member.subject.handle
        try:
            feed = client.app.bsky.feed.get_author_feed({
                "actor": handle,
                "limit": 10,
                "filter": "posts_with_media"
            })
            for post in feed.feed:
                record = post.post.record
                created_at = get_created_at(post)
                if not created_at:
                    continue
                # Alleen originele mediaposts
                if hasattr(post, "reason") and post.reason is not None:
                    continue
                if getattr(record, "reply", None):
                    continue
                all_posts.append({
                    "handle": handle,
                    "uri": post.post.uri,
                    "cid": post.post.cid,
                    "created_at": created_at
                })
        except Exception as e:
            log(f"⚠️ Fout bij ophalen feed @{handle}: {e}")

    log(f"🕒 {len(all_posts)} totale posts verzameld.")

    # Sorteer posts op tijd — nieuwste eerst
    all_posts.sort(key=lambda p: p["created_at"], reverse=True)

    done_this_run = set()
    total_reposts = 0
    total_likes = 0
    per_user_count = {}

    for p in all_posts:
        if total_reposts >= MAX_TOTAL_REPOSTS:
            log(f"🚫 Maximaal {MAX_TOTAL_REPOSTS} reposts bereikt. Stop run.")
            break

        handle = p["handle"]
        uri = p["uri"]
        cid = p["cid"]

        # Skip als al gedaan
        if uri in done or uri in done_this_run:
            continue

        # Limiet per gebruiker
        count = per_user_count.get(handle, 0)
        limit = 5 if handle != EXEMPT_HANDLE else float("inf")
        if count >= limit:
            continue

        try:
            client.app.bsky.feed.repost.create(
                repo=client.me.did,
                record={
                    "subject": {"uri": uri, "cid": cid},
                    "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                }
            )
            log(f"🟦 Gerepost @{handle}: {uri}")
            done.add(uri)
            done_this_run.add(uri)
            per_user_count[handle] = count + 1
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
                log(f"❤️ Geliked @{handle}")
                total_likes += 1
                time.sleep(1)
            except Exception as e_like:
                log(f"⚠️ Fout bij liken @{handle}: {e_like}")

        except Exception as e:
            log(f"⚠️ Fout bij repost @{handle}: {e}")

    save_log(done)
    log(f"✅ Klaar met run! ({total_reposts} reposts, {total_likes} likes)")
    log(f"⏰ Run beëindigd om {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")


if __name__ == "__main__":
    main()