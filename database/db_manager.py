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

        db_url = os.getenv("DB_URL", "")
        if db_url:
            try:
                self.conn = psycopg2.connect(db_url)
                self.conn.autocommit = True
                return True
            except Exception as e:
                print(f"  [DB] Connection with DB_URL failed: {e}")
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

    def insert_housing_price_trends(self, result):
        if not self.conn:
            return
        from datetime import datetime
        ts = datetime.now().strftime("%H_%M_%S_%d_%m__%y")
        product = result["product"]
        table_name = f"Housing_com_price_trends_{product}_{ts}"

        city_name = result["city_name"]
        summary = result["summary"]
        localities = result["localities"]

        with self.conn.cursor() as cur:
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id SERIAL PRIMARY KEY,
                    record_type TEXT,
                    city TEXT,
                    product TEXT,
                    locality_name TEXT,
                    property_type TEXT,
                    avg_price_per_sqft TEXT,
                    min_price TEXT,
                    max_price TEXT,
                    total_listings TEXT,
                    locality_url TEXT,
                    has_trend_data TEXT,
                    trend_raw JSONB,
                    scrape_timestamp TEXT
                );
            """)

            for pt_name, pt_data in summary.get("property_type_trends", {}).items():
                trend = pt_data.get("quarterly_trend", [])
                cur.execute(f"""
                    INSERT INTO {table_name}
                        (record_type, city, product, property_type,
                         avg_price_per_sqft, min_price, max_price, total_listings,
                         trend_raw, scrape_timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    "city_trend", city_name, product, pt_name,
                    summary.get("avg_price_per_sqft", ""),
                    summary.get("min_price", ""),
                    summary.get("max_price", ""),
                    summary.get("total_listings", ""),
                    json.dumps(trend) if trend else None,
                    ts,
                ))

            cur.execute(f"""
                INSERT INTO {table_name}
                    (record_type, city, product, property_type,
                     avg_price_per_sqft, min_price, max_price, total_listings,
                     trend_raw, scrape_timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                "city_summary", city_name, product,
                f"OVERALL avg={summary.get('avg_price_per_sqft', '')}",
                summary.get("avg_price_per_sqft", ""),
                summary.get("min_price", ""),
                summary.get("max_price", ""),
                summary.get("total_listings", ""),
                None, ts,
            ))

            for loc in localities:
                trend = loc.get("locality_trend", [])
                cur.execute(f"""
                    INSERT INTO {table_name}
                        (record_type, city, product, locality_name, property_type,
                         avg_price_per_sqft, min_price, max_price, total_listings,
                         locality_url, has_trend_data, trend_raw, scrape_timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    "locality", city_name, product, loc["locality_name"],
                    loc["property_type"],
                    loc.get("avg_price", ""),
                    loc.get("min_price", ""),
                    loc.get("max_price", ""),
                    loc.get("total_listings", ""),
                    loc.get("locality_url", ""),
                    "yes" if trend else "no",
                    json.dumps(trend) if trend else None,
                    ts,
                ))

            print(f"  > Created table: {table_name}")

    def close(self):
        if self.conn:
            self.conn.close()
