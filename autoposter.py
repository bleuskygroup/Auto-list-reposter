from atproto import Client
import os
import time
from datetime import datetime, timedelta

# Bluesky-lijst (waaruit gerepost wordt)
LIST_URI = "at://did:plc:jaka644beit3x4vmmg6yysw7/app.bsky.graph.list/3m3iga6wnmz2p"

# Gebruiker zonder repostlimiet
EXEMPT_HANDLE = "bleuskybeauty.bsky.social"

# Instellingen
MAX_REPOSTS_PER_USER = 5
MAX_REPOSTS_TOTAL = 25
DAYS_BACK = 7

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

    # Leden van lijst ophalen
    members = client.app.bsky.graph.get_list({"list": LIST_URI}).items
    log(f"📋 {len(members)} gebruikers gevonden.")

    # Logbestand voor reeds gereposte posts
    repost_log = "reposted.txt"
    done = set()
    if os.path.exists(repost_log):
        with open(repost_log, "r") as f:
            done = set(f.read().splitlines())

    all_posts = []
    cutoff_time = datetime.utcnow() - timedelta(days=DAYS_BACK)

    # Feeds ophalen van elk lid
    for member in members:
        handle = member.subject.handle
        log(f"🔎 Check feed @{handle}")

        try:
            feed = client.app.bsky.feed.get_author_feed({"actor": handle, "limit": 10})
            for post in feed.feed:
                record = post.post.record
                uri = post.post.uri
                cid = post.post.cid
                created = getattr(record, "createdAt", None)
                indexed = getattr(post.post, "indexedAt", None)
                created_time = None

                if created:
                    created_time = datetime.fromisoformat(created.replace("Z", "+00:00"))
                elif indexed:
                    created_time = datetime.fromisoformat(indexed.replace("Z", "+00:00"))

                if not created_time or created_time < cutoff_time:
                    continue

                # Alleen originele posts (geen replies/reposts)
                if hasattr(post, "reason") and post.reason:
                    continue
                if getattr(record, "reply", None):
                    continue

                all_posts.append({
                    "handle": handle,
                    "uri": uri,
                    "cid": cid,
                    "created": created_time,
                })

        except Exception as e:
            log(f"⚠️ Fout bij ophalen feed @{handle}: {e}")

    if not all_posts:
        log("🚫 Geen nieuwe posts gevonden.")
        return

    # Sorteren op tijd — nieuwste bovenaan
    all_posts.sort(key=lambda x: x["created"])

    reposted_total = 0
    per_user = {}

    for post in all_posts:
        if reposted_total >= MAX_REPOSTS_TOTAL:
            break

        handle = post["handle"]
        uri = post["uri"]
        cid = post["cid"]

        if uri in done:
            continue

        if handle != EXEMPT_HANDLE:
            per_user.setdefault(handle, 0)
            if per_user[handle] >= MAX_REPOSTS_PER_USER:
                continue

        # Repost uitvoeren
        try:
            client.app.bsky.feed.repost.create(
                repo=client.me.did,
                record={
                    "subject": {"uri": uri, "cid": cid},
                    "createdAt": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                }
            )
            log(f"🔁 Gerepost @{handle}: {uri}")
            done.add(uri)
            reposted_total += 1
            per_user[handle] = per_user.get(handle, 0) + 1
            time.sleep(2)

            # Like uitvoeren
            try:
                client.app.bsky.feed.like.create(
                    repo=client.me.did,
                    record={
                        "subject": {"uri": uri, "cid": cid},
                        "createdAt": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                    }
                )
                log(f"❤️ Geliked @{handle}: {uri}")
                time.sleep(1)
            except Exception as e_like:
                log(f"⚠️ Fout bij liken @{handle}: {e_like}")

        except Exception as e:
            log(f"⚠️ Fout bij repost @{handle}: {e}")

    # Logbestand bijwerken
    with open(repost_log, "w") as f:
        f.write("\n".join(done))

    log(f"✅ Klaar met run! ({reposted_total} reposts uitgevoerd)")
    log(f"⏰ Run beëindigd om {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")

if __name__ == "__main__":
    main()