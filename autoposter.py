from atproto import Client
import os
import time
from datetime import datetime

# 🔹 Bluesky-lijst waaruit gerepost wordt
LIST_URI = "at://did:plc:jaka644beit3x4vmmg6yysw7/app.bsky.graph.list/3m3iga6wnmz2p"

# 🔹 Account zonder repostlimiet
EXEMPT_HANDLE = "bleuskybeauty.bsky.social"


def log(msg: str):
    """Logregel met tijdstempel (UTC)."""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{now}] {msg}")


def main():
    username = os.environ["BSKY_USERNAME"]
    password = os.environ["BSKY_PASSWORD"]

    client = Client()
    client.login(username, password)
    log(f"✅ Ingelogd als: {username}")

    # ▪️ Lijst ophalen
    try:
        members = client.app.bsky.graph.get_list({"list": LIST_URI}).items
        log(f"📋 {len(members)} gebruikers in lijst gevonden.")
    except Exception as e:
        log(f"⚠️ Fout bij ophalen lijst: {e}")
        return

    # ▪️ Logbestand laden
    repost_log = "reposted.txt"
    if os.path.exists(repost_log):
        with open(repost_log, "r") as f:
            done = set(f.read().splitlines())
    else:
        done = set()

    posts_to_check = []

    # ▪️ Alle posts ophalen
    for member in members:
        handle = member.subject.handle
        try:
            feed = client.app.bsky.feed.get_author_feed({"actor": handle, "limit": 5})
            if not feed.feed:
                log(f"ℹ️ Geen posts gevonden voor @{handle}")

            for post in feed.feed:
                record = getattr(post.post, "record", None) or getattr(post, "record", None)
                created_at = None

                # 🔍 Zoek tijdveld op meerdere mogelijke plekken
                if record and hasattr(record, "createdAt"):
                    created_at = record.createdAt
                elif hasattr(post.post, "createdAt"):
                    created_at = post.post.createdAt
                elif hasattr(post.post, "indexedAt"):
                    created_at = post.post.indexedAt
                elif hasattr(post, "indexedAt"):
                    created_at = post.indexedAt

                if not created_at:
                    log(f"⚠️ Geen tijdveld gevonden voor @{handle}, skip.")
                    continue

                posts_to_check.append({
                    "handle": handle,
                    "uri": post.post.uri,
                    "cid": post.post.cid,
                    "created_at": datetime.fromisoformat(created_at.replace('Z', '+00:00')),
                    "post": post
                })

        except Exception as e:
            log(f"⚠️ Fout bij ophalen feed @{handle}: {e}")

    log(f"🕒 {len(posts_to_check)} totale posts verzameld vóór filtering.")

    if not posts_to_check:
        log("🚫 Geen posts gevonden. Controleer of gebruikers recente originele posts hebben.")
        return

    # ▪️ Sorteer op tijd (nieuwste bovenaan)
    posts_to_check.sort(key=lambda x: x["created_at"], reverse=True)

    total_reposts = 0
    total_likes = 0
    posted_this_run = set()
    user_counts = {}

    # ▪️ Repost in tijdsvolgorde
    for entry in posts_to_check:
        handle = entry["handle"]
        uri = entry["uri"]
        cid = entry["cid"]
        post = entry["post"]

        # Skip reposts, replies en embeds van anderen
        if hasattr(post, "reason") and post.reason is not None:
            continue
        record = post.post.record
        if getattr(record, "reply", None):
            continue
        embed = getattr(post.post, "embed", None)
        if embed and hasattr(embed, "record"):
            rec = getattr(embed, "record", None)
            if rec and hasattr(rec, "author") and rec.author.handle != handle:
                continue

        # Dubbelcontrole
        if uri in done or uri in posted_this_run:
            continue

        # Limiet per gebruiker
        limit = 3 if handle != EXEMPT_HANDLE else float("inf")
        user_counts.setdefault(handle, 0)
        if user_counts[handle] >= limit:
            continue

        try:
            # 🔁 Repost
            client.app.bsky.feed.repost.create(
                repo=client.me.did,
                record={
                    "subject": {"uri": uri, "cid": cid},
                    "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                }
            )
            log(f"🟦 Gerepost @{handle}: {uri}")
            done.add(uri)
            posted_this_run.add(uri)
            user_counts[handle] += 1
            total_reposts += 1
            time.sleep(2)

            # ❤️ Like
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

    # ▪️ Logbestand bijwerken
    with open(repost_log, "w") as f:
        f.write("\n".join(done))

    # ▪️ Samenvatting
    log(f"📊 Samenvatting: {total_reposts} reposts en {total_likes} likes uitgevoerd.")
    log(f"⏰ Run beëindigd om {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")

if __name__ == "__main__":
    main()