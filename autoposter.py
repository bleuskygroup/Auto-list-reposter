from atproto import Client
import os
import time
from datetime import datetime, timedelta

# Bluesky-lijst (waaruit gerepost wordt)
LIST_URI = "at://did:plc:jaka644beit3x4vmmg6yysw7/app.bsky.graph.list/3m3iga6wnmz2p"

# Gebruiker zonder repost-limiet
EXEMPT_HANDLE = "bleuskybeauty.bsky.social"

# Algemene instellingen
MAX_REPOSTS_PER_RUN = 25
MAX_PER_USER = 5
DAYS_BACK = 7  # geen oudere posts dan dit
SLEEP_BETWEEN = 2  # seconden tussen reposts

def log(msg: str):
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

    # verzamel alle recente posts
    posts_all = []
    seen_total = 0

    for member in members:
        handle = member.subject.handle
        log(f"🔎 Check feed @{handle}")

        try:
            feed = client.app.bsky.feed.get_author_feed({"actor": handle, "limit": 10})
            user_posts = []
            for post in feed.feed:
                seen_total += 1

                record = getattr(post.post, "record", None)
                if not record:
                    continue

                # skip reposts (reason != None)
                if hasattr(post, "reason") and post.reason is not None:
                    continue

                # skip replies
                if getattr(record, "reply", None):
                    continue

                # datum bepalen
                created_at = getattr(record, "createdAt", None)
                indexed_at = getattr(post.post, "indexedAt", None)
                timestamp = created_at or indexed_at
                if not timestamp:
                    continue

                try:
                    created_dt = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%fZ")
                except ValueError:
                    created_dt = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")

                # te oud?
                if created_dt < datetime.utcnow() - timedelta(days=DAYS_BACK):
                    continue

                # geen media = overslaan
                embed = getattr(post.post, "embed", None)
                if not embed:
                    continue

                embed_type = getattr(embed, "$type", "")
                has_media = any(
                    t in embed_type
                    for t in ["app.bsky.embed.images", "app.bsky.embed.video"]
                )

                # recordWithMedia
                if "recordWithMedia" in embed_type:
                    media = getattr(embed, "media", None)
                    if media and any(
                        t in getattr(media, "$type", "")
                        for t in ["app.bsky.embed.images", "app.bsky.embed.video"]
                    ):
                        has_media = True

                if not has_media:
                    continue

                user_posts.append({
                    "handle": handle,
                    "uri": post.post.uri,
                    "cid": post.post.cid,
                    "time": created_dt
                })

            posts_all.extend(user_posts[:MAX_PER_USER])

        except Exception as e:
            log(f"⚠️ Fout bij ophalen feed @{handle}: {e}")

    log(f"🕒 {seen_total} totale posts bekeken (voor filtering).")

    # sorteer op tijd — nieuwste eerst
    posts_all.sort(key=lambda x: x["time"], reverse=True)
    log(f"📊 {len(posts_all)} posts na filtering, max {MAX_REPOSTS_PER_RUN} zal gepost worden.")

    reposted_count = 0
    already_done = 0
    liked_count = 0

    for post in posts_all:
        if reposted_count >= MAX_REPOSTS_PER_RUN:
            break

        uri, cid, handle = post["uri"], post["cid"], post["handle"]

        if uri in done:
            already_done += 1
            continue

        try:
            # Repost uitvoeren
            client.app.bsky.feed.repost.create(
                repo=client.me.did,
                record={
                    "subject": {"uri": uri, "cid": cid},
                    "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                }
            )
            log(f"🔁 Gerepost @{handle}: {uri}")
            done.add(uri)
            reposted_count += 1
            time.sleep(SLEEP_BETWEEN)

            # Like ook uitvoeren
            try:
                client.app.bsky.feed.like.create(
                    repo=client.me.did,
                    record={
                        "subject": {"uri": uri, "cid": cid},
                        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    }
                )
                log(f"❤️ Geliked @{handle}: {uri}")
                liked_count += 1
                time.sleep(1)
            except Exception as e_like:
                log(f"⚠️ Fout bij liken @{handle}: {e_like}")

        except Exception as e:
            log(f"⚠️ Fout bij repost @{handle}: {e}")

    # logbestand bijwerken
    with open(repost_log, "w") as f:
        f.write("\n".join(done))

    log(f"✅ Klaar met run! ({reposted_count} reposts, {liked_count} likes)")
    log(f"🧮 Samenvatting: {seen_total} bekeken, {already_done} al gedaan, {reposted_count} nieuw verwerkt.")
    log(f"⏰ Run beëindigd om {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")

if __name__ == "__main__":
    main()