from atproto import Client
import os
import time
from datetime import datetime, timedelta, timezone

# Configuratie
LIST_URI = "at://did:plc:jaka644beit3x4vmmg6yysw7/app.bsky.graph.list/3m3iga6wnmz2p"
EXEMPT_HANDLE = "bleuskybeauty.bsky.social"
MAX_PER_RUN = 25
MAX_PER_USER = 5
DAYS_BACK = 7

def log(msg: str):
    now = datetime.now(timezone.utc).strftime("[%H:%M:%S]")
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
    cutoff_time = datetime.now(timezone.utc) - timedelta(days=DAYS_BACK)

    for member in members:
        handle = member.subject.handle
        log(f"🔎 Check feed @{handle}")
        try:
            feed = client.app.bsky.feed.get_author_feed({"actor": handle, "limit": 10})
            for item in feed.feed:
                post = item.post
                record = post.record
                uri = post.uri
                cid = post.cid
                indexed_at = getattr(post, "indexedAt", None)

                # Skip reposts
                if hasattr(item, "reason") and item.reason is not None:
                    log(f"  ⚪ @{handle} → SKIP: is repost ({uri})")
                    continue

                # Skip replies
                if getattr(record, "reply", None):
                    log(f"  ⚪ @{handle} → SKIP: is reply ({uri})")
                    continue

                # Skip dubbele
                if uri in done:
                    log(f"  ⚪ @{handle} → SKIP: al gerepost ({uri})")
                    continue

                # Tijd bepalen
                created = getattr(record, "createdAt", None) or indexed_at
                if not created:
                    log(f"  ⚪ @{handle} → SKIP: geen tijd gevonden ({uri})")
                    continue
                try:
                    created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                except Exception:
                    log(f"  ⚪ @{handle} → SKIP: fout bij tijd parsing ({created})")
                    continue

                # Filter te oude posts
                if created_dt < cutoff_time:
                    log(f"  ⚪ @{handle} → SKIP: ouder dan {DAYS_BACK} dagen ({created_dt})")
                    continue

                log(f"  ✅ @{handle} → TOEGEVOEGD: {created_dt} ({uri})")
                all_posts.append({
                    "handle": handle,
                    "uri": uri,
                    "cid": cid,
                    "created": created_dt,
                })
        except Exception as e:
            log(f"⚠️ Fout bij ophalen feed @{handle}: {e}")

    log(f"🕒 {len(all_posts)} totale posts verzameld (voor filtering).")

    # Nieuwste eerst
    all_posts.sort(key=lambda x: x["created"], reverse=True)

    reposted = 0
    liked = 0
    per_user_count = {}
    posts_to_do = all_posts[:MAX_PER_RUN]
    log(f"📊 {len(posts_to_do)} posts geselecteerd (max {MAX_PER_RUN}).")

    for post in posts_to_do:
        handle = post["handle"]
        uri = post["uri"]
        cid = post["cid"]

        if reposted >= MAX_PER_RUN:
            break

        if handle != EXEMPT_HANDLE:
            count = per_user_count.get(handle, 0)
            if count >= MAX_PER_USER:
                log(f"  ⚪ @{handle} → SKIP: limiet van {MAX_PER_USER} bereikt.")
                continue

        try:
            client.app.bsky.feed.repost.create(
                repo=client.me.did,
                record={
                    "subject": {"uri": uri, "cid": cid},
                    "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )
            log(f"🔁 Gerepost @{handle}: {uri}")
            done.add(uri)
            reposted += 1
            per_user_count[handle] = per_user_count.get(handle, 0) + 1
            time.sleep(2)

            try:
                client.app.bsky.feed.like.create(
                    repo=client.me.did,
                    record={
                        "subject": {"uri": uri, "cid": cid},
                        "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    },
                )
                log(f"❤️ Geliked @{handle}: {uri}")
                liked += 1
                time.sleep(1)
            except Exception as e_like:
                log(f"⚠️ Fout bij liken @{handle}: {e_like}")

        except Exception as e:
            log(f"⚠️ Fout bij repost @{handle}: {e}")

    with open(repost_log, "w") as f:
        f.write("\n".join(done))

    log(f"✅ Klaar met run! ({reposted} reposts, {liked} likes)")
    log(f"🧮 Samenvatting: {len(all_posts)} bekeken, {reposted} nieuw gerepost.")
    log(f"⏰ Run beëindigd om {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")

if __name__ == "__main__":
    main()