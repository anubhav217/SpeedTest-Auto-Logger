#!/usr/bin/env python3
"""speedlogger.py
Cross-platform Speedtest logger:
- Calls Ookla Speedtest CLI (or speedtest-cli fallback)
- Saves raw JSON in ./raw_logs/
- Appends a CSV row to speedtest.csv
- Inserts a record into speedtest.db (SQLite)
- Sends alerts to a Discord webhook (loaded from environment) when thresholds are breached

Configure via environment variables or edit the CONFIG section below:
- DISCORD_WEBHOOK (recommended: set as environment variable)
- DOWNLOAD_THRESHOLD_Mbps, UPLOAD_THRESHOLD_Mbps, PING_THRESHOLD_ms

Run once: python3 speedlogger.py
Schedule externally (cron / Task Scheduler) to run every 30 minutes (README shows examples).
"""

import subprocess
import json
import os
import sqlite3
import csv
import datetime
import requests
import sys
import shutil
from datetime import timedelta

# === CONFIG (edit as needed) ===
# NOTE: For security, the webhook should be provided via environment variable:
# export DISCORD_WEBHOOK="https://discord.com/api/webhooks/ID/TOKEN"
DISCORD_WEBHOOK = os.environ.get('DISCORD_WEBHOOK', '')

DB_PATH = os.environ.get('DB_PATH', 'speedtest.db')
CSV_PATH = os.environ.get('CSV_PATH', 'speedtest.csv')
RAW_DIR = os.environ.get('RAW_DIR', 'raw_logs')

# Thresholds (can also be set via environment variables)
DOWNLOAD_THRESHOLD_Mbps = float(os.environ.get('DOWNLOAD_THRESHOLD_Mbps', '150.0'))   # alert if download < this (change to suit 200 Mbps plan)
UPLOAD_THRESHOLD_Mbps = float(os.environ.get('UPLOAD_THRESHOLD_Mbps', '150.0'))
PING_THRESHOLD_ms = float(os.environ.get('PING_THRESHOLD_ms', '80.0'))
# ================================

os.makedirs(RAW_DIR, exist_ok=True)


# IST helper — returns naive datetime adjusted to IST (UTC+5:30)
def get_ist_time():
    utc_now = datetime.datetime.utcnow()
    ist_offset = timedelta(hours=5, minutes=30)
    ist_time = utc_now + ist_offset
    return ist_time


def find_speedtest_cmd():
    # prefer new Ookla CLI 'speedtest', fallback to 'speedtest-cli'
    for cmd in (['speedtest', '--format=json'], ['speedtest-cli', '--json']):
        exe = cmd[0]
        if shutil.which(exe):
            return cmd
    return None


def run_speedtest():
    cmd = find_speedtest_cmd()
    if not cmd:
        raise RuntimeError(
            "No speedtest CLI found. Install Ookla Speedtest CLI (https://www.speedtest.net/apps/cli) or python speedtest-cli and put it in PATH."
        )
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if proc.returncode != 0:
        raise RuntimeError(f"speedtest returned code {proc.returncode}: {proc.stderr[:200]}")
    return json.loads(proc.stdout)


def save_raw_json(data):
    ts = get_ist_time().strftime('%Y%m%dT%H%M%S+05:30')
    fname = os.path.join(RAW_DIR, f'speed_{ts}.json')
    with open(fname, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    return fname


def ensure_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS speedtest (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts_utc TEXT,
            download_mbps REAL,
            upload_mbps REAL,
            ping_ms REAL,
            server_id TEXT,
            server_name TEXT,
            client_ip TEXT,
            raw_file TEXT
        )
    ''')
    conn.commit()
    return conn


def parse_speedtest_json(data):
    # Try to be robust to different CLIs.
    download = None
    upload = None
    ping = None
    server_id = ''
    server_name = ''
    client_ip = ''
    if isinstance(data, dict):
        d = data.get('download')
        u = data.get('upload')
        if isinstance(d, dict) and 'bandwidth' in d:
            # Ookla new CLI: bandwidth is bits/sec
            download = float(d['bandwidth']) / 1e6
        elif isinstance(d, (int, float)):
            download = float(d) / 1e6
        if isinstance(u, dict) and 'bandwidth' in u:
            upload = float(u['bandwidth']) / 1e6
        elif isinstance(u, (int, float)):
            upload = float(u) / 1e6
        p = data.get('ping')
        if isinstance(p, dict) and 'latency' in p:
            ping = float(p['latency'])
        elif isinstance(p, (int, float)):
            ping = float(p)
        server = data.get('server') or {}
        client = data.get('client') or {}
        server_id = str(server.get('id') or server.get('host') or '')
        server_name = str(server.get('name') or server.get('host') or '')
        client_ip = str(client.get('ip') or '')
        # Try alternate keys
        if download is None:
            for k in ('download_mbps', 'downloadMbps', 'download_bandwidth', 'download_bandwidth_mbps'):
                if k in data and isinstance(data[k], (int, float)):
                    download = float(data[k])
        if upload is None:
            for k in ('upload_mbps', 'uploadMbps', 'upload_bandwidth', 'upload_bandwidth_mbps'):
                if k in data and isinstance(data[k], (int, float)):
                    upload = float(data[k])
    return download, upload, ping, server_id, server_name, client_ip


def push_to_db(conn, ts_iso, download, upload, ping, server_id, server_name, client_ip, raw_file):
    cur = conn.cursor()
    cur.execute('''INSERT INTO speedtest (ts_utc, download_mbps, upload_mbps, ping_ms, server_id, server_name, client_ip, raw_file)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (ts_iso, download, upload, ping, server_id, server_name, client_ip, raw_file))
    conn.commit()


def append_csv(ts_iso, download, upload, ping, server_name, client_ip, raw_file):
    header = ['ts_utc', 'download_mbps', 'upload_mbps', 'ping_ms', 'server', 'client_ip', 'raw_file']
    write_header = not os.path.exists(CSV_PATH)
    with open(CSV_PATH, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(header)
        writer.writerow([ts_iso, download, upload, ping, server_name, client_ip, raw_file])


def send_discord_alert(text=None, *, title="Speedtest Alert", fields=None, username="SpeedLogger", webhook_url=None):
    """
    Send a Discord message. If `fields` provided, send an embed.
    - text: plain text content
    - fields: list of tuples: [(name, value, inline_bool), ...]
    - webhook_url: optional override; defaults to DISCORD_WEBHOOK env var
    """
    webhook = (webhook_url or DISCORD_WEBHOOK or os.environ.get('DISCORD_WEBHOOK', '')).strip()
    if not webhook:
        # No webhook configured — print for local debugging
        print("No DISCORD_WEBHOOK configured. Alert not sent. Message would be:", text)
        return None

    payload = {}
    if text:
        payload['content'] = text

    if fields:
        embed = {
            "title": title,
            "type": "rich",
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "fields": []
        }
        for name, value, inline in fields:
            # Discord requires field values to be non-empty strings and <=1024 chars
            v = str(value) if value is not None else "n/a"
            if len(v) > 1024:
                v = v[:1020] + "..."
            embed["fields"].append({"name": str(name), "value": v, "inline": bool(inline)})
        payload['embeds'] = [embed]

    payload['username'] = username

    try:
        r = requests.post(webhook, json=payload, timeout=10)
        if r.status_code in (200, 204):
            return r.status_code
        else:
            print("Discord webhook returned", r.status_code, r.text)
            return r.status_code
    except Exception as e:
        print("Error sending Discord alert:", e)
        return None


def check_and_alert(ts_iso, download, upload, ping, server_name, client_ip):
    msgs = []
    if download is None or upload is None:
        msgs.append("Couldn't parse speedtest numbers properly.")
    else:
        if download < DOWNLOAD_THRESHOLD_Mbps:
            msgs.append(f"Download low: {download:.1f} Mbps (< {DOWNLOAD_THRESHOLD_Mbps})")
        if upload < UPLOAD_THRESHOLD_Mbps:
            msgs.append(f"Upload low: {upload:.1f} Mbps (< {UPLOAD_THRESHOLD_Mbps})")
    if ping is not None and ping > PING_THRESHOLD_ms:
        msgs.append(f"High ping: {ping:.1f} ms (> {PING_THRESHOLD_ms})")

    if msgs:
        # Make a human-friendly plain text and a clean embed with fields
        plain = f"Speedtest alert — {ts_iso} UTC\n" + "\n".join(msgs)
        fields = [
            ("Download", f"{download:.1f} Mbps" if download is not None else "n/a", True),
            ("Upload", f"{upload:.1f} Mbps" if upload is not None else "n/a", True),
            ("Ping", f"{ping:.1f} ms" if ping is not None else "n/a", True),
            ("Server", server_name or "n/a", False),
            ("Client IP", client_ip or "n/a", False),
            ("Time (IST)", ts_iso, False),
        ]
        print(plain)
        send_discord_alert(plain, title="Speedtest — Alert (Alliance Broadband)", fields=fields)


def main():
    try:
        data = run_speedtest()
    except Exception as e:
        print("Failed to run speedtest:", e)
        # optional: send alert about test failure
        send_discord_alert(f"Speedtest run failed: {e}", title="Speedtest — Failure")
        sys.exit(1)

    raw_file = save_raw_json(data)
    download, upload, ping, server_id, server_name, client_ip = parse_speedtest_json(data)
    ts_iso = get_ist_time().isoformat() + '+05:30'

    # store locally
    conn = ensure_db()
    push_to_db(conn, ts_iso, download, upload, ping, server_id, server_name, client_ip, raw_file)
    append_csv(ts_iso, download, upload, ping, server_name, client_ip, raw_file)

    # alerting if needed
    check_and_alert(ts_iso, download or 0, upload or 0, ping or 9999, server_name, client_ip)

    print(f"Logged {ts_iso}: dl={download} Mbps, ul={upload} Mbps, ping={ping} ms (server={server_name})")


if __name__ == '__main__':
    main()
