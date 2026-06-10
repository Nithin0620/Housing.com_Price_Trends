# Housing.com Price Trends Scraper

Scrapes housing price trends from Housing.com for multiple cities.

## Output

Generates `Housing.com_price_trends_{buy|rent}_HH_MM_SS_DD_MM__YY.csv` with:

- **City-level trends**: Avg Price/Sqft for the city per property type
- **Locality data**: Per locality, per property type — avg price, min, max, listings
- **Locality trends**: Quarterly price trend data (wide format columns)
- **record_type**: `city_summary` | `city_trend` | `locality`

## Usage

```bash
# Default: scrape New Delhi buy page
python3 main.py

# One or more URLs
python3 main.py https://housing.com/price-trends/property-rates-for-buy-in-new_delhi_india-P6xfqdsey6cc3d95h

# With custom delay
python3 main.py --delay 0.5

# With proxy file
python3 main.py --proxy-file proxies/proxies.txt

# Push to PostgreSQL
python3 main.py --db
```

## Project Structure

```
├── main.py              # Entry point
├── scraper/             # Scraper logic (split by concern)
│   ├── fetcher.py       # HTTP client (curl_cffi for Akamai bypass)
│   ├── parser.py        # __INITIAL_STATE__ JSON extraction
│   ├── city_scraper.py  # City page + pagination + trends
│   ├── property_types.py# Property type ID mapping
│   └── output_writer.py # CSV generation
├── proxies/
│   ├── proxy_manager.py # Proxy rotation
│   └── proxies.txt      # One proxy per line (optional)
├── database/
│   └── db_manager.py    # PostgreSQL integration
├── data/                # CSV output directory
└── requirements.txt
```

## DB Setup

Create `.env` file:
```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=housing_trends
DB_USER=postgres
DB_PASSWORD=yourpass
```
