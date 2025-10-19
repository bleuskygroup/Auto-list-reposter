from atproto import Client
import os
import time
from datetime import datetime, timedelta

LIST_URI = "at://did:plc:jaka644beit3x4vmmg6yysw7/app.bsky.graph.list/3m3iga6wnmz2p"
MAX_PER_USER = 5
MAX_TOTAL = 25
DAYS_LIMIT = 7

def log(msg):
    now = datetime.utcnow().strftime("[%H:%M:%S]")
    print(f"{now} {msg}")

def main():
    username = os.environ["BSKY_USERNAME"]
    password = os.environ["BSKY_PASSWORD"]

    client = Client()
    client.login(username, password)
    log(f"✅ Ingelogd als {username}")

    # lijst ophalen
    members = client.app.bsky.graph.get_list({"list": LIST_URI}).items
    log(f"📋 {len(members)} gebruikers gevonden.")

    # repostlog laden
    repost_log = "reposted.txt"
    if os.path.exists(repost_log):
        with open(repost_log, "r") as f:
            done = set(f.read().splitlines())
    else:
        done = set()

    cutoff = datetime.utcnow() - timedelta(days=DAYS_LIMIT)
    all_posts = []

    # Posts ophalen
    for member in members:
        handle = member.subject.handle
        log(f"🔎 Check feed @{handle}")
        try:
            feed = client.app.bsky.feed.get_author_feed({"actor": handle, "limit": 10}).feed
            for post in feed:
                uri = post.post.uri
                cid = post.post.cid
                record = post.post.record
                created_at = getattr(record, "createdAt", None) or getattr(post.post, "indexedAt", None)
                if not created_at:
                    continue

                created_time = datetime.strptime(created_at[:19], "%Y-%m-%dT%H:%M:%S")
                if created_time < cutoff:
                    continue

                # skip replies en reposts
                if getattr(record, "reply", None):
                    continue
                if hasattr(post, "reason") and post.reason is not None:
                    continue

                all_posts.append({
                    "handle": handle,
                    "uri": uri,
                    "cid": cid,
                    "created_at": created_time
                })
        except Exception as e:
            log(f"⚠️ Fout bij ophalen @{handle}: {e}")

    log(f"🕒 {len(all_posts)} totale posts verzameld (voor filtering).")

    # sorteren nieuwste eerst
    all_posts.sort(key=lambda x: x["created_at"], reverse=True)

    # filter dubbele en beperkingen
    reposted = set()
    counts = {}
    final_posts = []

    for p in all_posts:
        h = p["handle"]
        if p["uri"] in done or p["uri"] in reposted:
            continue
        if counts.get(h, 0) >= MAX_PER_USER:
            continue
        final_posts.append(p)
        reposted.add(p["uri"])
        counts[h] = counts.get(h, 0) + 1
        if len(final_posts) >= MAX_TOTAL:
            break

    log(f"📊 {len(final_posts)} posts na filtering, max {MAX_TOTAL} zal gepost worden.")

    total_reposts = 0
    total_likes = 0

    for post in final_posts:
        handle = post["handle"]
        uri = post["uri"]
        cid = post["cid"]
        try:
            client.app.bsky.feed.repost.create(
                repo=client.me.did,
                record={
                    "subject": {"uri": uri, "cid": cid},
                    "createdAt": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
                }
            )
            log(f"🔁 Gerepost @{handle}: {uri}")
            done.add(uri)
            total_reposts += 1
            time.sleep(2)

            try:
                client.app.bsky.feed.like.create(
                    repo=client.me.did,
                    record={
                        "subject": {"uri": uri, "cid": cid},
                        "createdAt": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
                    }
                )
                log(f"❤️ Geliked @{handle}: {uri}")
                total_likes += 1
                time.sleep(1)
            except Exception as e:
                log(f"⚠️ Fout bij liken @{handle}: {e}")

        except Exception as e:
            log(f"⚠️ Fout bij repost @{handle}: {e}")

    with open(repost_log, "w") as f:
        f.write("\n".join(done))

    log(f"✅ Klaar met run! ({total_reposts} reposts, {total_likes} likes)")
    log(f"🧮 Samenvatting: {len(all_posts)} bekeken, {len(done)} totaal gerepost.")
    log(f"⏰ Run beëindigd om {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")

if __name__ == "__main__":
    main()