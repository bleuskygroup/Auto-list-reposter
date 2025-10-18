from atproto import Client
import os
import time

# jouw Bluesky-lijst (waar de bot uit moet reposten)
LIST_URI = "at://did:plc:jaka644beit3x4vmmg6yysw7/app.bsky.graph.list/3m3iga6wnmz2p"

def main():
    username = os.environ["BSKY_USERNAME"]
    password = os.environ["BSKY_PASSWORD"]

    client = Client()
    client.login(username, password)
    print(f"✅ Ingelogd als: {username}")

    # haal leden uit de lijst
    try:
        members = client.app.bsky.graph.get_list({"list": LIST_URI}).items
        print(f"📋 {len(members)} gebruikers in lijst gevonden.")
    except Exception as e:
        print(f"⚠️ Fout bij ophalen lijst: {e}")
        return

    # logbestand voor al gerepostte posts
    repost_log = "reposted.txt"
    if os.path.exists(repost_log):
        with open(repost_log, "r") as f:
            done = set(f.read().splitlines())
    else:
        done = set()

    for member in members:
        handle = member.subject.handle
        print(f"\n🔎 Controleer originele posts van @{handle}")

        try:
            feed = client.app.bsky.feed.get_author_feed({"actor": handle, "limit": 5})
            posts = list(feed.feed)

            for post in reversed(posts):
                record = post.post.record
                uri = post.post.uri
                cid = post.post.cid

                # skip reposts van anderen
                if hasattr(post, "reason") and post.reason is not None:
                    print(f"⏭️  Overgeslagen (repost van ander): {uri}")
                    continue

                # skip replies
                if getattr(record, "reply", None):
                    print(f"💬 Overgeslagen (reply): {uri}")
                    continue

                # skip dubbele reposts
                if uri in done:
                    print(f"🔁 Overgeslagen (al gerepost): {uri}")
                    continue

                viewer = getattr(post, "viewer", None)
                already_reposted = getattr(viewer, "repost", None)

                # probeer alleen nieuwe originele posts
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

    # log bijwerken
    with open(repost_log, "w") as f:
        f.write("\n".join(done))

    print("\n✅ Klaar met run!")

if __name__ == "__main__":
    main()