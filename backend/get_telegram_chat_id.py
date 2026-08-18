"""Find your Telegram chat ID so alerts can reach your phone.

Run it from the backend folder:

    python get_telegram_chat_id.py

Before running:
  1. Open Telegram, search for @BotFather and send /newbot
  2. Pick any name and a username ending in 'bot'
  3. Copy the token BotFather gives you into backend/.env as TELEGRAM_BOT_TOKEN
  4. Open a chat with your new bot and send it any message (e.g. "hi")
  5. Run this script - it prints the chat id to paste into TELEGRAM_CHAT_IDS

Your bot token is never printed.
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

from notification_service import get_settings


def main() -> int:
    settings = get_settings()
    token = settings.telegram_bot_token

    print("=" * 62)
    print("Telegram chat ID finder")
    print("=" * 62)

    if not token:
        print("FAIL: TELEGRAM_BOT_TOKEN is not set in backend/.env")
        print()
        print("Get one by messaging @BotFather on Telegram and sending /newbot.")
        return 1

    print(f"Bot token    : found, {len(token)} characters")

    try:
        response = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=15)
        me = response.json()
    except Exception as exc:
        print(f"FAIL: could not reach Telegram: {exc}")
        return 1

    if not me.get("ok"):
        print(f"FAIL: Telegram rejected the token: {me.get('description', 'unknown error')}")
        print("      Copy TELEGRAM_BOT_TOKEN again from @BotFather.")
        return 1

    bot_username = (me.get("result") or {}).get("username", "unknown")
    print(f"Bot          : @{bot_username}")
    print("-" * 62)

    try:
        response = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=15)
        updates = response.json()
    except Exception as exc:
        print(f"FAIL: could not read updates: {exc}")
        return 1

    if not updates.get("ok"):
        print(f"FAIL: {updates.get('description', 'unknown error')}")
        return 1

    results = updates.get("result") or []
    chats: dict[str, str] = {}

    for update in results:
        message = update.get("message") or update.get("channel_post") or {}
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        if chat_id is None:
            continue
        label = chat.get("title") or " ".join(
            part for part in (chat.get("first_name"), chat.get("last_name")) if part
        ) or chat.get("username") or chat.get("type", "chat")
        chats[str(chat_id)] = str(label)

    if not chats:
        print("No messages found yet.")
        print()
        print(f"Open Telegram, search for @{bot_username}, press Start and send it any")
        print("message. Then run this script again.")
        return 1

    print("Found these chats:")
    print()
    for chat_id, label in chats.items():
        print(f"   {label}  ->  chat id: {chat_id}")
    print()
    print("Add this line to backend/.env (comma separated for more than one):")
    print()
    print(f"   TELEGRAM_CHAT_IDS={','.join(chats)}")
    print()
    print("Then restart the backend and press 'Send test SMS' on the Alerts page.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
