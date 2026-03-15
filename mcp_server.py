"""
UK Climate Insights — MCP Server
=================================
Exposes the UK Climate API as a set of tools callable by AI assistants
(Claude Desktop, any MCP-compatible client) via the Model Context Protocol.

Run standalone:
    python mcp_server.py

Or inspect with the MCP CLI:
    fastmcp dev mcp_server.py

Tools available:
  - list_stations            List all UK weather stations
  - get_station_info         Details for a single station
  - get_climate_normals      WMO 1991–2020 monthly averages for a station
  - get_seasonal_stats       Monthly stats (mean/min/max/std) for any variable & year range
  - get_climate_trend        Linear regression trend with slope per decade and R²
  - detect_anomalies         Find months that deviate beyond a sigma threshold
  - compare_stations         Aggregate stats for multiple stations side-by-side
  - get_all_time_records     All-time UK climate records (hottest/coldest/wettest/sunniest)
  - get_observations         Paginated raw monthly observations for a station
"""

from datetime import date
from typing import Literal

from fastmcp import FastMCP

from app.database import AsyncSessionLocal
from app.services.analytics_service import AnalyticsService
from app.services.station_service import StationService
from app.repositories.observation_repository import ObservationRepository

mcp = FastMCP(
    name="UK Climate Insights",
    instructions=(
        "You have access to historical UK weather data from 8 Met Office stations "
        "spanning from 1853 to 2025. Use these tools to answer questions about UK climate, "
        "temperature trends, rainfall patterns, extreme weather events, and seasonal norms. "
        "Station IDs are: HEATHROW, OXFORD, CAMBRIDGE, DURHAM, SHEFFIELD, CARDIFF, ARMAGH, LERWICK."
    ),
)

VALID_VARIABLES = ["max_temp_c", "min_temp_c", "mean_temp_c", "rainfall_mm", "sunshine_hours"]
VariableName = Literal["max_temp_c", "min_temp_c", "mean_temp_c", "rainfall_mm", "sunshine_hours"]


# ── Stations ──────────────────────────────────────────────────────────────────

@mcp.tool()
async def list_stations(
    region: str | None = None,
    country: str | None = None,
) -> list[dict]:
    """
    List all UK weather stations with their coordinates, region, elevation,
    and date range of available data.

    Args:
        region: Optional filter by region name (partial match), e.g. "Yorkshire"
        country: Optional filter by country, e.g. "England", "Scotland"
    """
    async with AsyncSessionLocal() as db:
        service = StationService(db)
        result = await service.list_stations(
            offset=0, limit=100,
            region=region, country=country, active_only=False,
        )
    # list_stations returns (items, total) tuple
    items = result[0] if isinstance(result, tuple) else (result if isinstance(result, list) else [])
    return [
        {
            "station_id": s.station_id,
            "name": s.name,
            "region": s.region,
            "country": s.country,
            "latitude": float(s.latitude) if s.latitude is not None else None,
            "longitude": float(s.longitude) if s.longitude is not None else None,
            "elevation_m": s.elevation_m,
        }
        for s in items
    ]


@mcp.tool()
async def get_climate_normals(station_id: str) -> dict:
    """
    Return WMO standard 30-year climate normals (1991–2020) for a station.
    Includes monthly averages for max temperature, min temperature, rainfall,
    and sunshine hours — the internationally recognised climate baseline.

    Args:
        station_id: Station identifier, e.g. "HEATHROW", "DURHAM", "OXFORD"
    """
    async with AsyncSessionLocal() as db:
        service = AnalyticsService(db)
        return await service.get_climate_normal(station_id.upper())


# ── Analytics ─────────────────────────────────────────────────────────────────

@mcp.tool()
async def get_seasonal_stats(
    station_id: str,
    variable: VariableName = "mean_temp_c",
    year_from: int = 1991,
    year_to: int = 2020,
) -> dict:
    """
    Monthly climate statistics (mean, min, max, standard deviation, record count)
    for any climate variable over a chosen year range. Useful for understanding
    the seasonal cycle at a station.

    Args:
        station_id: Station identifier, e.g. "HEATHROW"
        variable:   Climate variable — one of: max_temp_c, min_temp_c, mean_temp_c,
                    rainfall_mm, sunshine_hours
        year_from:  Start year (default 1991)
        year_to:    End year (default 2020, capped at last complete year)
    """
    async with AsyncSessionLocal() as db:
        service = AnalyticsService(db)
        return await service.get_seasonal(station_id.upper(), variable, year_from, year_to)


@mcp.tool()
async def get_climate_trend(
    station_id: str,
    variable: VariableName = "mean_temp_c",
    date_from: str = "1950-01-01",
    date_to: str = "2025-12-31",
) -> dict:
    """
    Compute a linear regression trend for any climate variable at a station.
    Returns the slope (change per decade), R² goodness-of-fit, and all data points.
    A positive slope means the variable is increasing over time.

    Args:
        station_id: Station identifier, e.g. "DURHAM"
        variable:   Climate variable — one of: max_temp_c, min_temp_c, mean_temp_c,
                    rainfall_mm, sunshine_hours
        date_from:  Start date in YYYY-MM-DD format
        date_to:    End date in YYYY-MM-DD format (capped at last complete year)
    """
    async with AsyncSessionLocal() as db:
        service = AnalyticsService(db)
        return await service.get_trend(
            station_id.upper(), variable,
            date.fromisoformat(date_from),
            date.fromisoformat(date_to),
        )


@mcp.tool()
async def detect_anomalies(
    station_id: str,
    variable: VariableName = "max_temp_c",
    threshold_sigma: float = 2.0,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict:
    """
    Detect months where a climate variable deviates unusually far from the
    long-term monthly average, using a z-score (standard deviation) threshold.
    Useful for finding heatwaves, cold snaps, droughts, and flood months.

    At threshold_sigma=2.0, roughly 5% of months are flagged by chance.
    At threshold_sigma=3.0, less than 0.3% — only the most extreme events.

    Args:
        station_id:       Station identifier, e.g. "HEATHROW"
        variable:         Climate variable to analyse
        threshold_sigma:  Detection threshold in standard deviations (0.5–5.0)
        date_from:        Optional start date filter (YYYY-MM-DD)
        date_to:          Optional end date filter (YYYY-MM-DD)
    """
    async with AsyncSessionLocal() as db:
        service = AnalyticsService(db)
        return await service.get_anomalies(
            station_id.upper(),
            variable,
            threshold_sigma,
            date.fromisoformat(date_from) if date_from else None,
            date.fromisoformat(date_to) if date_to else None,
        )


@mcp.tool()
async def compare_stations(
    station_ids: list[str],
    variable: VariableName = "mean_temp_c",
    date_from: str = "1991-01-01",
    date_to: str = "2020-12-31",
) -> dict:
    """
    Compare aggregate statistics (mean, min, max, record count) for a climate
    variable across multiple stations over a date range. Useful for understanding
    regional climate differences across the UK.

    Args:
        station_ids: List of 2–8 station IDs, e.g. ["HEATHROW", "DURHAM", "LERWICK"]
        variable:    Climate variable to compare
        date_from:   Start date (YYYY-MM-DD)
        date_to:     End date (YYYY-MM-DD)
    """
    async with AsyncSessionLocal() as db:
        service = AnalyticsService(db)
        return await service.get_compare(
            [s.upper() for s in station_ids],
            variable,
            date.fromisoformat(date_from),
            date.fromisoformat(date_to),
        )


@mcp.tool()
async def get_all_time_records(region: str | None = None) -> dict:
    """
    Return all-time UK climate records across all stations:
    - Hottest month (highest max_temp_c)
    - Coldest month (lowest min_temp_c)
    - Wettest month (highest rainfall_mm)
    - Most sunshine (highest sunshine_hours)

    Args:
        region: Optional region filter, e.g. "Scotland", "Wales"
    """
    async with AsyncSessionLocal() as db:
        service = AnalyticsService(db)
        return await service.get_extremes(region)


@mcp.tool()
async def get_observations(
    station_id: str,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 24,
) -> dict:
    """
    Retrieve raw monthly observations for a station, optionally filtered by date range.
    Each record contains max/min/mean temperature, rainfall, sunshine hours, and snow depth.

    Args:
        station_id: Station identifier, e.g. "OXFORD"
        date_from:  Optional start date (YYYY-MM-DD)
        date_to:    Optional end date (YYYY-MM-DD)
        limit:      Max records to return (default 24, max 120)
    """
    from app.repositories.station_repository import StationRepository
    from app.repositories.observation_repository import ObservationRepository

    limit = min(limit, 120)
    async with AsyncSessionLocal() as db:
        station_repo = StationRepository(db)
        station = await station_repo.get_by_station_id(station_id.upper())
        if not station:
            return {"error": f"Station '{station_id}' not found"}

        obs_repo = ObservationRepository(db)
        d_from = date.fromisoformat(date_from) if date_from else None
        d_to = date.fromisoformat(date_to) if date_to else None
        observations, total = await obs_repo.get_all(
            offset=0, limit=limit,
            station_id=station.id,
            date_from=d_from,
            date_to=d_to,
        )

    return {
        "station_id": station_id.upper(),
        "total_matching": total,
        "returned": len(observations),
        "observations": [
            {
                "date": str(o.date),
                "max_temp_c": float(o.max_temp_c) if o.max_temp_c is not None else None,
                "min_temp_c": float(o.min_temp_c) if o.min_temp_c is not None else None,
                "mean_temp_c": float(o.mean_temp_c) if o.mean_temp_c is not None else None,
                "rainfall_mm": float(o.rainfall_mm) if o.rainfall_mm is not None else None,
                "sunshine_hours": float(o.sunshine_hours) if o.sunshine_hours is not None else None,
                "snow_depth_cm": o.snow_depth_cm,
            }
            for o in observations
        ],
    }


if __name__ == "__main__":
    mcp.run()
