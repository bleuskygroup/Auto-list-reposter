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

    # bekijk de laatste posts van elk lid en repost (nieuwste eerst)
    for member in members:
        handle = member.subject.handle
        print(f"🔎 Controleer posts van @{handle}")

        try:
            feed = client.app.bsky.feed.get_author_feed({"actor": handle, "limit": 5})
            posts = list(feed.feed)

            # van oud → nieuw zodat nieuwste laatst komt
            for post in reversed(posts):
                # sla replies over
                if getattr(post.post.record, "reply", None):
                    continue

                # controleer of post media (foto of video) bevat
                embed = getattr(post.post, "embed", None)
                has_media = False

                if embed:
                    embed_type = getattr(embed, "$type", "")
                    if "app.bsky.embed.images" in embed_type or "app.bsky.embed.video" in embed_type:
                        has_media = True
                    elif embed_type == "app.bsky.embed.recordWithMedia":
                        # sommige posts hebben recordWithMedia-structuur (combinatie)
                        media = getattr(embed, "media", None)
                        if media and (
                            "app.bsky.embed.images" in getattr(media, "$type", "")
                            or "app.bsky.embed.video" in getattr(media, "$type", "")
                        ):
                            has_media = True

                if not has_media:
                    continue  # geen foto of video, overslaan

                uri = post.post.uri
                cid = post.post.cid

                # sla dubbele reposts over
                if uri in done:
                    continue

                viewer = getattr(post, "viewer", None)
                already_reposted = getattr(viewer, "repost", None)

                if not already_reposted:
                    try:
                        # Repost
                        client.app.bsky.feed.repost.create(
                            repo=client.me.did,
                            record={
                                "subject": {"uri": uri, "cid": cid},
                                "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                            }
                        )
                        print(f"📸 Gerepost (met foto/video): {uri}")
                        done.add(uri)
                        time.sleep(2)

                        # Like (alleen als nog niet geliked)
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

    print("✅ Klaar met run!")

if __name__ == "__main__":
    main()