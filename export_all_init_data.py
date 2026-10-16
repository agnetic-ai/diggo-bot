#!/usr/bin/env python3
"""
Exports fresh initData / tgWebAppData from all authorized Telegram sessions
in /opt/telegram-multi-account/sessions (STRICTLY EXCLUDING ombengz)
and saves them directly into /opt/diggo-miner/.env
"""

import os
import sys
import asyncio
from urllib.parse import urlsplit, parse_qs
from telethon import TelegramClient, functions

SESSION_DIR = "/opt/telegram-multi-account/sessions"
ENV_PATH = "/opt/diggo-miner/.env"
REF_CODE = "ref_0615dd5877f9bdaa953fc770"
BOT_USERNAME = "Diggominer_bot"

API_ID = 37429744
API_HASH = "491629652b9115dfcf86a185a7bc6bc5"

EXCLUDED_ACCOUNTS = {"ombengz"}


async def fetch_init_data_for_session(session_path: str, session_name: str) -> str | None:
    client = TelegramClient(session_path, API_ID, API_HASH)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            print(f"[-] {session_name}: Not authorized, skipping.")
            await client.disconnect()
            return None

        bot = await client.get_entity(BOT_USERNAME)
        input_bot = await client.get_input_entity(bot)

        res = await client(functions.messages.RequestMainWebViewRequest(
            peer=input_bot,
            bot=input_bot,
            platform="android",
            start_param=REF_CODE
        ))
        await client.disconnect()

        frag = urlsplit(res.url).fragment
        qs = parse_qs(frag)
        init_data = qs.get("tgWebAppData", [""])[0]

        if init_data and "hash=" in init_data:
            print(f"[+] {session_name}: OK (length {len(init_data)})")
            return init_data
        else:
            print(f"[-] {session_name}: Empty initData in webview url")
            return None
    except Exception as e:
        print(f"[-] {session_name}: Error {e}")
        try:
            await client.disconnect()
        except Exception:
            pass
        return None


async def main():
    if not os.path.exists(SESSION_DIR):
        print(f"Session dir {SESSION_DIR} not found.")
        sys.exit(1)

    session_files = sorted([
        f for f in os.listdir(SESSION_DIR)
        if f.endswith(".session")
    ])

    print("==================================================")
    print("DIGGO MINER - FETCHING INIT DATA FOR ALL ACCOUNTS")
    print(f"Total session files: {len(session_files)}")
    print(f"Excluded: {EXCLUDED_ACCOUNTS}")
    print("==================================================")

    valid_inits = []
    for f in session_files:
        name = f[:-8]
        if name in EXCLUDED_ACCOUNTS:
            print(f"[SKIP] {name} is explicitly excluded.")
            continue

        full_path = os.path.join(SESSION_DIR, f)
        init_data = await fetch_init_data_for_session(full_path, name)
        if init_data:
            valid_inits.append(init_data.strip())
        await asyncio.sleep(1)

    print("\n==================================================")
    print(f"Total valid initData collected: {len(valid_inits)}")
    print("==================================================")

    if not valid_inits:
        print("No valid initData collected. .env unchanged.")
        return

    # Write pure initData lines to .env
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        for item in valid_inits:
            f.write(item + "\n")

    print(f"Successfully saved {len(valid_inits)} accounts into {ENV_PATH}!")


if __name__ == "__main__":
    asyncio.run(main())
