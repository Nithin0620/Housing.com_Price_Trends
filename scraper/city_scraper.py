from pathlib import Path
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

from scraper.property_types import get_property_name


class CityScraper:
    def __init__(self, fetcher, output_dir="data"):
        self.fetcher = fetcher
        self.output_dir = Path(output_dir)

    def scrape(self, url):
        html = self.fetcher.fetch_html(url)
        if not html:
            raise RuntimeError(f"Failed to fetch {url}")

        from scraper.parser import extract_initial_state
        data = extract_initial_state(html)
        pt = data.get("priceTrends", {})

        selected_city = data.get("filters", {}).get("selectedCity", {})
        city_name = selected_city.get("name", "unknown")
        city_id = selected_city.get("id", "")

        results = {}
        for product in ["buy", "rent"]:
            city_data = pt.get(product, {})
            all_trends = pt.get("trendData", {}).get(product, {})
            summary = self._build_summary(city_data, all_trends, product, city_name)
            localities = self._scrape_all_pages(url, product, pt, city_name)
            self.fetch_locality_trends(localities)

            results[product] = {
                "city_name": city_name,
                "city_id": city_id,
                "product": product,
                "url": url,
                "summary": summary,
                "localities": localities,
            }

        return results

    def _build_summary(self, city_data, all_trends, product, city_name):
        trends_by_type = {}
        for city_id, trends_list in all_trends.items():
            for t in trends_list:
                type_id = int(t["id"])
                type_name = get_property_name(product, type_id)
                if not type_name:
                    continue
                trends_by_type[type_name] = {
                    "property_type_id": type_id,
                    "quarterly_trend": t["trend"],
                }

        return {
            "city": city_name,
            "product": product,
            "avg_price_per_sqft": city_data.get("averagePrice", ""),
            "min_price": city_data.get("minPrice", ""),
            "max_price": city_data.get("maxPrice", ""),
            "total_listings": city_data.get("flatCount", ""),
            "url": city_data.get("url", ""),
            "property_type_trends": trends_by_type,
        }

    def _scrape_all_pages(self, base_url, product, pt, city_name):
        city_data = pt.get(product, {})
        page_info = city_data.get("pageInfo", {})
        num_pages = page_info.get("numPages", 1)

        all_items_grouped = []
        page1_data = city_data.get("tableData", {}).get("1", [])
        all_items_grouped.extend(page1_data)

        for page_num in range(2, num_pages + 1):
            page_url = f"{base_url}?page={page_num}"
            try:
                html = self.fetcher.fetch_html(page_url)
                if not html:
                    continue
                from scraper.parser import extract_initial_state
                data = extract_initial_state(html)
                page_items = (
                    data.get("priceTrends", {})
                    .get(product, {})
                    .get("tableData", {})
                    .get(str(page_num), [])
                )
                all_items_grouped.extend(page_items)
                print(f"  [{product.upper()}] PAGE {page_num}/{num_pages}")
            except Exception as e:
                print(f"  [WARN] {product} page {page_num}: {e}")

        return self._flatten_table_data(all_items_grouped, product, city_name, base_url)

    def _flatten_table_data(self, grouped_items, product, city_name, base_url):
        seen = {}

        for group in grouped_items:
            prop_type_id = group.get("id")
            prop_type_name = group.get("key")
            if not prop_type_id or not prop_type_name:
                continue
            prop_type_id = int(prop_type_id)

            for lt in group.get("localityTrends", []):
                locality_name = lt.get("name", "")
                if not locality_name:
                    continue

                key = (locality_name, prop_type_id)
                if key not in seen:
                    seen[key] = {
                        "city": city_name,
                        "product": product,
                        "locality_name": locality_name,
                        "locality_id": lt.get("id", ""),
                        "locality_url": lt.get("url", ""),
                        "price_trend_url": lt.get("priceTrendUrl", ""),
                        "property_type_id": prop_type_id,
                        "property_type": prop_type_name,
                        "avg_price": lt.get("averagePrice", ""),
                        "min_price": lt.get("minPrice", ""),
                        "max_price": lt.get("maxPrice", ""),
                        "total_listings": lt.get("flatCount", ""),
                        "locality_trend": None,
                    }

        return list(seen.values())

    def fetch_locality_trends(self, localities):
        unique_urls = {}
        for i, loc in enumerate(localities):
            url = loc.get("price_trend_url", "")
            if url:
                unique_urls.setdefault(url, []).append(i)

        if not unique_urls:
            return localities

        print(f"  [TRENDS] Fetching {len(unique_urls)} unique locality pages...")

        fetched = {}

        def fetch_one(url):
            from urllib.parse import urljoin
            from scraper.parser import extract_initial_state

            full_url = url if url.startswith("http") else urljoin("https://housing.com", url)
            html = self.fetcher.fetch_html(full_url)
            if not html:
                return url, None
            try:
                data = extract_initial_state(html)
                return url, data
            except Exception:
                return url, None

        with ThreadPoolExecutor(max_workers=5) as pool:
            fut_map = {pool.submit(fetch_one, url): url for url in unique_urls}
            done_count = 0
            for fut in as_completed(fut_map):
                done_count += 1
                url, page_data = fut.result()
                if page_data:
                    fetched[url] = page_data
                pct = int(done_count / len(unique_urls) * 100)
                print(f"    [{done_count}/{len(unique_urls)}] {pct}%", end="\r")

        print()

        for url, page_data in fetched.items():
            indices = unique_urls[url]
            product = localities[indices[0]]["product"]
            trend_data = page_data.get("priceTrends", {}).get("trendData", {}).get(product, {})

            trends_by_type = {}
            for city_id, trends_list in trend_data.items():
                for t in trends_list:
                    trends_by_type[int(t["id"])] = t["trend"]

            for idx in indices:
                ptype_id = localities[idx]["property_type_id"]
                if ptype_id in trends_by_type:
                    localities[idx]["locality_trend"] = trends_by_type[ptype_id]

        found = sum(1 for loc in localities if loc.get("locality_trend"))
        print(f"  [TRENDS] Found for {found}/{len(localities)} entries")
        return localities
