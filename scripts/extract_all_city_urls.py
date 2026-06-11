import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from curl_cffi import requests

GRAPHQL_ENDPOINT = "https://mightyzeus-mum.housing.com/api/gql"

QUERY = """
query($service: String) {
  cityUrlsListing(service: $service) {
    list
  }
}
"""

HEADERS = {
    "content-type": "application/json",
    "user-agent": "Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Mobile Safari/537.36",
    "origin": "https://housing.com",
    "referer": "https://housing.com/",
}

BASE_URL = "https://housing.com"


def _slugify(name):
    s = name.strip().lower()
    s = s.replace(",", "").replace(" ", "_")
    s = s.replace("-", "_")
    return s


def _timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def fetch_city_urls(service="buy"):
    payload = {"query": QUERY, "variables": {"service": service}}
    r = requests.post(
        GRAPHQL_ENDPOINT,
        impersonate="chrome124",
        headers=HEADERS,
        data=json.dumps(payload),
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    city_list = data.get("data", {}).get("cityUrlsListing", {}).get("list", {})
    return city_list


def scrape_city_list(service="buy", output_dir="data"):
    city_list = fetch_city_urls(service)
    results = []
    for city_name, info in city_list.items():
        results.append({
            "city_name": city_name,
            "city_page_url": f"https://housing.com/in/buy/real-estate-{_slugify(city_name)}",
            "price_trend_url": BASE_URL + info["priceTrendUrl"],
        })
    return results


def write_csv(results, output_dir="data"):
    ts = _timestamp()
    filename = f"Housing.com_all_city_urls_{ts}.csv"
    os.makedirs(output_dir, exist_ok=True)
    filepath = Path(output_dir) / filename
    fieldnames = ["city_name", "city_page_url", "price_trend_url"]
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    print(f"\n  > {filepath} ({len(results)} cities)")
    return filepath


def print_pretty(results):
    if not results:
        return
    name_w = max(len(r["city_name"]) for r in results) + 2
    print(f"\n  {'City':<{name_w}} {'Price Trend URL'}")
    print(f"  {'-' * name_w} {'-' * 60}")
    for r in results:
        print(f"  {r['city_name']:<{name_w}} {r['price_trend_url']}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Extract all city URLs from Housing.com GraphQL API")
    parser.add_argument("--output", default="data", help="Output directory for CSV")
    parser.add_argument("--service", default="buy", choices=["buy", "rent"], help="Service type")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print city list in console")
    args = parser.parse_args()

    print(f"Fetching all city URLs (service={args.service})...")
    results = scrape_city_list(service=args.service, output_dir=args.output)
    csv_path = write_csv(results, args.output)
    print(f"  > {len(results)} cities exported")

    if args.pretty:
        print_pretty(results)


if __name__ == "__main__":
    main()
