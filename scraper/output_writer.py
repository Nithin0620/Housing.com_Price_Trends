import json
import csv
import os
from datetime import datetime
from pathlib import Path


def _timestamp():
    now = datetime.now()
    return now.strftime("%H_%M_%S_%d_%m__%y")


def _sorted_quarters(localities):
    qs = set()
    for loc in localities:
        trend = loc.get("locality_trend")
        if trend:
            for q, _ in trend:
                qs.add(q)
    return sorted(qs)


def _write_result(writer, result):
    city_name = result["city_name"]
    product = result["product"]
    summary = result["summary"]
    localities = result["localities"]

    city_row = {
        "record_type": "city_summary",
        "city": city_name,
        "product": product,
        "locality_name": "ALL",
        "property_type": "ALL",
        "avg_price_per_sqft": summary.get("avg_price_per_sqft", ""),
        "min_price": summary.get("min_price", ""),
        "max_price": summary.get("max_price", ""),
        "total_listings": summary.get("total_listings", ""),
        "has_trend_data": "",
    }

    for pt_name, pt_data in summary.get("property_type_trends", {}).items():
        pt_row = dict(city_row)
        pt_row["property_type"] = pt_name
        pt_row["record_type"] = "city_trend"
        trend = pt_data.get("quarterly_trend", [])
        if trend:
            pt_row["trend_raw"] = json.dumps(trend)
            for q, p in trend:
                pt_row[f"trend_{q}"] = str(p)
        writer.writerow(pt_row)

    city_row["record_type"] = "city_summary"
    city_row["property_type"] = f"OVERALL avg={summary.get('avg_price_per_sqft', '')}"
    writer.writerow(city_row)

    for loc in localities:
        row = {
            "record_type": "locality",
            "city": loc["city"],
            "product": loc["product"],
            "locality_name": loc["locality_name"],
            "property_type": loc["property_type"],
            "avg_price_per_sqft": loc.get("avg_price", ""),
            "min_price": loc.get("min_price", ""),
            "max_price": loc.get("max_price", ""),
            "total_listings": loc.get("total_listings", ""),
            "locality_url": loc.get("locality_url", ""),
            "has_trend_data": "yes" if loc.get("locality_trend") else "no",
            "trend_raw": json.dumps(loc.get("locality_trend", [])),
        }

        trend = loc.get("locality_trend")
        if trend:
            for q, p in trend:
                row[f"trend_{q}"] = str(p)

        writer.writerow(row)


def write_combined_csv(result, output_dir):
    city_name = result["city_name"]
    product = result["product"]
    ts = _timestamp()
    filename = f"Housing.com_price_trends_{product}_{ts}.csv"

    os.makedirs(output_dir, exist_ok=True)
    filepath = Path(output_dir) / filename

    localities = result["localities"]
    summary = result["summary"]
    sq = _sorted_quarters(localities)

    fieldnames = [
        "record_type", "city", "product",
        "locality_name", "property_type", "avg_price_per_sqft",
        "min_price", "max_price", "total_listings",
        "locality_url", "has_trend_data",
    ] + [f"trend_{q}" for q in sq] + ["trend_raw"]

    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        _write_result(writer, result)

    print(f"  > {filepath} ({len(localities)} locality rows)")
    return filepath


def write_csv_all(city_results, output_dir):
    ts = _timestamp()
    filename = f"Housing.com_price_trends_{ts}.csv"

    os.makedirs(output_dir, exist_ok=True)
    filepath = Path(output_dir) / filename

    all_qs = set()
    for results in city_results:
        for product, result in results.items():
            for pt_name, pt_data in result["summary"].get("property_type_trends", {}).items():
                for q, _ in pt_data.get("quarterly_trend", []):
                    all_qs.add(q)
            for loc in result["localities"]:
                trend = loc.get("locality_trend")
                if trend:
                    for q, _ in trend:
                        all_qs.add(q)
    sq = sorted(all_qs)

    fieldnames = [
        "record_type", "city", "product",
        "locality_name", "property_type", "avg_price_per_sqft",
        "min_price", "max_price", "total_listings",
        "locality_url", "has_trend_data",
    ] + [f"trend_{q}" for q in sq] + ["trend_raw"]

    total_loc = 0
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for results in city_results:
            for product, result in results.items():
                _write_result(writer, result)
                total_loc += len(result["localities"])

    print(f"  > {filepath} ({len(city_results)} cities, {total_loc} locality rows)")
    return filepath
