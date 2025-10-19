from atproto import Client
import os
import time
from datetime import datetime

# Bluesky-lijst (waaruit gerepost wordt)
LIST_URI = "at://did:plc:jaka644beit3x4vmmg6yysw7/app.bsky.graph.list/3m3iga6wnmz2p"

# Gebruiker zonder limiet
EXEMPT_HANDLE = "bleuskybeauty.bsky.social"

def log(msg: str):
    """Voeg tijd toe aan elke logregel"""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{now}] {msg}")

def main():
    username = os.environ["BSKY_USERNAME"]
    password = os.environ["BSKY_PASSWORD"]

    client = Client()
    client.login(username, password)
    log(f"✅ Ingelogd als: {username}")

    # lijst ophalen
    try:
        members = client.app.bsky.graph.get_list({"list": LIST_URI}).items
        log(f"📋 {len(members)} gebruikers in lijst gevonden.")
    except Exception as e:
        log(f"⚠️ Fout bij ophalen lijst: {e}")
        return

    # logbestand
    repost_log = "reposted.txt"
    if os.path.exists(repost_log):
        with open(repost_log, "r") as f:
            done = set(f.read().splitlines())
    else:
        done = set()

    posted_this_run = set()
    total_reposts = 0
    total_likes = 0

    for member in members:
        handle = member.subject.handle
        log(f"🔎 Controleer posts van @{handle}")

        try:
            feed = client.app.bsky.feed.get_author_feed({"actor": handle, "limit": 5})
            posts = list(feed.feed)

            reposted_this_user = 0
            user_limit = 3 if handle != EXEMPT_HANDLE else float("inf")

            for post in reversed(posts):
                if reposted_this_user >= user_limit:
                    break

                record = post.post.record
                uri = post.post.uri
                cid = post.post.cid

                # skip reposts van anderen
                if hasattr(post, "reason") and post.reason is not None:
                    continue

                # skip replies
                if getattr(record, "reply", None):
                    continue

                # skip embeds van andere gebruikers
                embed = getattr(post.post, "embed", None)
                if embed and hasattr(embed, "record"):
                    rec = getattr(embed, "record", None)
                    if rec and hasattr(rec, "author") and rec.author.handle != handle:
                        continue

                # dubbele check
                if uri in done or uri in posted_this_run:
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

        except Exception as e:
            log(f"⚠️ Fout bij ophalen feed @{handle}: {e}")

    # logbestand bijwerken
    with open(repost_log, "w") as f:
        f.write("\n".join(done))

    log("✅ Klaar met run!")
    log(f"📊 Samenvatting: {total_reposts} reposts en {total_likes} likes uitgevoerd.")
    log(f"⏰ Run beëindigd om {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")

if __name__ == "__main__":
    main()