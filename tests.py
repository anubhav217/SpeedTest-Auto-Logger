#!/usr/bin/env python3
"""
tests.py — safe Discord webhook tester
--------------------------------------
Reads DISCORD_WEBHOOK from environment or .env file and sends a test message.
No secrets are hardcoded.
"""

import os
import requests

# Optional: support .env file for local development
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Load webhook from environment
webhook = os.environ.get("DISCORD_WEBHOOK", "")

if not webhook:
    print("⚠️  No DISCORD_WEBHOOK set. Please export it or create a .env file.")
    print("Example: DISCORD_WEBHOOK=https://discord.com/api/webhooks/XXXX/YYYY")
    exit(1)

# Compose message
payload = {
    "content": "✅ Test alert from Python (Speedtest Logger)",
    "username": "Speedtest Logger",
}

try:
    r = requests.post(webhook, json=payload, timeout=10)
    if r.status_code == 204:
        print("✅ Discord test alert sent successfully!")
    else:
        print(f"⚠️  HTTP {r.status_code}: {r.text}")
except Exception as e:
    print(f"❌ Error sending alert: {e}")
