from atproto import Client
import os
import time
import random
from datetime import datetime, timedelta

# --- Instellingen ---
LIST_URI = "at://did:plc:jaka644beit3x4vmmg6yysw7/app.bsky.graph.list/3m3iga6wnmz2p"
EXEMPT_HANDLE = "bleuskybeauty.bsky.social"
MAX_PER_USER = 5
MAX_TOTAL = 25
MAX_AGE_DAYS = 7


# --- Hulpfuncties ---
def log(msg: str):
    """Voeg tijd toe aan elke logregel"""
    now = datetime.utcnow().strftime("[%H:%M:%S]")
    print(f"{now} {msg}")


def sleep_random(min_s=2, max_s=5):
    """Willekeurige vertraging om spam te voorkomen"""
    delay = random.uniform(min_s, max_s)
    time.sleep(delay)


# --- Hoofdprogramma ---
def main():
    username = os.environ["BSKY_USERNAME"]
    password = os.environ["BSKY_PASSWORD"]

    client = Client()
    client.login(username, password)
    log(f"✅ Ingelogd als {username}")

    # Lijst ophalen
    try:
        members = client.app.bsky.graph.get_list({"list": LIST_URI}).items
        log(f"📋 {len(members)} gebruikers gevonden.")
    except Exception as e:
        log(f"⚠️ Fout bij ophalen lijst: {e}")
        return

    # Repost-logbestand bijhouden
    repost_log = "reposted.txt"
    if os.path.exists(repost_log):
        with open(repost_log, "r") as f:
            done = set(f.read().splitlines())
    else:
        done = set()

    all_posts = []
    total_checked = 0
    cutoff = datetime.utcnow() - timedelta(days=MAX_AGE_DAYS)

    # --- Feeds ophalen ---
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

                created_at = getattr(record, "createdAt", None) or getattr(post.post, "indexedAt", None)
                if not created_at:
                    continue

                # Parse tijd
                try:
                    post_time = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%S.%fZ")
                except ValueError:
                    try:
                        post_time = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ")
                    except Exception:
                        continue

                # Skip oude posts (>7 dagen)
                if post_time < cutoff:
                    continue

                # Skip reposts of replies
                if hasattr(post, "reason") and post.reason:
                    continue
                if getattr(record, "reply", None):
                    continue

                # Voeg toe aan verzamel-lijst
                all_posts.append({
                    "handle": handle,
                    "uri": post.post.uri,
                    "cid": post.post.cid,
                    "created_at": post_time
                })

            # Kleine pauze tussen gebruikersfeeds
            sleep_random(3, 6)

        except Exception as e:
            log(f"⚠️ Fout bij ophalen feed @{handle}: {e}")

    log(f"🕒 {total_checked} totale posts bekeken (voor filtering).")

    # Sorteer op tijd: oudste eerst (zodat nieuwe posts bovenaan verschijnen op tijdlijn)
    all_posts.sort(key=lambda p: p["created_at"])

    # Filter reeds gereposte posts
    new_posts = [p for p in all_posts if p["uri"] not in done]
    log(f"📊 {len(new_posts)} posts na filtering, max {MAX_TOTAL} zal gepost worden.")

    total_reposts = 0
    total_likes = 0
    posted_uris = set()

    # --- Repost & Like ---
    for post in new_posts:
        if total_reposts >= MAX_TOTAL:
            break

        handle = post["handle"]
        uri = post["uri"]
        cid = post["cid"]

        # Max per gebruiker
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
            sleep_random()

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
                sleep_random()
            except Exception as e_like:
                log(f"⚠️ Fout bij liken @{handle}: {e_like}")

        except Exception as e:
            log(f"⚠️ Fout bij repost @{handle}: {e}")

    # Logbestand bijwerken
    with open(repost_log, "w") as f:
        f.write("\n".join(done))

    # Samenvatting
    log(f"✅ Klaar met run! ({total_reposts} reposts, {total_likes} likes)")
    log(f"🧮 Samenvatting: {total_checked} bekeken, {len(new_posts)} nieuw, {total_reposts} gerepost.")
    log(f"⏰ Run beëindigd om {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")

# --- Start ---
if __name__ == "__main__":
    main()