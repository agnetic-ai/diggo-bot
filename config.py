"""
Configuration loader and Account parser for DIGGO Miner Bot
"""

import os
import json
import re
from urllib.parse import urlsplit, parse_qs, unquote
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

BASE_URL = os.environ.get("BASE_URL", "https://diggo.linkpc.net").rstrip("/")
DEFAULT_REF = os.environ.get("DEFAULT_REF", "ref_0615dd5877f9bdaa953fc770")

PROXY_MODE = os.environ.get("PROXY_MODE", "none").lower()
PROXY_URL = os.environ.get("PROXY_URL", "socks5://127.0.0.1:9050")
TOR_PROXY = os.environ.get("TOR_PROXY", "socks5://127.0.0.1:9050")
PROXY_LIST = [p.strip() for p in os.environ.get("PROXY_LIST", "").split(",") if p.strip()]

MINING_INTERVAL_HOURS = float(os.environ.get("MINING_INTERVAL_HOURS", 8))
AUTO_DAILY_CHECKIN = os.environ.get("AUTO_DAILY_CHECKIN", "true").lower() == "true"
AUTO_DAILY_STREAK = os.environ.get("AUTO_DAILY_STREAK", "true").lower() == "true"
AUTO_TASKS = os.environ.get("AUTO_TASKS", "true").lower() == "true"
ACCOUNT_DELAY_SECONDS = float(os.environ.get("ACCOUNT_DELAY_SECONDS", 3))


def clean_init_data(raw_data: str) -> str:
    """Extracts and sanitizes clean initData / tgWebAppData string."""
    if not raw_data:
        return ""
    data = raw_data.strip().strip('"').strip("'")
    
    # Check if a full URL was provided
    if "#" in data or "tgWebAppData=" in data:
        try:
            frag = urlsplit(data).fragment if "#" in data else data
            parsed = parse_qs(frag)
            if "tgWebAppData" in parsed:
                return parsed["tgWebAppData"][0]
        except Exception:
            pass

    # Extract tgWebAppData directly if present in query format
    if "tgWebAppData=" in data:
        match = re.search(r"tgWebAppData=([^&#]+)", data)
        if match:
            return unquote(match.group(1))

    return data


def extract_username_from_init(init_data: str, fallback_idx: int = 1) -> str:
    """Tries to extract user username or first_name or user_id for logging."""
    try:
        parsed = parse_qs(init_data)
        if "user" in parsed:
            user_json = json.loads(parsed["user"][0])
            return user_json.get("username") or user_json.get("first_name") or str(user_json.get("id"))
    except Exception:
        pass
    return f"account_{fallback_idx}"


class ProxyRotator:
    def __init__(self):
        self.mode = PROXY_MODE
        self.proxy_list = PROXY_LIST
        self._index = 0

    def get_proxy(self, account_name: str = "default") -> str | None:
        if self.mode == "none":
            return None
        elif self.mode == "single":
            return PROXY_URL
        elif self.mode == "tor":
            # Stream isolation via credentials
            host = TOR_PROXY.replace("socks5://", "").replace("socks5h://", "")
            return f"socks5://{account_name}:diggo@{host}"
        elif self.mode == "list":
            if not self.proxy_list:
                return None
            proxy = self.proxy_list[self._index % len(self.proxy_list)]
            self._index += 1
            return proxy
        return None


def get_configured_accounts() -> list:
    """Returns list of account dicts: [{'name': ..., 'init_data': ...}]"""
    accounts = []
    
    # 1. Check ACCOUNTS_INIT_DATA JSON string
    raw_accounts = os.environ.get("ACCOUNTS_INIT_DATA")
    if raw_accounts:
        try:
            parsed_accounts = json.loads(raw_accounts)
            if isinstance(parsed_accounts, list):
                for idx, a in enumerate(parsed_accounts, 1):
                    init_str = clean_init_data(a.get("init_data") or a.get("tgWebAppData") or "")
                    if init_str:
                        name = a.get("name") or extract_username_from_init(init_str, idx)
                        accounts.append({"name": name, "init_data": init_str})
        except Exception as e:
            print(f"[Config Warning] Error parsing ACCOUNTS_INIT_DATA: {e}")

    # 2. Check main INIT_DATA or TG_WEB_APP_DATA
    main_init = os.environ.get("INIT_DATA") or os.environ.get("TG_WEB_APP_DATA")
    if main_init:
        clean_main = clean_init_data(main_init)
        if clean_main and not any(a["init_data"] == clean_main for a in accounts):
            accounts.insert(0, {
                "name": extract_username_from_init(clean_main, 1),
                "init_data": clean_main
            })

    # 3. Check numbered INIT_DATA_1, INIT_DATA_2, etc.
    for k, v in os.environ.items():
        if k.startswith("INIT_DATA_") or k.startswith("TG_WEB_APP_DATA_"):
            clean_v = clean_init_data(v)
            if clean_v and not any(a["init_data"] == clean_v for a in accounts):
                accounts.append({
                    "name": extract_username_from_init(clean_v, len(accounts) + 1),
                    "init_data": clean_v
                })

    return accounts
