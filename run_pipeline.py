import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from database.db_manager import DatabaseManager
from proxies.proxy_manager import ProxyManager
from scraper.fetcher import PageFetcher
from scraper.city_scraper import CityScraper
from scraper.output_writer import write_csv_all

from scripts.extract_all_city_urls import fetch_city_urls, _slugify, BASE_URL


def stage0_fetch_urls(db):
    print(f"\n{'=' * 60}")
    print(f"Stage 0: Fetching city URLs from GraphQL...")
    print(f"{'=' * 60}")
    city_list = fetch_city_urls("buy")
    count = 0
    for city_name, info in city_list.items():
        price_trend_url = BASE_URL + info["priceTrendUrl"]
        city_page_url = f"https://housing.com/in/buy/real-estate-{_slugify(city_name)}"
        if db.insert_city_url(city_name, price_trend_url, city_page_url):
            count += 1
    print(f"  > Inserted {count} new URLs (skipped existing)")
    return count


def stage2_scrape_data(db, delay=1.0, proxy_file=None, output_csv=False, limit=0, _result=None):
    """Stage 2: scrape all cities. `_result` is an optional dict to receive partial counts on interrupt."""
    print(f"\n{'=' * 60}")
    print(f"Stage 2: Scraping cities without cached data...")
    print(f"{'=' * 60}")

    proxy_mgr = ProxyManager(proxy_file) if proxy_file else ProxyManager()
    fetcher = PageFetcher(proxy_mgr, delay=delay)

    rows = db.get_all_city_urls()
    all_urls = {city: url for city, url, _ in rows}

    if not all_urls:
        print("  > No URLs found in DB. Run stage 0 first.")
        return 0, 0

    total = len(all_urls)
    scraped = 0
    skipped = 0
    all_csv_results = []
    try:
        for idx, (city_name, url) in enumerate(sorted(all_urls.items()), 1):
            if limit > 0 and scraped >= limit:
                break
            if db.has_city_data(city_name):
                skipped += 1
                if output_csv:
                    print(f"  [{idx}/{total}] {city_name} - skipped (cached)")
                continue

            print(f"\n  [{idx}/{total}] Scraping: {city_name}")
            try:
                scraper = CityScraper(fetcher, output_dir="data")
                results = scraper.scrape(url)

                page_name = next(iter(results.values()))["city_name"]
                use_name = page_name if page_name != city_name else city_name
                if page_name != city_name:
                    print(f"  [INFO] City name mismatch: URL table says '{city_name}', page says '{page_name}' — renaming URL entry to '{page_name}'")
                    db.rename_city_url(city_name, page_name)

                ts = datetime.now().strftime("%H_%M_%S_%d_%m__%y")
                inserted_any = False
                for product, result in results.items():
                    result["city_name"] = use_name
                    for loc in result["localities"]:
                        loc["city"] = use_name
                    result["scrape_timestamp"] = ts
                    if db.insert_scrape_result(result):
                        inserted_any = True
                    else:
                        skipped += 1

                if output_csv:
                    all_csv_results.append(results)

                if inserted_any:
                    scraped += 1
            except Exception as e:
                print(f"  [ERROR] {city_name}: {e}")
                db.insert_failed(city_name, url, e)
    except KeyboardInterrupt:
        print(f"\n\n  [!] Interrupted by user")
        if _result is not None:
            _result["scraped"] = scraped
            _result["skipped"] = skipped
            _result["interrupted"] = True
        raise

    if output_csv and all_csv_results:
        write_csv_all(all_csv_results, "data")

    return scraped, skipped


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Pipeline: Stage 0 (fetch URLs) + Stage 2 (scrape data) -> DB only"
    )
    parser.add_argument("--proxy-file", help="Proxy list file (one per line)")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between requests (seconds)")
    parser.add_argument("--db-url", help="PostgreSQL connection string (overrides .env)")
    parser.add_argument("--csv", action="store_true", help="Also write CSV output")
    parser.add_argument("--limit", type=int, default=0, help="Max cities to scrape (0 = unlimited)")
    args = parser.parse_args()

    db = DatabaseManager()
    if args.db_url:
        import os
        os.environ["DATABASE_URL"] = args.db_url

    if not db.connect():
        print("[ERROR] Could not connect to database")
        sys.exit(1)
    db.ensure_tables()

    stage0_fetch_urls(db)

    result = {"scraped": 0, "skipped": 0, "interrupted": False}
    try:
        scraped, skipped = stage2_scrape_data(db, delay=args.delay, proxy_file=args.proxy_file, output_csv=args.csv, limit=args.limit, _result=result)
    except KeyboardInterrupt:
        pass  # partial counts already in result

    db.close()

    print(f"\n{'=' * 60}")
    status = "Interrupted" if result["interrupted"] else "Complete"
    print(f"Pipeline {status}! Scraped: {result['scraped']}, Skipped (cached): {result['skipped']}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
