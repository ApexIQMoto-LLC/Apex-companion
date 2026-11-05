"""Pair a private Telegram chat without pasting the bot token into ChatGPT.

Only stores it in the user's Windows Credential Manager via keyring.
Run after creating a bot with @BotFather and sending `/start` to the bot.
"""
from __future__ import annotations
import getpass
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

try:
    import keyring
except ImportError:
    print("Missing keyring package. Run the Companion installer first.")
    raise SystemExit(1)

SERVICE="APEXIQ Companion Telegram"

def main():
    print("APEX / Phone briefing pairing")
    print("Use a new bot created in Telegram with @BotFather, then message your bot /start.")
    token=getpass.getpass("Bot API token (hidden): ").strip()
    if not re.fullmatch(r"\d{5,20}:[A-Za-z0-9_-]{20,}",token):
        print("Token format invalid. No credentials saved.");return 1
    url="https://api.telegram.org/bot"+quote(token,safe=":")+"/getUpdates?limit=40&timeout=0"
    try:
        with urlopen(Request(url,headers={"User-Agent":"APEX-LocalPairing/0.7"}),timeout=12) as resp:
            payload=json.loads(resp.read(100_000).decode("utf-8"))
    except Exception:
        print("Could not query Telegram. Check bot token, network and /start message. No credentials saved.")
        return 2
    if not isinstance(payload,dict) or payload.get("ok") is not True:
        print("Telegram did not accept this token. No credentials saved.");return 3
    ids=sorted({str(obj.get("message",{}).get("chat",{}).get("id"))
                for obj in payload.get("result",[]) if obj.get("message",{}).get("chat",{}).get("type")=="private"
                and obj.get("message",{}).get("chat",{}).get("id") is not None})
    if not ids:
        print("No private chats found. Send /start to the bot in Telegram, then run again.");return 4
    print("Private chat IDs seen by your bot: "+", ".join(ids))
    chosen=ids[0] if len(ids)==1 else input("Type YOUR chat ID from the list: ").strip()
    if chosen not in ids:
        print("Chat ID not selected. No credentials saved.");return 5
    try:
        keyring.set_password(SERVICE,"bot_token",token)
        keyring.set_password(SERVICE,"chat_id",chosen)
    except Exception:
        print("Credential Manager could not store the credentials. No secret printed.");return 6
    print("Paired successfully. Enable PHONE BRIEFING in APEX, then send a test. No keys were placed in config.json.")
    return 0

if __name__=='__main__':
    sys.exit(main())
