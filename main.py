import sys
import time
from pathlib import Path

from scraper.fetcher import PageFetcher
from scraper.city_scraper import CityScraper
from scraper.output_writer import write_combined_csv
from scraper.city_list_scraper import scrape_city_list, write_cities_csv
from proxies.proxy_manager import ProxyManager


def scrape_url(url, fetcher, output_dir, no_csv=False):
    print(f"\n{'='*60}")
    print(f"Scraping: {url}")
    print(f"{'='*60}")

    city_scraper = CityScraper(fetcher, output_dir)
    results = city_scraper.scrape(url)

    csv_paths = []
    if not no_csv:
        for product, result in results.items():
            print(f"\n  --- {product.upper()} ---")
            csv_path = write_combined_csv(result, output_dir)
            csv_paths.append(csv_path)

    return results, csv_paths


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Housing.com Price Trends Scraper")
    parser.add_argument("urls", nargs="*", help="Price trend page URLs to scrape")
    parser.add_argument("--proxy-file", help="Proxy list file (one per line)")
    parser.add_argument("--output", default="data", help="Output directory for CSVs")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between requests (seconds)")
    parser.add_argument("--headless", action="store_true", default=True, help="Run in headless mode (always on)")
    parser.add_argument("--no-csv", action="store_true", help="Skip CSV output (DB only)")
    parser.add_argument("--db", action="store_true", help="Push to database")
    parser.add_argument("--db-url", help="PostgreSQL connection string (overrides env)")
    parser.add_argument("--discover", metavar="CITIES_TXT", nargs="?", const="data/cities.txt",
                        help="Discover price trend URLs from city landing pages")

    args = parser.parse_args()

    if args.discover:
        proxy_mgr = ProxyManager(args.proxy_file) if args.proxy_file else ProxyManager()
        print("Discovering price trend URLs from city landing pages...")
        results = scrape_city_list(
            cities_txt_path=args.discover,
            delay=max(args.delay, 3.0),
            output_dir=args.output,
            proxy_manager=proxy_mgr,
        )
        csv_path = write_cities_csv(results, args.output)
        print(f"\n  > Results written to {csv_path}")
        found = sum(1 for r in results if r.get("price_trend_url"))
        print(f"  > {found}/{len(results)} cities resolved")
        return

    urls = args.urls or [
        "https://housing.com/price-trends/property-rates-for-buy-in-new_delhi_india-P6xfqdsey6cc3d95h"
    ]

    proxy_mgr = ProxyManager(args.proxy_file) if args.proxy_file else ProxyManager()
    fetcher = PageFetcher(proxy_mgr, delay=args.delay)

    db_mgr = None
    if args.db:
        from database.db_manager import DatabaseManager
        db_mgr = DatabaseManager()
        if args.db_url:
            import os
            os.environ["DB_URL"] = args.db_url
        if db_mgr.connect():
            db_mgr.ensure_tables()
            print("  [DB] Connected and tables ready")
        else:
            db_mgr = None

    for url in urls:
        try:
            results, csv_paths = scrape_url(url, fetcher, args.output, args.no_csv)

            if db_mgr:
                for product, result in results.items():
                    print(f"  [DB] Inserting {product} data...")
                    db_mgr.insert_city_summary(result["summary"])
                    db_mgr.insert_city_trends(
                        result["city_name"],
                        result["product"],
                        result["summary"].get("property_type_trends", {}),
                    )
                    db_mgr.insert_localities(
                        result["city_name"], result["product"], result["localities"]
                    )
                    db_mgr.insert_locality_trends(
                        result["city_name"], result["product"], result["localities"]
                    )
                    db_mgr.insert_housing_price_trends(result)
                print("  [DB] Done")

        except Exception as e:
            print(f"\n  [ERROR] Failed to scrape {url}: {e}")
            import traceback
            traceback.print_exc()

    if db_mgr:
        db_mgr.close()

    print(f"\n{'='*60}")
    print(f"All done!")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
