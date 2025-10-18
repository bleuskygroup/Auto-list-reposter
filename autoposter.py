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

    # bekijk de laatste posts van elk lid en repost
    for member in members:
        handle = member.subject.handle
        print(f"🔎 Controleer posts van @{handle}")

        try:
            feed = client.app.bsky.feed.get_author_feed({"actor": handle, "limit": 3})
            for post in feed.feed:
                uri = post.post.uri
                cid = post.post.cid

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
                        print(f"🔁 Gerepost: {uri}")
                        time.sleep(2)
                    except Exception as e:
                        print(f"⚠️ Fout bij repost @{handle}: {e}")
        except Exception as e:
            print(f"⚠️ Fout bij ophalen feed @{handle}: {e}")

    print("✅ Klaar met run!")

if __name__ == "__main__":
    main()