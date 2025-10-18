from atproto import Client
import os
import time
from datetime import datetime, timedelta, timezone

# jouw Bluesky-lijst
LIST_URI = "at://did:plc:jaka644beit3x4vmmg6yysw7/app.bsky.graph.list/3m3iga6wnmz2p"

# gebruiker die geen limiet heeft
EXEMPT_HANDLE = "bleuskybeauty.bsky.social"

def main():
    username = os.environ["BSKY_USERNAME"]
    password = os.environ["BSKY_PASSWORD"]

    client = Client()
    client.login(username, password)
    print(f"✅ Ingelogd als: {username}")

    # lijst ophalen
    try:
        members = client.app.bsky.graph.get_list({"list": LIST_URI}).items
        print(f"📋 {len(members)} gebruikers in lijst gevonden.")
    except Exception as e:
        print(f"⚠️ Fout bij ophalen lijst: {e}")
        return

    # logbestand
    repost_log = "reposted.txt"
    if os.path.exists(repost_log):
        with open(repost_log, "r") as f:
            done = set(f.read().splitlines())
    else:
        done = set()

    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    print(f"🕓 Alleen posts na {cutoff.isoformat()} worden meegenomen.")

    for member in members:
        handle = member.subject.handle
        print(f"\n🔎 Controleer originele posts van @{handle}")

        try:
            feed = client.app.bsky.feed.get_author_feed({"actor": handle, "limit": 10})
            posts = list(feed.feed)

            reposted_this_user = 0
            user_limit = 1 if handle != EXEMPT_HANDLE else float("inf")

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

                # tijd check
                created_at_str = getattr(record, "createdAt", None)
                if not created_at_str:
                    continue
                created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                if created_at < cutoff:
                    continue

                # dubbele check
                if uri in done:
                    continue

                viewer = getattr(post, "viewer", None)
                already_reposted = getattr(viewer, "repost", None)

                if not already_reposted:
                    try:
                        client.app.bsky.feed.repost.create(
                            repo=client.me.did,
                            record={
                                "subject": {"uri": uri, "cid": cid},
                                "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                            }
                        )
                        print(f"🟦 Gerepost originele post: {uri}")
                        done.add(uri)
                        reposted_this_user += 1
                        time.sleep(2)

                        # like toevoegen
                        already_liked = getattr(viewer, "like", None)
                        if not already_liked:
                            try:
                                client.app.bsky.feed.like.create(
                                    repo=client.me.did,
                                    record={
                                        "subject": {"uri": uri, "cid": cid},
                                        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                                    }
                                )
                                print(f"❤️ Geliked: {uri}")
                                time.sleep(1)
                            except Exception as e_like:
                                print(f"⚠️ Fout bij liken @{handle}: {e_like}")

                    except Exception as e:
                        print(f"⚠️ Fout bij repost @{handle}: {e}")
        except Exception as e:
            print(f"⚠️ Fout bij ophalen feed @{handle}: {e}")

    with open(repost_log, "w") as f:
        f.write("\n".join(done))

    print("\n✅ Klaar met run! (max 1 per gebruiker, onbeperkt voor @bleuskybeauty.bsky.social)")

if __name__ == "__main__":
    main()