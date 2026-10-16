"""
DIGGO Miner Client API Implementation
Handles Telegram WebApp Authentication, Tasks, Streaks, and Mining Operations.
"""

import time
import uuid
import httpx
from datetime import datetime, timezone

from config import (
    BASE_URL,
    AUTO_DAILY_CHECKIN,
    AUTO_DAILY_STREAK,
    AUTO_TASKS
)

HEADERS_BASE = {
    "Content-Type": "application/json",
    "Origin": BASE_URL,
    "Referer": f"{BASE_URL}/",
    "User-Agent": "Mozilla/5.0 (Linux; Android 14; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.6668.100 Mobile Safari/537.36",
    "Accept": "application/json"
}


class DiggoClient:
    def __init__(self, account_name: str, init_data: str, proxy: str | None = None):
        self.account_name = account_name
        self.init_data = init_data
        self.proxy = proxy
        self.token: str | None = None
        self.state: dict = {}
        self.player: dict = {}
        self.outbound_ip: str | None = None

    def _get_headers(self, with_auth: bool = True, idempotency: bool = False) -> dict:
        h = dict(HEADERS_BASE)
        if with_auth and self.token:
            h["Authorization"] = f"Bearer {self.token}"
        if idempotency:
            h["Idempotency-Key"] = str(uuid.uuid4())
        return h

    async def check_ip(self, client: httpx.AsyncClient) -> str:
        try:
            r = await client.get("https://api.ipify.org", timeout=5.0)
            self.outbound_ip = r.text.strip()
            return self.outbound_ip
        except Exception:
            self.outbound_ip = "Unknown/Direct"
            return self.outbound_ip

    async def login(self, client: httpx.AsyncClient) -> bool:
        """Authenticates with DIGGO backend using initData."""
        url = f"{BASE_URL}/api/auth/telegram"
        payload = {"initData": self.init_data}
        
        try:
            resp = await client.post(url, headers=self._get_headers(with_auth=False), json=payload)
            if resp.status_code == 200:
                data = resp.json()
                self.token = data.get("token")
                self.state = data.get("state", {})
                self.player = self.state.get("player", {})
                return True
            else:
                print(f"[{self.account_name}] Login failed HTTP {resp.status_code}: {resp.text[:150]}")
                return False
        except httpx.ConnectTimeout:
            print(f"[{self.account_name}] Connection timed out to {BASE_URL}. Target server may be restarting.")
            return False
        except Exception as e:
            print(f"[{self.account_name}] Login error: {e}")
            return False

    async def refresh_state(self, client: httpx.AsyncClient) -> dict:
        """Fetches the latest player and mining state."""
        url = f"{BASE_URL}/api/state"
        try:
            resp = await client.get(url, headers=self._get_headers())
            if resp.status_code == 200:
                data = resp.json()
                self.state = data.get("state", self.state)
                self.player = self.state.get("player", self.player)
                return self.state
        except Exception as e:
            print(f"[{self.account_name}] State refresh error: {e}")
        return self.state

    async def claim_daily_checkin(self, client: httpx.AsyncClient) -> bool:
        """Claims daily checkin task."""
        tasks = self.state.get("tasks", {})
        checkin_task = tasks.get("checkin", {})
        if checkin_task.get("claimed"):
            return False

        url = f"{BASE_URL}/api/tasks/claim"
        payload = {"taskId": "checkin"}
        try:
            resp = await client.post(url, headers=self._get_headers(idempotency=True), json=payload)
            if resp.status_code == 200:
                data = resp.json()
                self.state = data.get("state", self.state)
                reward = checkin_task.get("reward", 10)
                print(f"[{self.account_name}] Daily Check-in Claimed! (+{reward} DIGGO)")
                return True
        except Exception as e:
            print(f"[{self.account_name}] Daily Check-in error: {e}")
        return False

    async def claim_daily_streak(self, client: httpx.AsyncClient) -> bool:
        """Claims available daily streak reward (Day 1 - 7)."""
        day_rewards = self.state.get("dayRewards", [])
        claimed_any = False

        for dr in day_rewards:
            if dr.get("status") == "available":
                day_num = dr.get("day")
                reward = dr.get("diggo", 15)
                url = f"{BASE_URL}/api/streak/claim"
                payload = {"day": day_num}
                try:
                    resp = await client.post(url, headers=self._get_headers(idempotency=True), json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        self.state = data.get("state", self.state)
                        print(f"[{self.account_name}] Daily Streak Day {day_num} Claimed! (+{reward} DIGGO)")
                        claimed_any = True
                except Exception as e:
                    print(f"[{self.account_name}] Streak claim Day {day_num} error: {e}")
        return claimed_any

    async def claim_social_tasks(self, client: httpx.AsyncClient) -> None:
        """Optionally verifies and claims Telegram channel & social tasks."""
        tasks = self.state.get("tasks", {})

        # 1. Telegram Community Task
        tg_task = tasks.get("telegram", {})
        if tg_task and not tg_task.get("claimed"):
            try:
                v_res = await client.post(f"{BASE_URL}/api/tasks/verify", headers=self._get_headers(), json={"taskId": "telegram"})
                if v_res.status_code == 200:
                    c_res = await client.post(f"{BASE_URL}/api/tasks/claim", headers=self._get_headers(idempotency=True), json={"taskId": "telegram"})
                    if c_res.status_code == 200:
                        self.state = c_res.json().get("state", self.state)
                        print(f"[{self.account_name}] Telegram Task Claimed! (+{tg_task.get('reward', 30)} DIGGO)")
            except Exception:
                pass

        # 2. X Follow & Post Tasks (self-reported)
        for task_id in ["x_follow", "x_post"]:
            task_info = tasks.get(task_id, {})
            if task_info and not task_info.get("claimed") and task_info.get("enabled"):
                try:
                    c_res = await client.post(f"{BASE_URL}/api/tasks/claim", headers=self._get_headers(idempotency=True), json={"taskId": task_id})
                    if c_res.status_code == 200:
                        self.state = c_res.json().get("state", self.state)
                        print(f"[{self.account_name}] Social Task '{task_id}' Claimed! (+{task_info.get('reward', 5)} DIGGO)")
                except Exception:
                    pass

    async def claim_mining(self, client: httpx.AsyncClient) -> tuple[bool, int]:
        """
        Claims uncollected mined DIGGO tokens if eligible (8-hour cooldown).
        Returns: (success_bool, seconds_until_next_claim)
        """
        mining = self.state.get("mining", {})
        next_claim_ms = mining.get("nextClaimAt", 0)
        now_ms = int(time.time() * 1000)

        # Calculate time remaining
        remaining_sec = max(0, int((next_claim_ms - now_ms) / 1000)) if next_claim_ms > 0 else 0

        if remaining_sec > 0:
            rem_h = remaining_sec // 3600
            rem_m = (remaining_sec % 3600) // 60
            print(f"[{self.account_name}] Mining still cooling down: {rem_h}h {rem_m}m remaining (Ready at {datetime.fromtimestamp(next_claim_ms / 1000, tz=timezone.utc).strftime('%H:%M:%S UTC')}).")
            return False, remaining_sec

        print(f"[{self.account_name}] Claiming mining rewards (8-hour cycle)...")
        url = f"{BASE_URL}/api/claims/mining"
        try:
            resp = await client.post(url, headers=self._get_headers(idempotency=True), json={})
            if resp.status_code == 200:
                data = resp.json()
                self.state = data.get("state", self.state)
                new_mining = self.state.get("mining", {})
                new_next_ms = new_mining.get("nextClaimAt", 0)
                new_remaining = max(0, int((new_next_ms - int(time.time() * 1000)) / 1000))
                print(f"[{self.account_name}] Mining claimed successfully! Next claim in ~{new_remaining // 3600} hours.")
                return True, new_remaining
            else:
                print(f"[{self.account_name}] Mining claim response: {resp.status_code} {resp.text[:100]}")
        except Exception as e:
            print(f"[{self.account_name}] Mining claim error: {e}")

        # Default fallback to 8 hours (28800 sec)
        return False, 28800

    async def execute_account_flow(self) -> dict:
        """Executes a full check & claim cycle for this account."""
        async with httpx.AsyncClient(timeout=25.0, proxy=self.proxy) as client:
            if self.proxy:
                ip = await self.check_ip(client)
                print(f"[{self.account_name}] Using Proxy: {self.proxy} (Exit IP: {ip})")

            # 1. Login
            if not await self.login(client):
                return {
                    "account": self.account_name,
                    "status": "LOGIN_FAILED",
                    "balance": 0,
                    "next_claim_sec": 300
                }

            initial_bal = self.state.get("balance", 0)
            mining_info = self.state.get("mining", {})
            print(f"[{self.account_name}] Logged In! Balance: {initial_bal} DIGGO | Mining Rate: {mining_info.get('daily', 5)} DIGGO/day")

            # 2. Daily Check-in
            if AUTO_DAILY_CHECKIN:
                await self.claim_daily_checkin(client)

            # 3. Daily Streak
            if AUTO_DAILY_STREAK:
                await self.claim_daily_streak(client)

            # 4. Social Tasks
            if AUTO_TASKS:
                await self.claim_social_tasks(client)

            # 5. Mining Claim (8-hour cycle)
            claimed_mining, next_claim_sec = await self.claim_mining(client)

            # 6. Final State
            final_state = await self.refresh_state(client)
            final_bal = final_state.get("balance", initial_bal)
            wallet_addr = final_state.get("wallet", {}).get("address") or "None"

            print(f"[{self.account_name}] Final Summary -> Balance: {final_bal} DIGGO | Wallet: {wallet_addr}")

            return {
                "account": self.account_name,
                "status": "SUCCESS",
                "balance": final_bal,
                "wallet": wallet_addr,
                "mining_daily": mining_info.get("daily", 5),
                "claimed_mining": claimed_mining,
                "next_claim_sec": next_claim_sec,
                "ip": self.outbound_ip
            }
