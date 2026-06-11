import re
import csv
import os
import time
import random
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from curl_cffi import requests
from proxies.proxy_manager import ProxyManager

MOBILE_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "accept-language": "en-US,en;q=0.9",
    "user-agent": "Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Mobile Safari/537.36",
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "none",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
}

CHROME_VERSIONS = ["chrome124", "chrome123", "chrome120", "chrome110"]
MAX_RETRIES = 5


def _timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _slugify_url(name):
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"\s+", "_", s)
    return s


def _construct_city_page_url(city_name):
    slug = _slugify_url(city_name)
    return f"https://housing.com/in/buy/real-estate-{slug}"


def _extract_state_suffix(html, city_slug):
    """Extract state suffix (e.g. 'gujarat', 'maharashtra', 'india') from SEO URLs."""
    # Look for pattern: /{city}-{state}-overview-{hash}
    pattern = rf'/{re.escape(city_slug)}-([a-z]+)-overview-P[a-z0-9]+'
    m = re.search(pattern, html)
    if m:
        return m.group(1)

    # Try rent URLs: /rent/flats-for-rent-in-{city}-{state}-P{hash}
    pattern = rf'/rent/[^"]*{re.escape(city_slug)}-([a-z]+)-P[a-z0-9]+'
    m = re.search(pattern, html)
    if m:
        return m.group(1)

    return None


def _extract_city_hash(html, city_slug):
    """Extract the P-hash for a city from SEO URLs."""
    # Look for pattern: /{city}-{state}-overview-{hash}
    pattern = rf'/{re.escape(city_slug)}-[a-z]+-overview-(P[a-z0-9]+)'
    m = re.search(pattern, html)
    if m:
        return m.group(1)

    # Try: /rent/...-{city}-{state}-P{hash}
    pattern = rf'/rent/[^"]*{re.escape(city_slug)}-[a-z]+-(P[a-z0-9]+)'
    m = re.search(pattern, html)
    if m:
        return m.group(1)

    # Fallback: any P-hash associated with this city
    pattern = rf'[^"]*{re.escape(city_slug)}[^"]*(P[a-z0-9]{{15,25}})'
    all_matches = re.findall(pattern, html)
    if all_matches:
        return all_matches[0]

    return None


def _construct_price_trend_url(city_slug, state_suffix, city_hash):
    """Build the price trends URL."""
    return f"https://housing.com/price-trends/property-rates-for-buy-in-{city_slug}_{state_suffix}-{city_hash}"


def _extract_price_trend_url(page_text, city_slug):
    """Try to find the price trends URL from a city landing page."""
    if not page_text or "__INITIAL_STATE__" not in page_text:
        return None

    # Parse INITIAL_STATE JSON
    start = page_text.find('window.__INITIAL_STATE__=JSON.parse("')
    if start < 0:
        return None
    start += len('window.__INITIAL_STATE__=JSON.parse("')
    end = page_text.find('")', start)
    if end < 0:
        return None

    raw = page_text[start:end]
    raw = raw.encode().decode("unicode_escape")
    data = json.loads(raw)

    # Dump to string for regex search
    dump = json.dumps(data)

    # Method 1: Direct price-trends URL in state
    urls = re.findall(r'"([^"]*price-trends/property-rates-for-buy-in-[^"]+)"', dump)
    if urls:
        u = urls[0]
        return f"https://housing.com{u}" if u.startswith("/") else u

    # Method 2: Extract city_slug, state, hash from SEO data
    city_hash = _extract_city_hash(dump, city_slug)
    state_suffix = _extract_state_suffix(dump, city_slug)

    if city_hash and state_suffix:
        return _construct_price_trend_url(city_slug, state_suffix, city_hash)

    # Method 3: Try routeParams
    url = data.get("routeParams", {}).get("url", "")
    if "price-trends" in url:
        return f"https://housing.com{url}" if url.startswith("/") else url

    return None


def _fetch_with_retry(city_name, proxy_mgr, delay):
    city_url = _construct_city_page_url(city_name)
    city_slug = _slugify_url(city_name)

    for attempt in range(1, MAX_RETRIES + 1):
        imp = random.choice(CHROME_VERSIONS)
        proxies = proxy_mgr.get_curl_proxies()

        try:
            time.sleep(delay)
            headers = dict(MOBILE_HEADERS)
            r = requests.get(
                city_url,
                impersonate=imp,
                headers=headers,
                proxies=proxies,
                timeout=30,
            )

            if r.status_code == 406:
                print(f"{r.status_code}", end=" " if attempt < MAX_RETRIES else "", flush=True)
                continue

            if r.status_code != 200:
                print(f"{r.status_code}", end=" ", flush=True)
                continue

            pt_url = _extract_price_trend_url(r.text, city_slug)
            if pt_url:
                return pt_url

            print(f"200_no_link", end=" ", flush=True)

        except Exception as e:
            print(f"err({e})", end=" ", flush=True)

    return None


def scrape_city_list(cities_txt_path="data/cities.txt", delay=3.0, output_dir="data", proxy_manager=None):
    with open(cities_txt_path) as f:
        lines = [line.strip() for line in f if line.strip()]

    city_names = lines
    proxy_mgr = proxy_manager or ProxyManager()

    results = []
    failed = []

    for i, city_name in enumerate(city_names):
        print(f"  [{i+1}/{len(city_names)}] {city_name}: ", end="", flush=True)

        pt_url = _fetch_with_retry(city_name, proxy_mgr, delay)

        if pt_url:
            print("OK")
        else:
            print("FAILED")
            failed.append(city_name)

        results.append({
            "city_name": city_name,
            "city_page_url": _construct_city_page_url(city_name),
            "price_trend_url": pt_url or "",
        })

    if failed:
        print(f"\n  Failed ({len(failed)}): {', '.join(failed)}")

    return results


def write_cities_csv(results, output_dir="data"):
    ts = _timestamp()
    filename = f"Housing.com_city_list_{ts}.csv"

    os.makedirs(output_dir, exist_ok=True)
    filepath = Path(output_dir) / filename

    fieldnames = ["city_name", "city_page_url", "price_trend_url"]

    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in results:
            writer.writerow(row)

    print(f"\n  > {filepath} ({len(results)} cities)")
    return filepath


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Scrape housing.com city list for price trend URLs")
    parser.add_argument("--cities", default="data/cities.txt", help="Path to cities text file")
    parser.add_argument("--output", default="data", help="Output directory for CSV")
    parser.add_argument("--delay", type=float, default=3.0, help="Delay between requests (seconds)")
    parser.add_argument("--proxy-file", help="Proxy list file (one per line)")

    args = parser.parse_args()

    proxy_mgr = ProxyManager(args.proxy_file) if args.proxy_file else ProxyManager()
    results = scrape_city_list(args.cities, delay=args.delay, output_dir=args.output)
    write_cities_csv(results, args.output)
