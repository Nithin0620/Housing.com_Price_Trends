# Housing.com Price Trends Scraper

Scrapes housing price trends from Housing.com for any city.

Works by parsing the `__INITIAL_STATE__` JSON embedded in server-rendered pages. Uses `curl_cffi` to bypass Akamai CDN protection.

## Output

Generates timestamped CSV files: `Housing.com_price_trends_{buy|rent}_HH_MM_SS_DD_MM__YY.csv`

### What's scraped (per city URL):

| Data | Description |
|------|-------------|
| **City summary** | Avg Price/Sqft, min/max, total listings (both Buy & Rent) |
| **City trends** | Quarterly price trend for each property type |
| **Locality table** | Per locality x property type: avg price, min, max, listings |
| **Locality trends** | Quarterly price trend per locality per property type |

### Property types:

| Product | Types |
|---------|-------|
| Buy | Apartment, Independent House, Villa |
| Rent | 1 BHK, 2 BHK, 3 BHK |

## Usage

```bash
#Stage 1 
python scripts/extract_all_city_urls.py --pretty

# Scrape default (New Delhi buy), save CSV
python main.py

# Scrape specific URLs
python main.py https://housing.com/.../property-rates-for-buy-in-mumbai-XXX

# Multiple URLs (works when 50-100 pages exist)
python main.py url1 url2 url3

# DB only (no CSV)
python main.py --db --no-csv

# DB + CSV
python main.py --db

# Custom delay between requests
python main.py --delay 1.0
```

## Project Structure

```
├── main.py                   # Entry point
├── scraper/
│   ├── fetcher.py            # curl_cffi HTTP client (Akamai bypass)
│   ├── parser.py             # __INITIAL_STATE__ extraction
│   ├── city_scraper.py       # City page + pagination + locality trends
│   ├── property_types.py     # Property type ID -> name mapping
│   └── output_writer.py      # CSV generation
├── proxies/
│   ├── proxy_manager.py      # Proxy rotation
│   └── proxies.txt           # One proxy per line
├── database/
│   └── db_manager.py         # PostgreSQL integration
├── data/                     # CSV output directory
├── .github/workflows/
│   └── scrape.yml            # GitHub Actions cron job
└── requirements.txt
```

## Database

Tables are auto-created on first run. Connection via env vars:

```bash
# Single connection string (recommended for CI)
export DB_URL="postgresql://user:pass@host:5432/housing_trends"

# Or individual vars
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=housing_trends
export DB_USER=postgres
export DB_PASSWORD=yourpass
```

Or create a `.env` file:
```
DB_URL=postgresql://user:pass@host:5432/housing_trends
```

### Tables

| Table | Description |
|-------|-------------|
| `city_summary` | City-level avg price/min/max per product |
| `city_trends` | City-level quarterly price trends per property type |
| `locality_data` | Per locality property type stats |
| `locality_trends` | Locality-level quarterly price trends |

## GitHub Actions (Cron)

The workflow runs on the 1st of every month at 6:00 AM IST.

**Secrets required:**
- `DB_URL` — PostgreSQL connection string

To run manually: go to Actions → "Scrape Housing.com Price Trends" → Run workflow.
