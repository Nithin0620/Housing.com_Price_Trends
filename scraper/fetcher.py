import time
import random
from urllib.parse import urljoin

from curl_cffi import requests


REQUEST_DELAY = 1.5

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

CHROME_VERSIONS = ["chrome124", "chrome123", "chrome120", "chrome110", "chrome116", "chrome99_android"]


class PageFetcher:
    def __init__(self, proxy_manager=None, delay=REQUEST_DELAY):
        self.proxy_manager = proxy_manager
        self.delay = delay
        self.session = requests.Session()

    def fetch_html(self, url, impersonate=None):
        time.sleep(self.delay + random.uniform(0, 0.5))

        if impersonate is None:
            impersonate = random.choice(CHROME_VERSIONS)

        proxy = self.proxy_manager.format_for_curl() if self.proxy_manager else None

        try:
            resp = self.session.get(
                url,
                impersonate=impersonate,
                headers=HEADERS,
                proxies=proxy,
                timeout=60,
            )
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            print(f"  [FETCH] Failed to load {url}: {e}")
            return None
