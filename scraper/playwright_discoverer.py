import re
import csv
import os
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright
PROXY_SERVER = "http://p.webshare.io:80"
PROXY_USER = "pzowwsjx-rotate"
PROXY_PASS = "csfv0jn6etha"
def _timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")
def _slugify_url(name):
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"\s+", "-", s)
    return s
def _construct_city_page_url(city_name):
    return f"https://housing.com/in/buy/real-estate-{_slugify_url(city_name)}"
def discover_cities(cities, output_dir="data", headless=True):
    results = []
    failed = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=headless,
            proxy={"server": PROXY_SERVER, "username": PROXY_USER, "password": PROXY_PASS},
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            viewport={"width": 414, "height": 896},
            user_agent="Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Mobile Safari/537.36",
            locale="en-IN",
        )
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
        """)
        page = context.new_page()
        for i, city_name in enumerate(cities):
            print(f"  [{i+1}/{len(cities)}] {city_name}: ", end="", flush=True)
            pt_url = None
            city_url = _construct_city_page_url(city_name)
            try:
                page.goto(city_url, wait_until="domcontentloaded", timeout=15000)
                page.wait_for_selector("section[data-q='researchAndInsights']", timeout=10000)
                card = page.locator("img[alt='Price Trends']").first
                if card.count() > 0:
                    card.click()
                    page.wait_for_load_state("load", timeout=10000)
                    card.click()
                    page.wait_for_load_state("load", timeout=10000)
                    # print current URL for debugging
                    print(f" [{page.url[:100]}]", end="", flush=True)
                    if "/price-trends/" in page.url:
                        pt_url = page.url
                    else:
                        for p in context.pages:
                            if "/price-trends/" in p.url:
                                pt_url = p.url
                                break
            except Exception:
                pass
            if pt_url:
                print("OK")
            else:
                print("FAILED")
                failed.append(city_name)
            results.append({"city_name": city_name, "city_page_url": city_url, "price_trend_url": pt_url or ""})
        context.close()
        browser.close()
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
        writer.writerows(results)
    print(f"\n  > {filepath} ({len(results)} cities)")
    return filepath
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--cities", default="data/cities.txt")
    parser.add_argument("--output", default="data")
    parser.add_argument("--visible", action="store_true")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    with open(args.cities) as f:
        lines = [line.strip() for line in f if line.strip()]
    if args.limit:
        lines = lines[:args.limit]
    results = discover_cities(lines, output_dir=args.output, headless=not args.visible)
    write_cities_csv(results, args.output)