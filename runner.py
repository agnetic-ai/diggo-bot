#!/usr/bin/env python3
"""
DIGGO Miner Main Runner & Scheduler
Supports Single Execution (--once) or Continuous 8-Hour Auto-Claim Daemon (--loop)
"""

import sys
import os
import json
import asyncio
from datetime import datetime, timezone, timedelta

from config import (
    BASE_DIR,
    get_configured_accounts,
    ProxyRotator,
    MINING_INTERVAL_HOURS,
    ACCOUNT_DELAY_SECONDS
)
from client import DiggoClient

STATUS_LOG_FILE = os.path.join(BASE_DIR, "status.json")


def save_status(results: list, next_run_time: datetime | None = None):
    data = {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "totalAccounts": len(results),
        "nextRunAt": next_run_time.isoformat() if next_run_time else None,
        "accounts": results
    }
    try:
        with open(STATUS_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[Warning] Failed to write {STATUS_LOG_FILE}: {e}")


async def run_fleet() -> int:
    """Runs all accounts and returns the minimum seconds until next claim."""
    accounts = get_configured_accounts()
    if not accounts:
        print("\n[Error] No accounts found! Please configure INIT_DATA or TG_WEB_APP_DATA in .env")
        return 300

    print("\n" + "=" * 65)
    print(f"DIGGO MINER RUNNER - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"Accounts Loaded: {len(accounts)}")
    print("=" * 65)

    rotator = ProxyRotator()
    results = []
    min_sleep_sec = int(MINING_INTERVAL_HOURS * 3600)

    for idx, acc in enumerate(accounts, 1):
        name = acc["name"]
        init_data = acc["init_data"]
        proxy = rotator.get_proxy(account_name=name)

        print(f"\n>>> [{idx}/{len(accounts)}] Processing: {name}")
        client = DiggoClient(name, init_data, proxy=proxy)
        res = await client.execute_account_flow()
        results.append(res)

        # Track next mining claim window
        if res.get("next_claim_sec"):
            claim_wait = res["next_claim_sec"] + 30  # add 30s buffer
            if claim_wait > 60 and claim_wait < min_sleep_sec:
                min_sleep_sec = claim_wait

        if idx < len(accounts):
            await asyncio.sleep(ACCOUNT_DELAY_SECONDS)

    # Save summary status
    next_time = datetime.now(timezone.utc) + timedelta(seconds=min_sleep_sec)
    save_status(results, next_time)

    print("\n" + "=" * 65)
    print("CYCLE COMPLETE SUMMARY")
    print("-" * 65)
    print(f"{'No':<3} | {'Account':<18} | {'Status':<12} | {'Balance (DIGGO)':<15} | {'Wallet'}")
    print("-" * 65)
    for i, r in enumerate(results, 1):
        acc_n = r.get("account", "-")[:18]
        st = r.get("status", "-")
        bal = str(r.get("balance", 0))
        w = (r.get("wallet") or "None")[:15] + "..." if r.get("wallet") and len(r.get("wallet")) > 15 else (r.get("wallet") or "None")
        print(f"{i:<3} | {acc_n:<18} | {st:<12} | {bal:<15} | {w}")
    print("=" * 65)
    print(f"Next Claim Scheduled in: {min_sleep_sec // 3600}h {(min_sleep_sec % 3600) // 60}m (at {next_time.strftime('%H:%M:%S UTC')})\n")

    return min_sleep_sec


async def main():
    mode = "--once"
    if len(sys.argv) > 1 and sys.argv[1] in ["--loop", "loop", "daemon", "-d"]:
        mode = "--loop"

    if mode == "--once":
        await run_fleet()
        return

    print(">>> Starting DIGGO Continuous 8-Hour Claim Daemon...")
    while True:
        try:
            wait_seconds = await run_fleet()
            # Safety clamp: minimum 120s, maximum 8.5 hours
            wait_seconds = max(120, min(wait_seconds, int(8.5 * 3600)))
            print(f"[Daemon] Sleeping for {wait_seconds} seconds until next claim tick...")
            await asyncio.sleep(wait_seconds)
        except KeyboardInterrupt:
            print("\n[Daemon] Terminated by user.")
            break
        except Exception as e:
            print(f"\n[Daemon Error] Unexpected exception in runner loop: {e}")
            print("[Daemon] Retrying in 60 seconds...")
            await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())
