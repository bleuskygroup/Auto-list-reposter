from atproto import Client
import os
import time
from datetime import datetime

LIST_URI = "at://did:plc:jaka644beit3x4vmmg6yysw7/app.bsky.graph.list/3m3iga6wnmz2p"
EXEMPT_HANDLE = "bleuskybeauty.bsky.social"
REPOST_LOG = "reposted.txt"
MAX_TOTAL_REPOSTS = 25


def log(msg: str):
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


def has_media(post):
    """Controleer of post afbeeldingen of video's bevat, ook nested."""
    embed = getattr(post.post, "embed", None)
    if not embed:
        return False

    t = getattr(embed, "$type", "")
    if "app.bsky.embed.images" in t or "app.bsky.embed.video" in t:
        return True

    if t == "app.bsky.embed.recordWithMedia":
        media = getattr(embed, "media", None)
        if media and (
            "app.bsky.embed.images" in getattr(media, "$type", "")
            or "app.bsky.embed.video" in getattr(media, "$type", "")
        ):
            return True
    return False


def get_timestamp(post):
    """Gebruik createdAt of fallback naar indexedAt"""
    record = getattr(post.post, "record", None)
    if record and hasattr(record, "createdAt"):
        return record.createdAt
    return getattr(post.post, "indexedAt", None)


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

    done = load_log()
    all_posts = []

    # Verzamel posts per gebruiker
    for member in members:
        handle = member.subject.handle
        try:
            feed = client.app.bsky.feed.get_author_feed({
                "actor": handle,
                "limit": 10
            })
            for post in feed.feed:
                record = post.post.record

                created_at = get_timestamp(post)
                if not created_at:
                    log(f"⚠️ Geen tijd gevonden voor @{handle}, skip.")
                    continue

                # Sla reposts of replies over
                if hasattr(post, "reason") and post.reason is not None:
                    log(f"↩️ Repost @{handle}, overslaan.")
                    continue
                if getattr(record, "reply", None):
                    log(f"💬 Reply @{handle}, overslaan.")
                    continue

                # Controleer media
                if not has_media(post):
                    log(f"📄 Geen media @{handle}, overslaan.")
                    continue

                all_posts.append({
                    "handle": handle,
                    "uri": post.post.uri,
                    "cid": post.post.cid,
                    "created_at": created_at
                })
        except Exception as e:
            log(f"⚠️ Fout bij ophalen feed @{handle}: {e}")

    log(f"🕒 {len(all_posts)} totale posts verzameld (na filtering).")

    # Sorteer nieuwste eerst
    all_posts.sort(key=lambda p: p["created_at"], reverse=True)

    done_this_run = set()
    total_reposts = 0
    total_likes = 0
    per_user_count = {}

    for p in all_posts:
        if total_reposts >= MAX_TOTAL_REPOSTS:
            log(f"🚫 Maximaal {MAX_TOTAL_REPOSTS} reposts bereikt. Stop run.")
            break

        handle, uri, cid = p["handle"], p["uri"], p["cid"]

        if uri in done or uri in done_this_run:
            continue

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