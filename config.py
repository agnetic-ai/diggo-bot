"""
Central Configuration & .env InitData Parser for DIGGO Miner Bot
"""

import os
import json
import re
from urllib.parse import urlsplit, parse_qs, unquote

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(BASE_DIR, ".env")

# ==============================================================================
# 1. Core Endpoints & Parameters
# ==============================================================================
BASE_URL = "https://app.diggocoin.com"
DEFAULT_REF = "ref_0615dd5877f9bdaa953fc770"

# ==============================================================================
# 2. Proxy Configuration (Opsional)
# ==============================================================================
# Pilihan PROXY_MODE:
# - "none"  : Tanpa proxy (koneksi langsung)
# - "tor"   : Menggunakan Tor SOCKS5 lokal dengan stream isolation per akun
# - "list"  : Menggunakan daftar proxy di PROXY_LIST (rotasi round-robin)
# - "single": Menggunakan satu proxy tunggal di PROXY_URL
PROXY_MODE = "tor"

PROXY_URL = "socks5://127.0.0.1:9050"
TOR_PROXY = "socks5://127.0.0.1:9050"
PROXY_LIST = [
    # "http://user:pass@ip1:port",
    # "socks5://user:pass@ip2:port"
]

# ==============================================================================
# 3. Mining & Task Settings
# ==============================================================================
MINING_INTERVAL_HOURS = 8      # Siklus klaim mining (default 8 jam)

# Task Selection (Hanya 5 Task yang Diminta)
TASK_DAILY_CHECKIN = True      # 1. Daily Check-in
TASK_DAILY_STREAK = True       # 2. Daily Streak Day 1-7
TASK_PLAY_GAME = True          # 3. Play Game
TASK_SELF_REPORT_SOCIAL = True # 4. Self-report Social (x_follow, x_post, community_react)
TASK_WATCH_ADS = True          # 5. Tonton Iklan (Adsgram)

ACCOUNT_DELAY_SECONDS = 3      # Jeda antar akun (detik)


# ==============================================================================
# 4. Proxy Rotator Engine
# ==============================================================================
class ProxyRotator:
    def __init__(self):
        self.mode = PROXY_MODE.lower()
        self.proxy_list = PROXY_LIST
        self._index = 0

    def get_proxy(self, account_name: str = "default") -> str | None:
        if self.mode == "none":
            return None
        elif self.mode == "single":
            return PROXY_URL
        elif self.mode == "tor":
            host = TOR_PROXY.replace("socks5://", "").replace("socks5h://", "")
            return f"socks5://{account_name}:diggo@{host}"
        elif self.mode == "list":
            if not self.proxy_list:
                return None
            proxy = self.proxy_list[self._index % len(self.proxy_list)]
            self._index += 1
            return proxy
        return None


# ==============================================================================
# 5. .env InitData Parser
# ==============================================================================
def clean_init_data_string(raw_text: str) -> str:
    """Membersihkan dan mengekstrak data initData dari baris string mentah."""
    if not raw_text:
        return ""
    data = raw_text.strip().strip('"').strip("'")

    # Jika user menempelkan URL lengkap (misal https://diggo.linkpc.net/#tgWebAppData=...)
    if "#" in data:
        data = data.split("#", 1)[1]

    if "tgWebAppData=" in data:
        match = re.search(r"tgWebAppData=([^&#]+)", data)
        if match:
            data = match.group(1)

    # Jika string ter-encode URL (%3D dan %26)
    if ("%3D" in data or "%3d" in data) and ("%26" in data or "%26" in data.lower()):
        data = unquote(data)

    # Hapus parameter client-side Telegram WebApp yang bukan bagian dari validasi initData
    for param in ["&tgWebAppVersion=", "&tgWebAppPlatform=", "&tgWebAppThemeParams="]:
        if param in data:
            data = data.split(param)[0]

    return data


def extract_username(init_str: str, fallback_idx: int = 1) -> str:
    """Mengekstrak username atau nama user dari payload JSON di initData."""
    try:
        parsed = parse_qs(init_str)
        if "user" in parsed:
            user_data = json.loads(parsed["user"][0])
            name = user_data.get("username") or user_data.get("first_name") or str(user_data.get("id"))
            if name:
                return name
    except Exception:
        pass
    return f"akun_{fallback_idx:02d}"


def get_configured_accounts() -> list:
    """
    Membaca berkas .env secara langsung baris demi baris.
    Mendukung format:
    1. Baris murni langsung: user=...&hash=... (atau query_id=...&user=...&hash=...)
    2. Multi-akun: 1 baris per akun
    3. Tetap mendukung jika ada prefix variabel seperti INIT_DATA=...
    """
    if not os.path.exists(ENV_FILE):
        return []

    accounts = []
    with open(ENV_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    idx = 1
    for raw_line in lines:
        line = raw_line.strip()
        # Lewati baris kosong atau komentar
        if not line or line.startswith("#"):
            continue

        # Jika ada format KEY=VALUE konvensional (selain yang diawali user= atau query_id=)
        if re.match(r"^[A-Za-z0-9_]+=", line) and not (line.startswith("user=") or line.startswith("query_id=")):
            val = line.split("=", 1)[1].strip()
        else:
            val = line

        cleaned = clean_init_data_string(val)
        if cleaned and "hash=" in cleaned:
            name = extract_username(cleaned, idx)
            accounts.append({
                "name": name,
                "init_data": cleaned
            })
            idx += 1

    return accounts
