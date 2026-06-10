from urllib.parse import urljoin

from scraper.parser import extract_initial_state
from scraper.property_types import get_property_name


class LocalityScraper:
    def __init__(self, fetcher):
        self.fetcher = fetcher
        self._cache = {}

    def scrape_trend(self, trend_path, property_type_id, product):
        if not trend_path:
            return None

        url = trend_path if trend_path.startswith("http") else urljoin("https://housing.com", trend_path)

        cache_key = (url, product)
        if cache_key in self._cache:
            return self._cache[cache_key].get(property_type_id)

        html = self.fetcher.fetch_html(url)
        if not html:
            return None

        try:
            data = extract_initial_state(html)
        except Exception as e:
            print(f"  [WARN] Parse failed for {url}: {e}")
            return None

        pt = data.get("priceTrends", {})
        trend_data = pt.get("trendData", {}).get(product, {})

        for city_id, trends_list in trend_data.items():
            for t in trends_list:
                if int(t["id"]) == property_type_id:
                    if cache_key not in self._cache:
                        self._cache[cache_key] = {}
                    self._cache[cache_key][property_type_id] = t["trend"]
                    return t["trend"]

        return None
