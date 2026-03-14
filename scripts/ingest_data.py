"""
UK Climate Data Ingestion Script
=================================
Reads Met Office historic station data files from the data/ folder and
loads them into PostgreSQL.

Data source: Met Office Historic Station Data
URL: https://www.metoffice.gov.uk/pub/data/weather/uk/climate/stationdata/
Licence: Open Government Licence v3.0

Usage (from project root inside Docker):
    docker-compose exec api python scripts/ingest_data.py

Or directly:
    python scripts/ingest_data.py --data-dir data/

The script is idempotent — re-running it will skip rows that already exist.
"""

import argparse
import logging
import os
import re
import sys

import psycopg2
from psycopg2.extras import execute_values

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

DB_URL = os.getenv(
    "DATABASE_URL_SYNC",
    "postgresql://postgres:postgres@db:5432/uk_climate",
)

# Met Office file → station metadata
# Lat/Lon extracted from file headers; region added manually
STATION_META = {
    "armaghdata.txt": {
        "station_id": "ARMAGH",
        "name": "Armagh",
        "region": "Northern Ireland",
        "country": "UK",
        "latitude": 54.352,
        "longitude": -6.649,
        "elevation_m": 62,
        "opened_year": 1853,
        "closed_year": None,
    },
    "cambridgedata.txt": {
        "station_id": "CAMBRIDGE",
        "name": "Cambridge NIAB",
        "region": "East England",
        "country": "UK",
        "latitude": 52.245,
        "longitude": 0.103,
        "elevation_m": 26,
        "opened_year": 1959,
        "closed_year": None,
    },
    "cardiffdata.txt": {
        "station_id": "CARDIFF",
        "name": "Cardiff Bute Park",
        "region": "Wales",
        "country": "UK",
        "latitude": 51.486,
        "longitude": -3.176,
        "elevation_m": 11,
        "opened_year": 1942,
        "closed_year": None,
    },
    "durhamdata.txt": {
        "station_id": "DURHAM",
        "name": "Durham",
        "region": "North East England",
        "country": "UK",
        "latitude": 54.768,
        "longitude": -1.585,
        "elevation_m": 102,
        "opened_year": 1880,
        "closed_year": None,
    },
    "heathrowdata.txt": {
        "station_id": "HEATHROW",
        "name": "London Heathrow",
        "region": "London",
        "country": "UK",
        "latitude": 51.479,
        "longitude": -0.449,
        "elevation_m": 25,
        "opened_year": 1948,
        "closed_year": None,
    },
    "lerwickdata.txt": {
        "station_id": "LERWICK",
        "name": "Lerwick",
        "region": "Scotland",
        "country": "UK",
        "latitude": 60.139,
        "longitude": -1.183,
        "elevation_m": 82,
        "opened_year": 1931,
        "closed_year": None,
    },
    "oxforddata.txt": {
        "station_id": "OXFORD",
        "name": "Oxford",
        "region": "South East England",
        "country": "UK",
        "latitude": 51.761,
        "longitude": -1.262,
        "elevation_m": 63,
        "opened_year": 1853,
        "closed_year": None,
    },
    "sheffielddata.txt": {
        "station_id": "SHEFFIELD",
        "name": "Sheffield",
        "region": "Yorkshire",
        "country": "UK",
        "latitude": 53.381,
        "longitude": -1.490,
        "elevation_m": 131,
        "opened_year": 1883,
        "closed_year": None,
    },
}


def parse_val(s: str) -> float | None:
    """Parse a Met Office value; return None for missing/estimated markers."""
    s = s.strip().replace("*", "").replace("#", "")
    if s in ("---", "", "-", "NA"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_metoffice_file(filepath: str) -> list[dict]:
    """
    Parse a Met Office historic station data file.
    Columns: yyyy  mm  tmax  tmin  af  rain  sun
    Returns list of observation dicts using the 15th of each month as the date.
    """
    rows = []
    in_data = False

    with open(filepath, encoding="utf-8", errors="replace") as f:
        for line in f:
            line_stripped = line.strip()

            # Data starts after the header row containing "yyyy"
            if re.search(r"\byyyy\b", line_stripped, re.IGNORECASE):
                in_data = True
                continue

            if not in_data:
                continue

            # Skip unit row (degC, days, mm, hours) and blank/note lines
            if not line_stripped or line_stripped.startswith("Provisional"):
                continue
            if re.match(r"^\s*(degC|days|mm|hours)", line_stripped, re.IGNORECASE):
                continue

            # Strip estimated/auto markers and split
            clean = re.sub(r"[*#]", "", line_stripped)
            parts = clean.split()

            if len(parts) < 6:
                continue

            try:
                year = int(parts[0])
                month = int(parts[1])
            except ValueError:
                continue

            if year < 1800 or year > 2030 or month < 1 or month > 12:
                continue

            tmax = parse_val(parts[2]) if len(parts) > 2 else None
            tmin = parse_val(parts[3]) if len(parts) > 3 else None
            rain = parse_val(parts[5]) if len(parts) > 5 else None
            sun  = parse_val(parts[6]) if len(parts) > 6 else None

            mean = round((tmax + tmin) / 2, 2) if tmax is not None and tmin is not None else None

            rows.append({
                "date": f"{year:04d}-{month:02d}-15",
                "max_temp_c": tmax,
                "min_temp_c": tmin,
                "mean_temp_c": mean,
                "rainfall_mm": rain,
                "sunshine_hours": sun,
                "data_quality": 1,
            })

    return rows


def upsert_station(conn, meta: dict) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO stations
                (station_id, name, region, country, latitude, longitude, elevation_m, opened_year, closed_year)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (station_id) DO UPDATE SET
                name        = EXCLUDED.name,
                region      = EXCLUDED.region,
                latitude    = EXCLUDED.latitude,
                longitude   = EXCLUDED.longitude,
                elevation_m = EXCLUDED.elevation_m
            RETURNING id
            """,
            (
                meta["station_id"], meta["name"], meta["region"], meta["country"],
                meta["latitude"], meta["longitude"], meta["elevation_m"],
                meta["opened_year"], meta["closed_year"],
            ),
        )
        row = cur.fetchone()
        conn.commit()
        return row[0]


def ingest_observations(conn, internal_id: int, rows: list[dict]) -> int:
    if not rows:
        return 0

    batch_size = 1000
    total = 0

    with conn.cursor() as cur:
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            execute_values(
                cur,
                """
                INSERT INTO observations
                    (station_id, date, max_temp_c, min_temp_c, mean_temp_c,
                     rainfall_mm, sunshine_hours, data_quality)
                VALUES %s
                ON CONFLICT (station_id, date) DO NOTHING
                """,
                [
                    (
                        internal_id, r["date"], r["max_temp_c"], r["min_temp_c"],
                        r["mean_temp_c"], r["rainfall_mm"], r["sunshine_hours"],
                        r["data_quality"],
                    )
                    for r in batch
                ],
            )
            conn.commit()
            total += len(batch)

    return total


def main():
    parser = argparse.ArgumentParser(description="Ingest Met Office station data into PostgreSQL")
    parser.add_argument(
        "--data-dir",
        default="data",
        help="Directory containing Met Office .txt files (default: data/)",
    )
    args = parser.parse_args()

    if not os.path.isdir(args.data_dir):
        log.error(f"Data directory not found: {args.data_dir}")
        sys.exit(1)

    conn = psycopg2.connect(DB_URL)
    try:
        for filename, meta in STATION_META.items():
            filepath = os.path.join(args.data_dir, filename)
            if not os.path.exists(filepath):
                log.warning(f"File not found, skipping: {filepath}")
                continue

            log.info(f"Processing {filename} → {meta['station_id']}")
            rows = parse_metoffice_file(filepath)
            log.info(f"  Parsed {len(rows)} monthly records")

            internal_id = upsert_station(conn, meta)
            n = ingest_observations(conn, internal_id, rows)
            log.info(f"  Loaded {n} observations (station db id={internal_id})")

        log.info("Ingestion complete.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
