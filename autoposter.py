name: Bluesky Auto Reposter (Feed versie, stabiel met autorestart en failsafe)

on:
  schedule:
    - cron: "*/30 * * * *"   # basisplanning: elke 30 minuten
  workflow_dispatch:

jobs:
  run:
    runs-on: ubuntu-latest
    env:
      MAX_RUNTIME_HOURS: 48   # failsafe: stop na 48 uur

    steps:
      - name: 📦 Checkout repository
        uses: actions/checkout@v4

      - name: 🐍 Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: ⚙️ Install dependencies
        run: |
          pip install atproto requests

      - name: 🚀 Run autoposter feed script
        env:
          BSKY_USERNAME: ${{ secrets.BSKY_USERNAME }}
          BSKY_PASSWORD: ${{ secrets.BSKY_PASSWORD }}
        run: |
          python autoposter.py

      - name: 🔁 Controleer failsafe
        id: check_runtime
        run: |
          echo "Controleer runtime..."
          # Bereken hoe lang de workflow actief is
          START_TIME=$(date -u -d "${{ github.run_started_at }}" +%s)
          NOW=$(date -u +%s)
          RUNTIME_HOURS=$(( (NOW - START_TIME) / 3600 ))
          echo "Actieve tijd: $RUNTIME_HOURS uur"
          if [ $RUNTIME_HOURS -ge $MAX_RUNTIME_HOURS ]; then
            echo "⚠️ Failsafe actief — workflow draait al $RUNTIME_HOURS uur. Stoppen."
            exit 1
          fi

      - name: 🔄 Trigger volgende run
        if: ${{ success() }}
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          REPO: ${{ github.repository }}
        run: |
          echo "Herstart workflow in 30 minuten..."
          sleep 1800
          curl -X POST \
            -H "Accept: application/vnd.github+json" \
            -H "Authorization: Bearer $GH_TOKEN" \
            https://api.github.com/repos/$REPO/actions/workflows/reposter.yml/dispatches \
            -d '{"ref":"main"}'