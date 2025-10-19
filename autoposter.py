from atproto import Client
import os
import time
from datetime import datetime, timedelta

# Bluesky-lijst (waaruit gerepost wordt)
LIST_URI = "at://did:plc:jaka644beit3x4vmmg6yysw7/app.bsky.graph.list/3m3iga6wnmz2p"
EXEMPT_HANDLE = "bleuskybeauty.bsky.social"

# instellingen
MAX_TOTAL = 25          # max 25 reposts per run
MAX_PER_USER = 5        # max 5 per gebruiker per uur
DAYS_LIMIT = 7          # posts ouder dan 7 dagen overslaan

def log(msg: str):
    """Voeg tijd toe aan elke logregel"""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{now}] {msg}")

def has_media(client, uri):
    """Check of een post media bevat (foto of video)"""
    try:
        thread = client.app.bsky.feed.get_post_thread({"uri": uri})
        post = getattr(thread, "thread", None)
        if not post:
            return False
        embed = getattr(post.post, "embed", None)
        if not embed:
            return False

        etype = getattr(embed, "$type", "")
        if "app.bsky.embed.images" in etype or "app.bsky.embed.video" in etype:
            return True
        if etype == "app.bsky.embed.recordWithMedia":
            media = getattr(embed, "media", None)
            if media and (
                "app.bsky.embed.images" in getattr(media, "$type", "") or
                "app.bsky.embed.video" in getattr(media, "$type", "")
            ):
                return True
        return False
    except Exception:
        return False

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

    # repost-log inladen
    repost_log = "reposted.txt"
    if os.path.exists(repost_log):
        with open(repost_log, "r") as f:
            done = set(f.read().splitlines())
    else:
        done = set()

    cutoff = datetime.utcnow() - timedelta(days=DAYS_LIMIT)
    all_posts = []

    # --- Haal feeds op ---
    for member in members:
        handle = member.subject.handle
        try:
            feed = client.app.bsky.feed.get_author_feed({"actor": handle, "limit": 10})
            total_found = 0
            total_valid = 0
            total_old = 0
            total_no_media = 0

            for item in feed.feed:
                total_found += 1
                post = item.post
                record = post.record

                # alleen originele posts
                if getattr(record, "reply", None):
                    continue
                if hasattr(item, "reason") and item.reason is not None:
                    continue

                # datum ophalen
                indexed = getattr(post, "indexed_at", None)
                if not indexed:
                    continue

                try:
                    post_time = datetime.strptime(indexed, "%Y-%m-%dT%H:%M:%S.%fZ")
                except ValueError:
                    continue

                if post_time < cutoff:
                    total_old += 1
                    continue

                # check of post media heeft
                if not has_media(client, post.uri):
                    total_no_media += 1
                    continue

                total_valid += 1
                all_posts.append({
                    "uri": post.uri,
                    "cid": post.cid,
                    "handle": handle,
                    "indexed_at": indexed
                })

            log(f"🔎 @{handle}: {total_found} posts → {total_valid} met media, {total_no_media} zonder, {total_old} te oud")

        except Exception as e:
            log(f"⚠️ Fout bij ophalen feed @{handle}: {e}")

    log(f"🕒 {len(all_posts)} totaal geschikte posts verzameld (binnen 7 dagen, met media).")
    all_posts.sort(key=lambda x: x["indexed_at"], reverse=True)  # nieuwste bovenaan

    reposted_total = 0
    user_reposts = {}

    # --- Repost fase ---
    for p in all_posts:
        if reposted_total >= MAX_TOTAL:
            break

        handle = p["handle"]
        uri, cid = p["uri"], p["cid"]

        # al gerepost?
        if uri in done:
            continue

        # per-gebruiker limiet
        if handle != EXEMPT_HANDLE:
            count = user_reposts.get(handle, 0)
            if count >= MAX_PER_USER:
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
            log(f"📸 Gerepost @{handle}: {uri}")
            done.add(uri)
            reposted_total += 1
            user_reposts[handle] = user_reposts.get(handle, 0) + 1
            time.sleep(2)

            # Like toevoegen
            client.app.bsky.feed.like.create(
                repo=client.me.did,
                record={
                    "subject": {"uri": uri, "cid": cid},
                    "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                }
            )
            log(f"❤️