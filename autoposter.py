from atproto import Client
import os
import time

LIST_URI = "at://did:plc:jaka644beit3x4vmmg6yysw7/app.bsky.graph.list/3m3iga6wnmz2p"

def has_media(post):
    """Controleer of de post foto of video bevat (ondersteunt alle bekende embed-types)."""
    embed = getattr(post.post, "embed", None)
    if not embed:
        return False

    embed_type = getattr(embed, "$type", "") or ""
    if any(x in embed_type for x in [
        "app.bsky.embed.images",
        "app.bsky.embed.video",
        "app.bsky.embed.external",
        "app.bsky.embed.recordWithMedia"
    ]):
        return True

    # recordWithMedia kan een nested 'media' veld bevatten
    if hasattr(embed, "media"):
        media = getattr(embed, "media", None)
        media_type = getattr(media, "$type", "") or ""
        if any(x in media_type for x in [
            "app.bsky.embed.images",
            "app.bsky.embed.video",
            "app.bsky.embed.external"
        ]):
            return True

    return False


def main():
    username = os.environ["BSKY_USERNAME"]
    password = os.environ["BSKY_PASSWORD"]

    client = Client()
    client.login(username, password)
    print(f"✅ Ingelogd als: {username}")

    try:
        members = client.app.bsky.graph.get_list({"list": LIST_URI}).items
        print(f"📋 {len(members)} gebruikers in lijst gevonden.")
    except Exception as e:
        print(f"⚠️ Fout bij ophalen lijst: {e}")
        return

    repost_log = "reposted.txt"
    if os.path.exists(repost_log):
        with open(repost_log, "r") as f:
            done = set(f.read().splitlines())
    else:
        done = set()

    for member in members:
        handle = member.subject.handle
        print(f"🔎 Controleer posts van @{handle}")

        try:
            feed = client.app.bsky.feed.get_author_feed({"actor": handle, "limit": 5})
            posts = list(feed.feed)

            for post in reversed(posts):
                # sla replies over
                if getattr(post.post.record, "reply", None):
                    continue

                # check media
                if not has_media(post):
                    continue

                uri = post.post.uri
                cid = post.post.cid

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
                        print(f"📸 Gerepost (met media): {uri}")
                        done.add(uri)
                        time.sleep(2)

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

    print("✅ Klaar met run!")

if __name__ == "__main__":
    main()