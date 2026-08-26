"""
Chartink -> Telegram alert bot (free-tier friendly).

Fetches your Chartink scan results using the same request the Chartink
website makes internally, compares against the last run, and sends a
Telegram message only for NEW stocks that have appeared in the scan.

Run this on a schedule (see the accompanying GitHub Actions workflow file)
so it checks periodically during market hours.
"""

import json
import os
import requests
from bs4 import BeautifulSoup

# ----------------------------------------------------------------------
# 1. PASTE YOUR SCAN CLAUSE HERE (see README / instructions for how to get it)
# ----------------------------------------------------------------------
SCAN_CLAUSE = "PASTE_YOUR_SCAN_CLAUSE_HERE"

# ----------------------------------------------------------------------
# 2. These come from environment variables / GitHub Actions secrets
#    (never hardcode your bot token in this file)
# ----------------------------------------------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

SEEN_FILE = "seen_stocks.json"


def get_scan_results():
    """Replicates the request Chartink's own site makes to run a scan."""
    with requests.Session() as session:
        r = session.get("https://chartink.com/screener/")
        soup = BeautifulSoup(r.content, "html.parser")
        csrf_token = soup.find("meta", {"name": "csrf-token"})["content"]

        headers = {
            "Referer": "https://chartink.com/screener/",
            "x-csrf-token": csrf_token,
        }
        payload = {"scan_clause": SCAN_CLAUSE}

        resp = session.post(
            "https://chartink.com/screener/process",
            headers=headers,
            data=payload,
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json().get("data", [])


def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    resp = requests.post(
        url,
        data={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"},
        timeout=20,
    )
    resp.raise_for_status()


def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    return set()


def save_seen(stock_codes):
    with open(SEEN_FILE, "w") as f:
        json.dump(sorted(stock_codes), f)


def main():
    if not BOT_TOKEN or not CHAT_ID:
        raise SystemExit("BOT_TOKEN and CHAT_ID environment variables must be set")

    if SCAN_CLAUSE == "PASTE_YOUR_SCAN_CLAUSE_HERE":
        raise SystemExit("Edit scanner.py and paste in your actual scan_clause")

    results = get_scan_results()
    current_codes = {row["nsecode"] for row in results if "nsecode" in row}
    seen_codes = load_seen()

    new_codes = current_codes - seen_codes

    if new_codes:
        lines = []
        for row in results:
            code = row.get("nsecode")
            if code in new_codes:
                price = row.get("close", "N/A")
                lines.append(f"• {code} — ₹{price}")

        message = "📢 *New scan hits*\n\n" + "\n".join(lines)
        send_telegram(message)
        print(f"Sent alert for {len(new_codes)} new stock(s): {sorted(new_codes)}")
    else:
        print("No new stocks since last run.")

    save_seen(current_codes)


if __name__ == "__main__":
    main()
