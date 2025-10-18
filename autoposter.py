from atproto import Client
import os

def main():
    username = os.environ["BSKY_USERNAME"]
    password = os.environ["BSKY_PASSWORD"]

    client = Client()
    client.login(username, password)

    print("✅ Verbonden met Bluesky als:", username)
    print("Hier komt later de repost-logica...")

if __name__ == "__main__":
    main()
