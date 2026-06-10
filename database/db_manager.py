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
            env_file = Path(__file__).parent.parent / ".env"
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
            cur.execute("""
                CREATE TABLE IF NOT EXISTS city_summary (
                    id SERIAL PRIMARY KEY,
                    city TEXT, product TEXT, avg_price_per_sqft TEXT,
                    min_price TEXT, max_price TEXT, total_listings TEXT,
                    scrape_date TIMESTAMP DEFAULT NOW(),
                    UNIQUE(city, product)
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS city_trends (
                    id SERIAL PRIMARY KEY,
                    city TEXT, product TEXT, property_type TEXT,
                    property_type_id INT, quarter TEXT, price NUMERIC,
                    scrape_date TIMESTAMP DEFAULT NOW(),
                    UNIQUE(city, product, property_type_id, quarter)
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS locality_data (
                    id SERIAL PRIMARY KEY,
                    city TEXT, product TEXT, locality_name TEXT,
                    property_type TEXT, property_type_id INT,
                    min_price TEXT, max_price TEXT, avg_price TEXT,
                    total_listings TEXT, locality_url TEXT,
                    scrape_date TIMESTAMP DEFAULT NOW()
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS locality_trends (
                    id SERIAL PRIMARY KEY,
                    locality_name TEXT, city TEXT, product TEXT,
                    property_type TEXT, property_type_id INT,
                    quarter TEXT, price NUMERIC,
                    scrape_date TIMESTAMP DEFAULT NOW(),
                    UNIQUE(locality_name, city, product, property_type_id, quarter)
                );
            """)

    def insert_city_summary(self, summary):
        if not self.conn:
            return
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO city_summary (city, product, avg_price_per_sqft, min_price, max_price, total_listings)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (city, product) DO UPDATE SET
                    avg_price_per_sqft=EXCLUDED.avg_price_per_sqft,
                    min_price=EXCLUDED.min_price,
                    max_price=EXCLUDED.max_price,
                    total_listings=EXCLUDED.total_listings,
                    scrape_date=NOW()
            """, (summary["city"], summary["product"], summary["avg_price_per_sqft"],
                  summary["min_price"], summary["max_price"], summary["total_listings"]))

    def insert_city_trends(self, city, product, trends_by_type):
        if not self.conn or not trends_by_type:
            return
        with self.conn.cursor() as cur:
            for type_name, trend_data in trends_by_type.items():
                for quarter, price in trend_data["quarterly_trend"]:
                    cur.execute("""
                        INSERT INTO city_trends (city, product, property_type, property_type_id, quarter, price)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (city, product, property_type_id, quarter) DO UPDATE SET
                            price=EXCLUDED.price, scrape_date=NOW()
                    """, (city, product, type_name, trend_data["property_type_id"], quarter, price))

    def insert_localities(self, city, product, localities):
        if not self.conn or not localities:
            return
        with self.conn.cursor() as cur:
            for loc in localities:
                cur.execute("""
                    INSERT INTO locality_data (city, product, locality_name, property_type,
                        property_type_id, min_price, max_price, avg_price, total_listings, locality_url)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (city, product, loc["locality_name"], loc["property_type"],
                      loc["property_type_id"], loc["min_price"], loc["max_price"],
                      loc["avg_price"], loc["total_listings"], loc.get("locality_url", "")))

    def insert_locality_trends(self, city, product, localities):
        if not self.conn or not localities:
            return
        with self.conn.cursor() as cur:
            for loc in localities:
                trend = loc.get("locality_trend")
                if not trend:
                    continue
                for quarter, price in trend:
                    cur.execute("""
                        INSERT INTO locality_trends (locality_name, city, product, property_type,
                            property_type_id, quarter, price)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (locality_name, city, product, property_type_id, quarter) DO UPDATE SET
                            price=EXCLUDED.price, scrape_date=NOW()
                    """, (loc["locality_name"], city, product, loc["property_type"],
                          loc["property_type_id"], quarter, price))

    def close(self):
        if self.conn:
            self.conn.close()
