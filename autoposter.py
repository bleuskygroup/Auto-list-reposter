from atproto import Client
import os
import time
from datetime import datetime, timedelta, timezone

# Feed-URI (deze komt van jouw Bluesky-feed)
FEED_URI = "at://did:plc:jaka644beit3x4vmmg6yysw7/app.bsky.feed.generator/aaaprg6dqhaii"

# Configuratie
MAX_PER_RUN = 50
HOURS_BACK = 2  # Alleen posts van de laatste 2 uur

def log(msg: str):
    """Print logregel met tijdstempel"""
    now = datetime.now(timezone.utc).strftime("[%H:%M:%S]")
    print(f"{now} {msg}")

def parse_time(record, post):
    """Bepaal de juiste tijd van een post"""
    for attr in ["createdAt", "indexedAt", "created_at", "timestamp"]:
        val = getattr(record, attr, None) or getattr(post, attr, None)
        if val:
            try:
                return datetime.fromisoformat(val.replace("Z", "+00:00"))
            except Exception:
                continue
    return None

def main():
    username = os.environ["BSKY_USERNAME"]
    password = os.environ["BSKY_PASSWORD"]

    client = Client()
    client.login(username, password)
    log(f"✅ Ingelogd als {username}")
    log("🔎 Ophalen feed...")

    # Feed ophalen
    try:
        feed = client.app.bsky.feed.get_feed({"feed": FEED_URI, "