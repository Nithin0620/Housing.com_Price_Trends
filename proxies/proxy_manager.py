import os
import random
import threading
from pathlib import Path


class ProxyManager:
    def __init__(self, proxy_file=None):
        self.lock = threading.Lock()
        self.proxies = []
        self._load_proxies(proxy_file)

    def _load_proxies(self, proxy_file):
        if proxy_file is None:
            proxy_file = Path(__file__).parent / "proxies.txt"
        proxy_file = Path(proxy_file)
        if proxy_file.exists():
            with open(proxy_file) as f:
                self.proxies = [line.strip() for line in f if line.strip()]
        if not self.proxies:
            self.proxies.append(None)

    def get_proxy(self):
        with self.lock:
            proxy = random.choice(self.proxies)
        if proxy is None:
            return None
        return {"server": proxy}

    def format_for_playwright(self):
        with self.lock:
            proxy = random.choice(self.proxies)
        if proxy is None:
            return None
        return {"server": proxy}

    def format_for_curl(self):
        with self.lock:
            proxy = random.choice(self.proxies)
        if proxy is None:
            return None
        return {"http": proxy, "https": proxy}

    def get_curl_proxies(self):
        """Return curl_cffi-compatible proxies dict or None."""
        p = self.get_proxy()
        if p is None:
            return None
        return {"http": p["server"], "https": p["server"]}
