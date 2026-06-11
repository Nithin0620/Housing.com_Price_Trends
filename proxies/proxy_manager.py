import random
import threading
from pathlib import Path


class ProxyManager:
    def __init__(self, proxy_file=None):
        self.lock = threading.Lock()
        self.proxies = []
        self._load_proxies(proxy_file)
        self._log_proxy_info()

    def _load_proxies(self, proxy_file):
        if proxy_file is None:
            proxy_file = Path(__file__).parent / "proxies.txt"
        proxy_file = Path(proxy_file)
        if proxy_file.exists():
            with open(proxy_file) as f:
                self.proxies = [line.strip() for line in f if line.strip()]
        if not self.proxies:
            self.proxies.append(None)

    def _log_proxy_info(self):
        if not self.proxies or self.proxies[0] is None:
            print("  [PROXY] No proxy configured — using direct connection")
            return
        sample = self.proxies[0]
        if "rotate" in sample.split("@")[0].split(":")[0].split("//")[-1].lower():
            print("  [PROXY] Rotating proxy detected — new IP on every request")
        else:
            print("  [PROXY] Static proxy — same IP for all requests")

    def get_proxy(self):
        with self.lock:
            proxy = random.choice(self.proxies)
        if proxy is None:
            return None
        return {"server": proxy}

    @property
    def is_rotating(self):
        if not self.proxies or self.proxies[0] is None:
            return False
        username = self.proxies[0].split("@")[0].split("://")[-1]
        return "rotate" in username.lower()

    def format_for_curl(self):
        with self.lock:
            proxy = random.choice(self.proxies)
        if proxy is None:
            return None
        return {"http": proxy, "https": proxy}

