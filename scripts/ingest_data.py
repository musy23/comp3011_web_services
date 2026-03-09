"""
UK Climate Data Ingestion Script
=================================
Imports weather station metadata and historical observations into PostgreSQL.

Data sources:
- Station metadata: Met Office / data.gov.uk (Open Government Licence v3.0)
- Observations: Kaggle 'uk-daily-weather-observations' dataset (CC0)

Usage:
    python scripts/ingest_data.py --stations data/stations.csv --observations data/observations.csv

The script is idempotent — re-running it will skip rows that already exist.
"""

import argparse
import csv
import logging
import os
import sys
from datetime import date, datetime

import psycopg2
from psycopg2.extras import execute_values

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

DB_URL = os.getenv(
    "DATABASE_URL_SYNC",
    "postgresql://postgres:postgres@localhost:5432/uk_climate",
)


def get_connection():
    return psycopg2.connect(DB_URL)


def parse_float(value: str) -> float | None:
    try:
        return float(value.strip()) if value and value.strip() not in ("", "NA", "N/A", "-") else None
    except ValueError:
        return None


def parse_int(value: str) -> int | None:
    try:
        return int(value.strip()) if value and value.strip() not in ("", "NA", "N/A", "-") else None
    except ValueError:
        return None


def ingest_stations(conn, filepath: str) -> dict[str, int]:
    """
    Load station metadata from CSV.
    Expected columns: station_id, name, region, country, latitude, longitude, elevation_m, opened_year, closed_year
    Returns mapping of station_id -> internal PK.
    """
    log.info(f"Loading stations from {filepath}")
    inserted = 0
    skipped = 0
    station_map: dict[str, int] = {}

    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        with conn.cursor() as cur:
            for row in reader:
                cur.execute(
                    """
                    INSERT INTO stations (station_id, name, region, country, latitude, longitude,
                                         elevation_m, opened_year, closed_year)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (station_id) DO NOTHING
                    RETURNING id, station_id
                    """,
                    (
                        row["station_id"].strip(),
                        row["name"].strip(),
                        row.get("region", "").strip() or None,
                        row.get("country", "UK").strip() or "UK",
                        parse_float(row.get("latitude", "")),
                        parse_float(row.get("longitude", "")),
                        parse_int(row.get("elevation_m", "")),
                        parse_int(row.get("opened_year", "")),
                        parse_int(row.get("closed_year", "")),
                    ),
                )
                result = cur.fetchone()
                if result:
                    station_map[result[1]] = result[0]
                    inserted += 1
                else:
                    # Already exists — fetch the ID
                    cur.execute("SELECT id FROM stations WHERE station_id = %s", (row["station_id"].strip(),))
                    existing = cur.fetchone()
                    if existing:
                        station_map[row["station_id"].strip()] = existing[0]
                    skipped += 1

    conn.commit()
    log.info(f"Stations: {inserted} inserted, {skipped} already existed")
    return station_map


def ingest_observations(conn, filepath: str, station_map: dict[str, int]) -> None:
    """
    Load daily observations from CSV in batches.
    Expected columns: station_id, date (YYYY-MM-DD), max_temp_c, min_temp_c, mean_temp_c,
                      rainfall_mm, sunshine_hours, wind_speed_kmh, snow_depth_cm, data_quality
    """
    log.info(f"Loading observations from {filepath}")
    batch = []
    batch_size = 1000
    inserted_total = 0
    skipped_total = 0

    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        with conn.cursor() as cur:
            for row in reader:
                sid = row["station_id"].strip()
                internal_id = station_map.get(sid)
                if internal_id is None:
                    log.warning(f"Unknown station_id '{sid}' — skipping row")
                    skipped_total += 1
                    continue

                batch.append((
                    internal_id,
                    row["date"].strip(),
                    parse_float(row.get("max_temp_c", "")),
                    parse_float(row.get("min_temp_c", "")),
                    parse_float(row.get("mean_temp_c", "")),
                    parse_float(row.get("rainfall_mm", "")),
                    parse_float(row.get("sunshine_hours", "")),
                    parse_float(row.get("wind_speed_kmh", "")),
                    parse_int(row.get("snow_depth_cm", "")),
                    parse_int(row.get("data_quality", "1")) or 1,
                ))

                if len(batch) >= batch_size:
                    execute_values(
                        cur,
                        """
                        INSERT INTO observations
                          (station_id, date, max_temp_c, min_temp_c, mean_temp_c,
                           rainfall_mm, sunshine_hours, wind_speed_kmh, snow_depth_cm, data_quality)
                        VALUES %s
                        ON CONFLICT (station_id, date) DO NOTHING
                        """,
                        batch,
                    )
                    conn.commit()
                    inserted_total += len(batch)
                    log.info(f"  {inserted_total} rows processed...")
                    batch = []

            # Final batch
            if batch:
                execute_values(
                    cur,
                    """
                    INSERT INTO observations
                      (station_id, date, max_temp_c, min_temp_c, mean_temp_c,
                       rainfall_mm, sunshine_hours, wind_speed_kmh, snow_depth_cm, data_quality)
                    VALUES %s
                    ON CONFLICT (station_id, date) DO NOTHING
                    """,
                    batch,
                )
                conn.commit()
                inserted_total += len(batch)

    log.info(f"Observations: {inserted_total} rows processed, {skipped_total} skipped (unknown station)")


def main():
    parser = argparse.ArgumentParser(description="Ingest UK climate data into PostgreSQL")
    parser.add_argument("--stations", required=True, help="Path to stations CSV file")
    parser.add_argument("--observations", required=True, help="Path to observations CSV file")
    args = parser.parse_args()

    if not os.path.exists(args.stations):
        log.error(f"Stations file not found: {args.stations}")
        sys.exit(1)
    if not os.path.exists(args.observations):
        log.error(f"Observations file not found: {args.observations}")
        sys.exit(1)

    conn = get_connection()
    try:
        station_map = ingest_stations(conn, args.stations)
        ingest_observations(conn, args.observations, station_map)
        log.info("Ingestion complete.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
