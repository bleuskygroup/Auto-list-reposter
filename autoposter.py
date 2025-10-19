from atproto import Client
import os
import time
from datetime import datetime

# Configuratie
LIST_URI = "at://did:plc:jaka644beit3x4vmmg6yysw7/app.bsky.graph.list/3m3iga6wnmz2p"
EXEMPT_HANDLE = "bleuskybeauty.bsky.social"
REPOST_LOG = "reposted.txt"

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
        log(f"🔎 Controleer media van @{handle}")

        try:
            # Alleen de mediaposts van gebruiker zelf (zoals tabblad “Media”)
            feed = client.app.bsky.feed.get_author_feed({
                "actor": handle,
                "limit": 10,
                "filter": "posts_with_media"
            })

            posts = list(feed.feed)
            posts.reverse()  # van oud naar nieuw

            reposted_this_user = 0
            user_limit = 5 if handle != EXEMPT_HANDLE else float("inf")

            for post in posts:
                record = post.post.record
                uri = post.post.uri
                cid = post.post.cid

                # Geen reposts of replies
                if hasattr(post, "reason") and post.reason is not None:
                    continue
                if getattr(record, "reply", None):
                    continue

                # Dubbele check
                if uri in done or uri in posted_this_run:
                    continue

                try:
                    # Repost uitvoeren
                    client.app.bsky.feed.repost.create(
                        repo=client.me.did,
                        record={
                            "subject": {"uri": uri, "cid": cid},
                            "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        },
                    )
                    log(f"🟦 Gerepost @{handle}: {uri}")
                    done.add(uri)
                    posted_this_run.add(uri)
                    reposted_this_user += 1
                    total_reposts += 1
                    time.sleep(2)

                    # Like uitvoeren
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

                # Stop na 5 per gebruiker
                if reposted_this_user >= user_limit:
                    break

        except Exception as e:
            log(f"⚠️ Fout bij ophalen feed @{handle}: {e}")

    save_log(done)
    log(f"✅ Klaar met run! ({total_reposts} reposts, {total_likes} likes)")
    log(f"⏰ Run beëindigd om {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")

if __name__ == "__main__":
    main()