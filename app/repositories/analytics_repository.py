"""
Analytics Repository
====================
All complex SQL queries for statistical analysis endpoints.
Uses PostgreSQL-native aggregate functions for efficiency:
  - regr_slope / regr_intercept / regr_r2  → linear regression
  - stddev_pop / avg                        → anomaly detection
  - EXTRACT(MONTH/YEAR FROM date)           → seasonal grouping
  - window functions                        → rolling calculations
"""

from datetime import date, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Mapping of API variable names to DB column names
VARIABLE_COLUMNS = {
    "max_temp_c": "max_temp_c",
    "min_temp_c": "min_temp_c",
    "mean_temp_c": "mean_temp_c",
    "rainfall_mm": "rainfall_mm",
    "sunshine_hours": "sunshine_hours",
    "wind_speed_kmh": "wind_speed_kmh",
    "snow_depth_cm": "snow_depth_cm",
}

MONTH_NAMES = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

SEASONS = {
    12: "Winter", 1: "Winter", 2: "Winter",
    3: "Spring", 4: "Spring", 5: "Spring",
    6: "Summer", 7: "Summer", 8: "Summer",
    9: "Autumn", 10: "Autumn", 11: "Autumn",
}


class AnalyticsRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _validate_variable(self, variable: str) -> str:
        if variable not in VARIABLE_COLUMNS:
            raise ValueError(
                f"Unknown variable '{variable}'. "
                f"Valid options: {', '.join(VARIABLE_COLUMNS.keys())}"
            )
        return VARIABLE_COLUMNS[variable]

    async def get_station_by_station_id(self, station_id: str) -> dict | None:
        result = await self.db.execute(
            text("SELECT id, station_id, name, region FROM stations WHERE station_id = :sid"),
            {"sid": station_id.upper()},
        )
        row = result.mappings().one_or_none()
        return dict(row) if row else None

    async def get_trend(
        self,
        internal_id: int,
        column: str,
        date_from: date,
        date_to: date,
    ) -> dict:
        """
        Linear regression using PostgreSQL regr_slope/regr_r2.
        Epoch seconds used as the X axis so slope is per-second; scaled to per-decade.
        Excludes the current calendar year to avoid partial-year skew.
        """
        last_complete_year = datetime.now().year - 1
        if date_to.year >= datetime.now().year:
            date_to = date(last_complete_year, 12, 31)
        sql = text(f"""
            SELECT
                regr_slope({column}, EXTRACT(EPOCH FROM date))    AS slope_per_sec,
                regr_r2({column},    EXTRACT(EPOCH FROM date))    AS r_squared,
                COUNT({column})                                    AS n
            FROM observations
            WHERE station_id = :sid
              AND date BETWEEN :d_from AND :d_to
              AND {column} IS NOT NULL
        """)
        result = await self.db.execute(sql, {"sid": internal_id, "d_from": date_from, "d_to": date_to})
        row = result.mappings().one()

        # Fetch time-series data points
        points_sql = text(f"""
            SELECT date, {column} AS value
            FROM observations
            WHERE station_id = :sid
              AND date BETWEEN :d_from AND :d_to
            ORDER BY date
        """)
        points_result = await self.db.execute(points_sql, {"sid": internal_id, "d_from": date_from, "d_to": date_to})
        points = [dict(r) for r in points_result.mappings().all()]

        seconds_per_decade = 10 * 365.25 * 24 * 3600
        slope = float(row["slope_per_sec"]) * seconds_per_decade if row["slope_per_sec"] else None
        r2 = float(row["r_squared"]) if row["r_squared"] else None

        return {"slope_per_decade": slope, "r_squared": r2, "data_points": points}

    async def get_anomalies(
        self,
        internal_id: int,
        column: str,
        threshold_sigma: float,
        date_from: date | None,
        date_to: date | None,
    ) -> list[dict]:
        """
        Detects observations more than `threshold_sigma` standard deviations
        from the monthly mean for that station and variable.
        Uses a subquery to compute monthly stats, then filters outliers.
        """
        date_filter = ""
        params: dict = {"sid": internal_id, "sigma": threshold_sigma}
        if date_from:
            date_filter += " AND o.date >= :d_from"
            params["d_from"] = date_from
        if date_to:
            date_filter += " AND o.date <= :d_to"
            params["d_to"] = date_to

        sql = text(f"""
            WITH monthly_stats AS (
                SELECT
                    EXTRACT(MONTH FROM date)::int AS month,
                    AVG({column})                 AS monthly_mean,
                    STDDEV_POP({column})           AS monthly_std
                FROM observations
                WHERE station_id = :sid
                  AND {column} IS NOT NULL
                GROUP BY EXTRACT(MONTH FROM date)
            )
            SELECT
                o.id,
                o.date,
                o.{column}                                                   AS value,
                ms.monthly_mean,
                (o.{column} - ms.monthly_mean) / NULLIF(ms.monthly_std, 0)  AS deviation_sigma
            FROM observations o
            JOIN monthly_stats ms ON EXTRACT(MONTH FROM o.date)::int = ms.month
            WHERE o.station_id = :sid
              AND o.{column} IS NOT NULL
              AND ms.monthly_std > 0
              AND ABS((o.{column} - ms.monthly_mean) / ms.monthly_std) > :sigma
              {date_filter}
            ORDER BY ABS((o.{column} - ms.monthly_mean) / ms.monthly_std) DESC
        """)
        result = await self.db.execute(sql, params)
        return [dict(r) for r in result.mappings().all()]

    async def get_seasonal(
        self,
        internal_id: int,
        column: str,
        year_from: int,
        year_to: int,
    ) -> list[dict]:
        """Monthly climate statistics over a given year range.
        Excludes the current calendar year to avoid partial-year skew."""
        last_complete_year = datetime.now().year - 1
        year_to = min(year_to, last_complete_year)
        sql = text(f"""
            SELECT
                EXTRACT(MONTH FROM date)::int  AS month,
                AVG({column})                  AS mean,
                MIN({column})                  AS min,
                MAX({column})                  AS max,
                STDDEV_POP({column})            AS std_dev,
                COUNT({column})                AS count
            FROM observations
            WHERE station_id = :sid
              AND {column} IS NOT NULL
              AND EXTRACT(YEAR FROM date) BETWEEN :y_from AND :y_to
            GROUP BY EXTRACT(MONTH FROM date)
            ORDER BY month
        """)
        result = await self.db.execute(sql, {"sid": internal_id, "y_from": year_from, "y_to": year_to})
        rows = []
        for r in result.mappings().all():
            month = int(r["month"])
            rows.append({
                "month": month,
                "month_name": MONTH_NAMES[month],
                "season": SEASONS[month],
                "mean": float(r["mean"]) if r["mean"] is not None else None,
                "min": float(r["min"]) if r["min"] is not None else None,
                "max": float(r["max"]) if r["max"] is not None else None,
                "std_dev": float(r["std_dev"]) if r["std_dev"] is not None else None,
                "count": int(r["count"]),
            })
        return rows

    async def get_compare(
        self,
        station_ids: list[str],
        column: str,
        date_from: date,
        date_to: date,
    ) -> list[dict]:
        """Aggregate statistics for multiple stations over a date range.
        Excludes the current calendar year to avoid partial-year skew."""
        last_complete_year = datetime.now().year - 1
        max_date = date(last_complete_year, 12, 31)
        if date_to.year >= datetime.now().year:
            date_to = max_date
        sql = text(f"""
            SELECT
                s.station_id,
                s.name        AS station_name,
                AVG(o.{column})   AS mean,
                MIN(o.{column})   AS min,
                MAX(o.{column})   AS max,
                COUNT(o.{column}) AS count
            FROM observations o
            JOIN stations s ON o.station_id = s.id
            WHERE s.station_id = ANY(:sids)
              AND o.date BETWEEN :d_from AND :d_to
              AND o.{column} IS NOT NULL
            GROUP BY s.station_id, s.name
            ORDER BY s.station_id
        """)
        result = await self.db.execute(sql, {
            "sids": [s.upper() for s in station_ids],
            "d_from": date_from,
            "d_to": date_to,
        })
        rows = []
        for r in result.mappings().all():
            rows.append({
                "station_id": r["station_id"],
                "station_name": r["station_name"],
                "mean": float(r["mean"]) if r["mean"] is not None else None,
                "min": float(r["min"]) if r["min"] is not None else None,
                "max": float(r["max"]) if r["max"] is not None else None,
                "count": int(r["count"]),
            })
        return rows

    async def get_extremes(self, region: str | None = None) -> dict:
        """All-time record high, low, wettest day, and most sunshine."""
        region_filter = "AND s.region ILIKE :region" if region else ""
        params = {"region": f"%{region}%"} if region else {}

        async def fetch_extreme(col: str, order: str) -> dict | None:
            sql = text(f"""
                SELECT s.station_id, s.name AS station_name, s.region,
                       o.date, o.{col} AS value
                FROM observations o
                JOIN stations s ON o.station_id = s.id
                WHERE o.{col} IS NOT NULL
                  {region_filter}
                ORDER BY o.{col} {order}
                LIMIT 1
            """)
            result = await self.db.execute(sql, params)
            row = result.mappings().one_or_none()
            return dict(row) if row else None

        return {
            "hottest_day": await fetch_extreme("max_temp_c", "DESC"),
            "coldest_day": await fetch_extreme("min_temp_c", "ASC"),
            "wettest_day": await fetch_extreme("rainfall_mm", "DESC"),
            "most_sunshine": await fetch_extreme("sunshine_hours", "DESC"),
        }

    async def get_heatmap(
        self,
        internal_id: int,
        column: str,
        year: int,
    ) -> list[dict]:
        """All daily values for a given station, variable, and year."""
        sql = text(f"""
            SELECT date, {column} AS value
            FROM observations
            WHERE station_id = :sid
              AND EXTRACT(YEAR FROM date)::int = :year
            ORDER BY date
        """)
        result = await self.db.execute(sql, {"sid": internal_id, "year": year})
        return [dict(r) for r in result.mappings().all()]

    async def get_climate_normal(self, internal_id: int) -> list[dict]:
        """
        WMO 30-year climate normals for the period 1991–2020.
        Returns monthly averages for temperature, rainfall, and sunshine.
        """
        sql = text("""
            SELECT
                EXTRACT(MONTH FROM date)::int  AS month,
                AVG(max_temp_c)                AS mean_max_temp_c,
                AVG(min_temp_c)                AS mean_min_temp_c,
                AVG(rainfall_mm)               AS mean_rainfall_mm,
                AVG(sunshine_hours)            AS mean_sunshine_hours
            FROM observations
            WHERE station_id = :sid
              AND date BETWEEN '1991-01-01' AND '2020-12-31'
            GROUP BY EXTRACT(MONTH FROM date)
            ORDER BY month
        """)
        result = await self.db.execute(sql, {"sid": internal_id})
        rows = []
        for r in result.mappings().all():
            month = int(r["month"])
            rows.append({
                "month": month,
                "month_name": MONTH_NAMES[month],
                "mean_max_temp_c": float(r["mean_max_temp_c"]) if r["mean_max_temp_c"] is not None else None,
                "mean_min_temp_c": float(r["mean_min_temp_c"]) if r["mean_min_temp_c"] is not None else None,
                "mean_rainfall_mm": float(r["mean_rainfall_mm"]) if r["mean_rainfall_mm"] is not None else None,
                "mean_sunshine_hours": float(r["mean_sunshine_hours"]) if r["mean_sunshine_hours"] is not None else None,
            })
        return rows
