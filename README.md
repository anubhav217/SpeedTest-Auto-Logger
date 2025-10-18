# Speedtest Logger bundle

Files in this bundle:
- `speedlogger.py` — Cross-platform Python script that runs Speedtest CLI, logs to `speedtest.db` (SQLite), `speedtest.csv`, and `raw_logs/` (JSON raw output). Sends alerts to Discord webhook when configured.
- `run_speedlogger.ps1` — PowerShell helper to run the script and optionally register a Windows Scheduled Task.
- `grafana_dashboard_sample.json` — A simple sample Grafana dashboard JSON (placeholder) you can import and customize.
- `sample_raw.json` — an example speedtest raw JSON (demo).
- `speedtest_bundle.zip` — this archive.

## Quick start (Windows)
1. Install Python 3.8+ and add to PATH.
2. Install `requests`: `pip install requests`
3. Install Ookla Speedtest CLI (preferred): https://www.speedtest.net/apps/cli
   - Or `pip install speedtest-cli` (python wrapper), but Ookla's CLI is recommended.
4. Place this folder somewhere like `C:\Users\You\speedlogger`
5. Configure Discord webhook:
   - Create a Discord webhook in a channel (Server Settings → Integrations → Webhooks) and copy the URL.
   - Either set an environment variable `DISCORD_WEBHOOK` or edit `speedlogger.py` and set `DISCORD_WEBHOOK = 'https://...'` in the CONFIG section.
6. Test run:
   - Open PowerShell, navigate to the folder, run: `python speedlogger.py`
7. (Optional) Register scheduled task using the helper (run as Administrator in PowerShell):
   - `.un_speedlogger.ps1 -RegisterTask -IntervalMinutes 30 -PythonPath "C:\Python39\python.exe"`
   - This will run the script every 30 minutes.

## Quick start (Linux / macOS)
1. Install Python 3.8+ and `requests`: `pip3 install requests`
2. Install Ookla Speedtest CLI (see https://www.speedtest.net/apps/cli) or `pip3 install speedtest-cli`
3. Set `DISCORD_WEBHOOK` env var or edit `speedlogger.py` config.
4. Add a cron entry (every 30 minutes):
   - `*/30 * * * * /usr/bin/python3 /path/to/speedlogger.py >> /path/to/speedlogger.log 2>&1`

## Thresholds and tuning
- Defaults: download/upload threshold = 150 Mbps, ping threshold = 80 ms. Edit the top of `speedlogger.py` to change.
- Run tests at least 48–72 hours to get meaningful median/percentile values before complaining to ISP.

## Evidence collection suggestions
- Keep raw JSON files from `raw_logs/` for timestamps and server IDs.
- Periodically run `mtr`/`traceroute` to problem servers and keep those logs with matching timestamps.
- Run VPN tests and iperf3 tests to corroborate shaping/peering issues.

## Grafana
The included `grafana_dashboard_sample.json` is a minimal placeholder. For an actual Grafana dashboard you will want to push metrics to a time-series DB (InfluxDB/Prometheus) or use a plugin/CSV connector. I can help create a full Grafana + Influx ingestion pipeline if you want.

---
Generated on 2025-10-18T19:47:22.093200Z
