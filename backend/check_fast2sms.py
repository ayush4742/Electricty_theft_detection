"""Diagnose Fast2SMS problems by talking to the API directly.

Run it from the backend folder:

    python check_fast2sms.py

It reads FAST2SMS_API_KEY and ALERT_PHONE_NUMBERS from backend/.env, sends one
plain test message, and prints the raw reply from Fast2SMS. Use it when the
Alerts page shows an error and you want to see exactly what the provider said.

Your API key is never printed.
"""

from __future__ import annotations

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

try:
    import requests
except ImportError:
    print("The 'requests' package is missing. Run: pip install -r requirements.txt")
    raise SystemExit(1)

from notification_service import get_settings, to_ascii

ENDPOINT = "https://www.fast2sms.com/dev/bulkV2"


def main() -> int:
    settings = get_settings()

    print("=" * 60)
    print("Fast2SMS connection check")
    print("=" * 60)

    if not settings.fast2sms_api_key:
        print("FAIL: FAST2SMS_API_KEY is not set in backend/.env")
        return 1

    key = settings.fast2sms_api_key
    print(f"API key      : found, {len(key)} characters (starts with {key[:4]}...)")

    if not settings.recipients:
        print("FAIL: ALERT_PHONE_NUMBERS is empty in backend/.env")
        return 1

    raw_number = settings.recipients[0]
    number = raw_number.replace("+91", "").replace("+", "").strip()
    print(f"Destination  : {number[:2]}****{number[-2:]} ({len(number)} digits)")

    if not number.isdigit() or len(number) != 10:
        print("FAIL: Fast2SMS needs exactly 10 digits with no +91 prefix.")
        print(f"      You have '{raw_number}' in ALERT_PHONE_NUMBERS.")
        return 1

    message = to_ascii("Test from Electricity Theft Detection. SMS setup is working.")
    print(f"Message      : {message}")
    print(f"Route        : q (Quick SMS, no DLT registration needed)")
    print("-" * 60)

    try:
        response = requests.post(
            ENDPOINT,
            headers={"authorization": key},
            data={
                "route": "q",
                "message": message,
                "numbers": number,
                "flash": "0",
                "language": "english",
            },
            timeout=20,
        )
    except Exception as exc:
        print(f"FAIL: could not reach Fast2SMS: {exc}")
        print("      Check your internet connection, VPN, firewall or proxy.")
        return 1

    print(f"HTTP status  : {response.status_code}")
    print(f"Raw response : {response.text[:500]}")
    print("-" * 60)

    try:
        payload = response.json()
    except ValueError:
        payload = None

    if isinstance(payload, dict) and payload.get("return"):
        print("SUCCESS: Fast2SMS accepted the message. Check your phone.")
        return 0

    detail = ""
    if isinstance(payload, dict):
        raw_message = payload.get("message")
        detail = "; ".join(raw_message) if isinstance(raw_message, list) else str(raw_message or "")

    print(f"FAILED: {detail or 'Fast2SMS rejected the request.'}")
    print()
    print("Common causes:")
    print("  * Wrong API key      - copy it again from Dev API > API Key")
    print("  * No wallet balance  - check Account Info > Wallet on the dashboard")
    print("  * Quick SMS disabled - some accounts must enable the 'q' route first")
    print("  * Number not allowed - new accounts can sometimes only text the")
    print("                         mobile number used at signup")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
