from atproto import Client
import os
import time
from datetime import datetime, timedelta

# Bluesky-lijst (waaruit gerepost wordt)
LIST_URI = "at://did:plc:jaka644beit3x4vmmg6yysw7/app.bsky.graph.list/3m3iga6wnmz2p"

# Gebruiker zonder limiet
EXEMPT_HANDLE = "bleuskybeauty.bsky.social"

# Limieten
MAX_PER_USER = 5
MAX_TOTAL = 25
MAX_AGE_DAYS = 7

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

    all_posts = []
    total_checked = 0

    cutoff = datetime.utcnow() - timedelta(days=MAX_AGE_DAYS)

    # Verzamel posts van alle gebruikers
    for member in members:
        handle = member.subject.handle
        log(f"🔎 Check feed @{handle}")
        try:
            feed = client.app.bsky.feed.get_author_feed({"actor": handle, "limit": 10})
            for post in feed.feed:
                total_checked += 1

                record = getattr(post.post, "record", None)
                if not record:
                    continue

                # Tijd bepalen
                created_at = getattr(record, "createdAt", None) or getattr(post.post, "indexedAt", None)
                if not created_at:
                    continue

                try:
                    post_time = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%S.%fZ")
                except ValueError:
                    try:
                        post_time = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ")
                    except Exception:
                        continue

                # Skip oude posts
                if post_time < cutoff:
                    continue

                # Skip reposts of replies
                if hasattr(post, "reason") and post.reason:
                    continue
                if getattr(record, "reply", None):
                    continue

                # Voeg toe aan lijst
                all_posts.append({
                    "handle": handle,
                    "uri": post.post.uri,
                    "cid": post.post.cid,
                    "created_at": post_time
                })
        except Exception as e:
            log(f"⚠️ Fout bij ophalen feed @{handle}: {e}")

    log(f"🕒 {total_checked} totale posts bekeken (voor filtering).")

    # Sorteer op tijd: oudste eerst
    all_posts.sort(key=lambda p: p["created_at"])

    # Filter reposts al gedaan
    new_posts = [p for p in all_posts if p["uri"] not in done]

    log(f"📊 {len(new_posts)} posts na filtering, max {MAX_TOTAL} zal gepost worden.")

    total_reposts = 0
    total_likes = 0
    posted_uris = set()

    for post in new_posts:
        if total_reposts >= MAX_TOTAL:
            break

        handle = post["handle"]
        uri = post["uri"]
        cid = post["cid"]

        # Tel per gebruiker
        if handle != EXEMPT_HANDLE:
            user_count = sum(1 for p in posted_uris if p.startswith(handle))
            if user_count >= MAX_PER_USER:
                continue

        try:
            # Repost
            client.app.bsky.feed.repost.create(
                repo=client.me.did,
                record={
                    "subject": {"uri": uri, "cid": cid},
                    "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                }
            )
            log(f"🔁 Gerepost @{handle}: {uri}")
            total_reposts += 1
            done.add(uri)
            posted_uris.add(f"{handle}:{uri}")
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

    # Logbestand bijwerken
    with open(repost_log, "w") as f:
        f.write("\n".join(done))

    log(f"✅ Klaar met run! ({total_reposts} reposts, {total_likes} likes)")
    log(f"🧮 Samenvatting: {total_checked} bekeken, {len(new_posts)} nieuw, {total_reposts} gerepost.")
    log(f"⏰ Run beëindigd om {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")

if __name__ == "__main__":
    main()