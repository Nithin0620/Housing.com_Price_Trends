import os
import json
from pathlib import Path

try:
    import psycopg2
    import psycopg2.extras
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False


class DatabaseManager:
    def __init__(self, env_file=None):
        self.conn = None
        if env_file is None:
            env_file = Path(__file__).resolve().parent.parent / ".env"
        self.env_file = Path(env_file)
        self._load_env()

    def _load_env(self):
        if self.env_file.exists():
            with open(self.env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, val = line.split("=", 1)
                        os.environ.setdefault(key.strip(), val.strip())

    def connect(self):
        if not HAS_PSYCOPG2:
            print("  [DB] psycopg2 not installed. Skipping DB.")
            return False

        db_url = os.getenv("DATABASE_URL") or os.getenv("DB_URL") or ""
        if db_url:
            try:
                self.conn = psycopg2.connect(db_url)
                self.conn.autocommit = True
                return True
            except Exception as e:
                print(f"  [DB] Connection failed: {e}")
                return False

        try:
            self.conn = psycopg2.connect(
                host=os.getenv("DB_HOST", "localhost"),
                port=os.getenv("DB_PORT", "5432"),
                dbname=os.getenv("DB_NAME", "housing_trends"),
                user=os.getenv("DB_USER", "postgres"),
                password=os.getenv("DB_PASSWORD", ""),
            )
            self.conn.autocommit = True
            return True
        except Exception as e:
            print(f"  [DB] Connection failed: {e}")
            return False

    def ensure_tables(self):
        if not self.conn:
            return
        with self.conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.housingcom_pricetrend_url')")
            exists = cur.fetchone()[0] is not None
            if exists:
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.columns
                        WHERE table_name='housingcom_pricetrend_url' AND column_name='service'
                    )
                """)
                if cur.fetchone()[0]:
                    print("  [DB] Migrating housingcom_pricetrend_url (old schema -> new)")
                    cur.execute("DROP TABLE housingcom_pricetrend_url CASCADE")
                    cur.execute("""
                        CREATE TABLE housingcom_pricetrend_url (
                            id SERIAL PRIMARY KEY,
                            city_name TEXT NOT NULL UNIQUE,
                            price_trend_url TEXT NOT NULL,
                            city_page_url TEXT,
                            scrape_timestamp TEXT DEFAULT '',
                            scraped_at TIMESTAMP DEFAULT NOW()
                        )
                    """)
            else:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS housingcom_pricetrend_url (
                        id SERIAL PRIMARY KEY,
                        city_name TEXT NOT NULL UNIQUE,
                        price_trend_url TEXT NOT NULL,
                        city_page_url TEXT,
                        scrape_timestamp TEXT DEFAULT '',
                        scraped_at TIMESTAMP DEFAULT NOW()
                    )
                """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS housingcom_pricetrend_data (
                    id SERIAL PRIMARY KEY,
                    city TEXT NOT NULL,
                    product TEXT NOT NULL,
                    record_type TEXT,
                    locality_name TEXT DEFAULT '',
                    property_type TEXT DEFAULT '',
                    avg_price_per_sqft TEXT DEFAULT '',
                    min_price TEXT DEFAULT '',
                    max_price TEXT DEFAULT '',
                    total_listings TEXT DEFAULT '',
                    locality_url TEXT DEFAULT '',
                    has_trend_data TEXT DEFAULT '',
                    trend_raw JSONB,
                    scrape_timestamp TEXT DEFAULT '',
                    scraped_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(city, product, record_type, locality_name, property_type)
                );
            """)
            print("  [DB] Tables ensured")

    def insert_city_url(self, city_name, price_trend_url, city_page_url):
        if not self.conn:
            return False
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO housingcom_pricetrend_url (city_name, price_trend_url, city_page_url)
                VALUES (%s, %s, %s)
                ON CONFLICT (city_name) DO NOTHING
            """, (city_name, price_trend_url, city_page_url))
            return cur.rowcount > 0

    def get_all_city_urls(self):
        if not self.conn:
            return []
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT city_name, price_trend_url, city_page_url
                FROM housingcom_pricetrend_url
                ORDER BY city_name
            """)
            return cur.fetchall()

    def has_city_data(self, city, product):
        if not self.conn:
            return False
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT 1 FROM housingcom_pricetrend_data
                WHERE city = %s AND product = %s
                LIMIT 1
            """, (city, product))
            return cur.fetchone() is not None

    def _insert_price_trend_row(self, data):
        if not self.conn:
            return
        with self.conn.cursor() as cur:
            trend_raw = json.dumps(data["trend_raw"]) if data.get("trend_raw") else None
            cur.execute("""
                INSERT INTO housingcom_pricetrend_data
                    (city, product, record_type, locality_name, property_type,
                     avg_price_per_sqft, min_price, max_price, total_listings,
                     locality_url, has_trend_data, trend_raw, scrape_timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (city, product, record_type, locality_name, property_type)
                DO NOTHING
            """, (
                data.get("city", ""),
                data.get("product", ""),
                data.get("record_type", ""),
                data.get("locality_name", ""),
                data.get("property_type", ""),
                data.get("avg_price_per_sqft", ""),
                data.get("min_price", ""),
                data.get("max_price", ""),
                data.get("total_listings", ""),
                data.get("locality_url", ""),
                data.get("has_trend_data", ""),
                trend_raw,
                data.get("scrape_timestamp", ""),
            ))

    def insert_scrape_result(self, result):
        if not self.conn:
            return
        city = result["city_name"]
        product = result["product"]

        if self.has_city_data(city, product):
            print(f"  [DB] Data already exists for {city} ({product}), skipping")
            return

        summary = result["summary"]
        localities = result["localities"]
        ts = result.get("scrape_timestamp", "")

        for pt_name, pt_data in summary.get("property_type_trends", {}).items():
            trend = pt_data.get("quarterly_trend", [])
            self._insert_price_trend_row({
                "city": city,
                "product": product,
                "record_type": "city_trend",
                "locality_name": "",
                "property_type": pt_name,
                "avg_price_per_sqft": summary.get("avg_price_per_sqft", ""),
                "min_price": summary.get("min_price", ""),
                "max_price": summary.get("max_price", ""),
                "total_listings": summary.get("total_listings", ""),
                "locality_url": "",
                "has_trend_data": "yes" if trend else "no",
                "trend_raw": trend,
                "scrape_timestamp": ts,
            })

        self._insert_price_trend_row({
            "city": city,
            "product": product,
            "record_type": "city_summary",
            "locality_name": "",
            "property_type": f"OVERALL avg={summary.get('avg_price_per_sqft', '')}",
            "avg_price_per_sqft": summary.get("avg_price_per_sqft", ""),
            "min_price": summary.get("min_price", ""),
            "max_price": summary.get("max_price", ""),
            "total_listings": summary.get("total_listings", ""),
            "locality_url": "",
            "has_trend_data": "",
            "trend_raw": None,
            "scrape_timestamp": ts,
        })

        for loc in localities:
            trend = loc.get("locality_trend", [])
            self._insert_price_trend_row({
                "city": city,
                "product": product,
                "record_type": "locality",
                "locality_name": loc["locality_name"],
                "property_type": loc["property_type"],
                "avg_price_per_sqft": loc.get("avg_price", ""),
                "min_price": loc.get("min_price", ""),
                "max_price": loc.get("max_price", ""),
                "total_listings": loc.get("total_listings", ""),
                "locality_url": loc.get("locality_url", ""),
                "has_trend_data": "yes" if trend else "no",
                "trend_raw": trend,
                "scrape_timestamp": ts,
            })

        print(f"  [DB] Inserted data for {city} ({product})")

    def close(self):
        if self.conn:
            self.conn.close()
