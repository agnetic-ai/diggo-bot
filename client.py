"""
DIGGO Miner Client API Implementation
Strictly executes only specified task categories:
1. Daily Check-in
2. Daily Streak
3. Play Game
4. Self-Reported Social Tasks
5. Watch Ads (Adsgram)
6. 8-Hour Mining Harvest
"""

import os
import json
import time
import uuid
import asyncio
import base64
import httpx
from datetime import datetime, timezone
from urllib.parse import parse_qs, unquote

from config import (
    BASE_URL,
    TASK_DAILY_CHECKIN,
    TASK_DAILY_STREAK,
    TASK_PLAY_GAME,
    TASK_SELF_REPORT_SOCIAL,
    TASK_WATCH_ADS
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

    async def try_refresh_init_data(self) -> bool:
        """
        Attempts to generate fresh initData on-the-fly from the Telegram session
        if available in /opt/telegram-multi-account/sessions/
        """
        session_dir = "/opt/telegram-multi-account/sessions"
        if not os.path.exists(session_dir):
            return False

        session_name = None
        # 1. Try session_map.json lookup
        map_path = os.path.join(os.path.dirname(__file__), "session_map.json")
        if os.path.exists(map_path):
            try:
                with open(map_path, "r", encoding="utf-8") as mf:
                    s_map = json.load(mf)
                qs = parse_qs(self.init_data)
                user_str = qs.get("user", [""])[0]
                if user_str:
                    user_obj = json.loads(unquote(user_str))
                    uid = str(user_obj.get("id"))
                    uname = (user_obj.get("username") or "").lower()
                    session_name = s_map.get(uid) or s_map.get(uname)
                if not session_name:
                    session_name = s_map.get(self.account_name.lower())
            except Exception:
                pass

        # 2. Try direct filename candidate match
        if not session_name:
            for candidate in [self.account_name, self.account_name.lower()]:
                if os.path.exists(os.path.join(session_dir, f"{candidate}.session")):
                    session_name = candidate
                    break

        if not session_name or session_name == "ombengz":
            return False

        session_path = os.path.join(session_dir, f"{session_name}.session")
        if not os.path.exists(session_path):
            return False

        try:
            from telethon import TelegramClient, functions
            from urllib.parse import urlsplit

            api_id = 37429744
            api_hash = "491629652b9115dfcf86a185a7bc6bc5"

            client = TelegramClient(session_path, api_id, api_hash)
            await client.connect()
            if not await client.is_user_authorized():
                await client.disconnect()
                return False

            bot = await client.get_entity("Diggominer_bot")
            input_bot = await client.get_input_entity(bot)
            res = await client(functions.messages.RequestMainWebViewRequest(
                peer=input_bot,
                bot=input_bot,
                platform="android",
                start_param="ref_0615dd5877f9bdaa953fc770"
            ))
            await client.disconnect()

            frag = urlsplit(res.url).fragment
            new_init = parse_qs(frag).get("tgWebAppData", [""])[0]
            if new_init and "hash=" in new_init:
                self.init_data = new_init
                print(f"[{self.account_name}] initData otomatis diperbarui via session '{session_name}'! (Fresh auth_date)")
                return True
        except Exception as e:
            print(f"[{self.account_name}] Auto-refresh initData error: {e}")

        return False

    async def login(self, client: httpx.AsyncClient) -> bool:
        """Authenticates with DIGGO backend using initData, with auto-refresh fallback."""
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
            elif resp.status_code == 401 and "expired_init_data" in resp.text:
                print(f"[{self.account_name}] initData expired. Mengambil auth_date fresh via session Telegram...")
                if await self.try_refresh_init_data():
                    retry_resp = await client.post(url, headers=self._get_headers(with_auth=False), json={"initData": self.init_data})
                    if retry_resp.status_code == 200:
                        data = retry_resp.json()
                        self.token = data.get("token")
                        self.state = data.get("state", {})
                        self.player = self.state.get("player", {})
                        print(f"[{self.account_name}] Login sukses setelah auto-refresh!")
                        return True
                    else:
                        print(f"[{self.account_name}] Login gagal setelah auto-refresh: HTTP {retry_resp.status_code}")
                        return False
            else:
                print(f"[{self.account_name}] Login failed HTTP {resp.status_code}: {resp.text[:150]}")
                return False
        except httpx.ConnectTimeout:
            print(f"[{self.account_name}] Connection timed out to {BASE_URL}.")
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

    # --------------------------------------------------------------------------
    # 1. Daily Check-in
    # --------------------------------------------------------------------------
    async def claim_daily_checkin(self, client: httpx.AsyncClient) -> bool:
        """Claims daily checkin task."""
        tasks = self.state.get("tasks", {})
        checkin_task = tasks.get("checkin", {})
        if not checkin_task or checkin_task.get("claimed"):
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

    # --------------------------------------------------------------------------
    # 2. Daily Streak (Day 1 - 7)
    # --------------------------------------------------------------------------
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

    # --------------------------------------------------------------------------
    # 3. Play Game Task
    # --------------------------------------------------------------------------
    async def claim_play_game(self, client: httpx.AsyncClient) -> bool:
        """Claims 'play' game task when progress >= total."""
        play_task = self.state.get("tasks", {}).get("play", {})
        if not play_task or play_task.get("claimed") or not play_task.get("enabled", True):
            return False

        prog = play_task.get("progress", 0)
        total = play_task.get("total", 1)
        if prog >= total:
            try:
                resp = await client.post(
                    f"{BASE_URL}/api/tasks/claim",
                    headers=self._get_headers(idempotency=True),
                    json={"taskId": "play"}
                )
                if resp.status_code == 200:
                    self.state = resp.json().get("state", self.state)
                    reward = play_task.get("reward", 10)
                    print(f"[{self.account_name}] Play Game Task Claimed! (+{reward} DIGGO)")
                    return True
            except Exception as e:
                print(f"[{self.account_name}] Play Game Task claim error: {e}")
        return False

    # --------------------------------------------------------------------------
    # 4. Self-Reported Social Tasks
    # --------------------------------------------------------------------------
    async def claim_self_reported_social(self, client: httpx.AsyncClient) -> None:
        """Starts, waits, confirms, and claims self-reported social tasks (x_follow, x_post, community_react)."""
        tasks = self.state.get("tasks", {})

        for task_id, task_info in tasks.items():
            if not task_info or task_info.get("claimed") or not task_info.get("enabled", True):
                continue
            if task_info.get("verification") != "self_reported":
                continue

            try:
                print(f"[{self.account_name}] Starting self-reported task '{task_id}'...")
                r_start = await client.post(f"{BASE_URL}/api/tasks/social/start", headers=self._get_headers(), json={"taskId": task_id})
                if r_start.status_code == 200:
                    start_data = r_start.json()
                    attempt = start_data.get("attempt", {})
                    attempt_id = attempt.get("attemptId")
                    confirm_at = attempt.get("confirmAt", 0)
                    now_ms = int(time.time() * 1000)
                    wait_sec = max(0, (confirm_at - now_ms) / 1000.0)

                    if wait_sec > 0:
                        print(f"[{self.account_name}] Waiting {wait_sec:.1f}s confirmation delay for '{task_id}'...")
                        await asyncio.sleep(wait_sec + 1.0)

                    r_conf = await client.post(
                        f"{BASE_URL}/api/tasks/social/confirm",
                        headers=self._get_headers(),
                        json={"taskId": task_id, "attemptId": attempt_id, "confirmed": True}
                    )
                    if r_conf.status_code == 200:
                        r_claim = await client.post(
                            f"{BASE_URL}/api/tasks/claim",
                            headers=self._get_headers(idempotency=True),
                            json={"taskId": task_id}
                        )
                        if r_claim.status_code == 200:
                            self.state = r_claim.json().get("state", self.state)
                            reward = task_info.get("reward", 5)
                            print(f"[{self.account_name}] Self-reported Task '{task_id}' Claimed! (+{reward} DIGGO)")
            except Exception as e:
                print(f"[{self.account_name}] Error completing task '{task_id}': {e}")

    # --------------------------------------------------------------------------
    # 5. Tonton Iklan (Adsgram)
    # --------------------------------------------------------------------------
    def _build_data_check_string(self) -> str:
        """Builds base64url-encoded data_check_string for Adsgram verification."""
        params = parse_qs(self.init_data)
        items = []
        for k, v in params.items():
            if k not in ["hash", "signature"]:
                items.append(f"{k}={v[0]}")
        items.sort()
        dcs = "\n".join(items)
        return base64.urlsafe_b64encode(dcs.encode("utf-8")).decode("utf-8").rstrip("=")

    async def claim_watch_ads(self, client: httpx.AsyncClient) -> None:
        """Watches Adsgram ads, triggers real tracking events, and claims DIGGO rewards."""
        ad_task = self.state.get("tasks", {}).get("ad", {})
        if not ad_task or ad_task.get("claimed") or not ad_task.get("enabled", True):
            return

        quota_used = ad_task.get("quotaUsed", 0)
        quota_total = ad_task.get("quotaTotal", 4)
        if quota_used >= quota_total:
            print(f"[{self.account_name}] Kuota iklan harian sudah penuh ({quota_used}/{quota_total}).")
            return

        remaining_slots = quota_total - quota_used
        print(f"[{self.account_name}] Memproses tonton iklan ({remaining_slots} slot tersisa)...")

        params = parse_qs(self.init_data)
        user_id = str(self.player.get("id") or "")
        sig = params.get("signature", [""])[0]
        dcs_b64 = self._build_data_check_string()
        block_id = str(ad_task.get("blockId") or "54249")

        for slot in range(remaining_slots):
            try:
                # 1. Inisiasi sesi iklan ke DIGGO backend
                r_start = await client.post(f"{BASE_URL}/api/adsgram/start", headers=self._get_headers(), json={})
                if r_start.status_code != 200:
                    print(f"[{self.account_name}] Gagal start iklan #{slot+1}: HTTP {r_start.status_code}")
                    break

                start_res = r_start.json()
                attempt_id = start_res.get("attemptId")
                self.state = start_res.get("state", self.state)

                if start_res.get("ready"):
                    r_claim = await client.post(
                        f"{BASE_URL}/api/tasks/claim",
                        headers=self._get_headers(idempotency=True),
                        json={"taskId": "ad"}
                    )
                    if r_claim.status_code == 200:
                        self.state = r_claim.json().get("state", self.state)
                        print(f"[{self.account_name}] Iklan #{slot+1} Langsung Diklaim! (+10 DIGGO)")
                        continue

                # 2. Request rewarded ad payload dari Adsgram Network
                adv_params = {
                    "envType": "telegram",
                    "blockId": block_id,
                    "platform": "Linux aarch64",
                    "language": "en",
                    "top_domain": "app.diggocoin.com",
                    "signature": sig,
                    "data_check_string": dcs_b64,
                    "tg_id": user_id,
                    "tg_platform": "android",
                    "tma_version": "9.6"
                }
                ads_headers = {
                    "User-Agent": HEADERS_BASE["User-Agent"],
                    "Origin": "https://app.diggocoin.com",
                    "Referer": "https://app.diggocoin.com/"
                }

                r_adv = await client.get("https://api.adsgram.ai/adv", params=adv_params, headers=ads_headers)
                if r_adv.status_code != 200:
                    print(f"[{self.account_name}] Gagal memuat iklan dari Adsgram: HTTP {r_adv.status_code}")
                    break

                adv_json = r_adv.json()
                trackings = adv_json.get("banner", {}).get("trackings", [])
                track_map = {t["name"]: t["value"] for t in trackings}

                # 3. Trigger tracking render & show
                if "render" in track_map:
                    await client.get(track_map["render"], headers=ads_headers)
                if "show" in track_map:
                    await client.get(track_map["show"], headers=ads_headers)

                # 4. Putar video iklan (16 detik)
                print(f"[{self.account_name}] Menonton video iklan #{slot+1} (16 detik)...")
                await asyncio.sleep(16)

                # 5. Trigger tracking reward ke Adsgram (memicu webhook callback server Adsgram ke DIGGO)
                if "reward" in track_map:
                    await client.get(track_map["reward"], headers=ads_headers)

                # 6. Kirim sinyal complete ke DIGGO
                await client.post(
                    f"{BASE_URL}/api/adsgram/complete",
                    headers=self._get_headers(),
                    json={"attemptId": attempt_id}
                )

                # 7. Polling status & klaim reward ke DIGGO
                claimed = False
                for _ in range(5):
                    await asyncio.sleep(2)
                    r_st = await client.get(f"{BASE_URL}/api/state", headers=self._get_headers())
                    if r_st.status_code == 200:
                        cur_ad = r_st.json().get("state", {}).get("tasks", {}).get("ad", {})
                        if cur_ad.get("progress", 0) >= cur_ad.get("total", 1) and not cur_ad.get("claimed"):
                            r_claim = await client.post(
                                f"{BASE_URL}/api/tasks/claim",
                                headers=self._get_headers(idempotency=True),
                                json={"taskId": "ad"}
                            )
                            if r_claim.status_code == 200:
                                self.state = r_claim.json().get("state", self.state)
                                print(f"[{self.account_name}] Iklan #{slot+1} Sukses Diklaim! (+10 DIGGO)")
                                claimed = True
                                break
                if not claimed:
                    print(f"[{self.account_name}] Iklan #{slot+1} Selesai diputar.")
            except Exception as e:
                print(f"[{self.account_name}] Error proses iklan #{slot+1}: {e}")
                break

    # --------------------------------------------------------------------------
    # 6. Mining Harvest (8-Hour Cycle)
    # --------------------------------------------------------------------------
    async def claim_mining(self, client: httpx.AsyncClient) -> tuple[bool, int]:
        """
        Claims uncollected mined DIGGO tokens if eligible (8-hour cooldown).
        Returns: (success_bool, seconds_until_next_claim)
        """
        mining = self.state.get("mining", {})
        next_claim_ms = mining.get("nextClaimAt", 0)
        now_ms = int(time.time() * 1000)

        remaining_sec = max(0, int((next_claim_ms - now_ms) / 1000)) if next_claim_ms > 0 else 0

        if remaining_sec > 0:
            rem_h = remaining_sec // 3600
            rem_m = (remaining_sec % 3600) // 60
            print(f"[{self.account_name}] Mining cooldown: {rem_h}h {rem_m}m tersisa (Siap pada {datetime.fromtimestamp(next_claim_ms / 1000, tz=timezone.utc).strftime('%H:%M:%S UTC')}).")
            return False, remaining_sec

        print(f"[{self.account_name}] Mengklaim hasil penambangan (siklus 8 jam)...")
        url = f"{BASE_URL}/api/claims/mining"
        try:
            resp = await client.post(url, headers=self._get_headers(idempotency=True), json={})
            if resp.status_code == 200:
                data = resp.json()
                self.state = data.get("state", self.state)
                new_mining = self.state.get("mining", {})
                new_next_ms = new_mining.get("nextClaimAt", 0)
                new_remaining = max(0, int((new_next_ms - int(time.time() * 1000)) / 1000))
                print(f"[{self.account_name}] Mining berhasil diklaim! Siklus berikutnya dalam ~{new_remaining // 3600} jam.")
                return True, new_remaining
            else:
                print(f"[{self.account_name}] Mining claim response: {resp.status_code} {resp.text[:100]}")
        except Exception as e:
            print(f"[{self.account_name}] Mining claim error: {e}")

        return False, 28800

    # --------------------------------------------------------------------------
    # Main Execution Flow per Account
    # --------------------------------------------------------------------------
    async def execute_account_flow(self) -> dict:
        """Executes the exact requested task categories."""
        async with httpx.AsyncClient(timeout=25.0, proxy=self.proxy) as client:
            if self.proxy:
                ip = await self.check_ip(client)
                print(f"[{self.account_name}] Using Proxy: {self.proxy} (Exit IP: {ip})")

            # Login
            if not await self.login(client):
                return {
                    "account": self.account_name,
                    "status": "LOGIN_FAILED",
                    "balance": 0,
                    "next_claim_sec": 300
                }

            initial_bal = self.state.get("balance", 0)
            mining_info = self.state.get("mining", {})
            print(f"[{self.account_name}] Logged In! Saldo: {initial_bal} DIGGO | Mining Rate: {mining_info.get('daily', 5)} DIGGO/hari")

            # 1. Daily Check-in
            if TASK_DAILY_CHECKIN:
                await self.claim_daily_checkin(client)

            # 2. Daily Streak
            if TASK_DAILY_STREAK:
                await self.claim_daily_streak(client)

            # 3. Play Game Task
            if TASK_PLAY_GAME:
                await self.claim_play_game(client)

            # 4. Self-Reported Social Tasks (x_follow, x_post, community_react)
            if TASK_SELF_REPORT_SOCIAL:
                await self.claim_self_reported_social(client)

            # 5. Tonton Iklan (Adsgram)
            if TASK_WATCH_ADS:
                await self.claim_watch_ads(client)

            # 6. Mining Claim (Siklus 8 Jam)
            claimed_mining, next_claim_sec = await self.claim_mining(client)

            # Final Refresh
            final_state = await self.refresh_state(client)
            final_bal = final_state.get("balance", initial_bal)
            wallet_addr = final_state.get("wallet", {}).get("address") or "None"

            print(f"[{self.account_name}] Ringkasan -> Saldo Akhir: {final_bal} DIGGO | Wallet: {wallet_addr}")

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
