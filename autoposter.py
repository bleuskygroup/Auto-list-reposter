from atproto import Client
import os
import time
from datetime import datetime

# === Config ===
LIST_URI = "at://did:plc:jaka644beit3x4vmmg6yysw7/app.bsky.graph.list/3m3iga6wnmz2p"
EXEMPT_HANDLE = "bleuskybeauty.bsky.social"
REPOST_LOG = "reposted.txt"


def log(msg: str):
    """Log met tijdstempel (UTC)."""
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
    """Check of post een foto of video bevat."""
    embed = getattr(post.post, "embed", None)
    if not embed:
        return False

    embed_type = getattr(embed, "$type", "")
    if "app.bsky.embed.images" in embed_type or "app.bsky.embed.video" in embed_type:
        return True

    if embed_type == "app.bsky.embed.recordWithMedia":
        media = getattr(embed, "media", None)
        if media and (
            "app.bsky.embed.images" in getattr(media, "$type", "") or
            "app.bsky.embed.video" in getattr(media, "$type", "")
        ):
            return True

    return False


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
    posted_this_run = set()
    total_reposts = 0
    total_likes = 0

    for member in members:
        handle = member.subject.handle
        log(f"🔎 Controleer posts van @{handle}")

        try:
            feed = client.app.bsky.feed.get_author_feed({"actor": handle, "limit": 5})
            posts = list(feed.feed)
            posts.reverse()  # van oud naar nieuw

            reposted_this_user = 0
            user_limit = 3 if handle != EXEMPT_HANDLE else float("inf")

            for post in posts:
                record = post.post.record
                uri = post.post.uri
                cid = post.post.cid

                # Skip als het een repost of reply is
                if hasattr(post, "reason") and post.reason is not None:
                    continue
                if getattr(record, "reply", None):
                    continue

                # Alleen media
                if not has_media(post):
                    continue

                # Als al gerepost → overslaan
                if uri in done or uri in posted_this_run:
                    continue

                # Reposten
                try:
                    client.app.bsky.feed.repost.create(
                        repo=client.me.did,
                        record={
                            "subject": {"uri": uri, "cid": cid},
                            "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        },
                    )
                    log(f"🔁 Gerepost @{handle}: {uri}")
                    done.add(uri)
                    posted_this_run.add(uri)
                    reposted_this_user += 1
                    total_reposts += 1
                    time.sleep(2)

                    # Like
                    try:
                        client.app.bsky.feed.like.create(
                            repo=client.me.did,
                            record={
                                "subject": {"uri": uri, "cid": cid},
                                "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            },
                        )
                        log(f"❤️ Geliked @{handle}")
                        total_likes += 1
                        time.sleep(1)
                    except Exception as e_like:
                        log(f"⚠️ Fout bij liken @{handle}: {e_like}")

                except Exception as e:
                    log(f"⚠️ Fout bij repost @{handle}: {e}")

                if reposted_this_user >= user_limit:
                    break

        except Exception as e:
            log(f"⚠️ Fout bij ophalen feed @{handle}: {e}")

    save_log(done)
    log(f"✅ Klaar met run! ({total_reposts} reposts, {total_likes} likes)")
    log(f"⏰ Run beëindigd om {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")


if __name__ == "__main__":
    main()