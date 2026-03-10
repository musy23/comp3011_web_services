from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.repositories.analytics_repository import VARIABLE_COLUMNS
from app.schemas.analytics import (
    AnomalyResponse,
    ClimateNormalResponse,
    CompareResponse,
    ExtremesResponse,
    HeatmapResponse,
    SeasonalResponse,
    TrendResponse,
)
from app.services.analytics_service import AnalyticsService

router = APIRouter()

VALID_VARIABLES = list(VARIABLE_COLUMNS.keys())
VARIABLE_DESC = "Climate variable: " + ", ".join(VALID_VARIABLES)


@router.get(
    "/trends/{station_id}",
    response_model=TrendResponse,
    summary="Temperature/rainfall trend over time",
    description="""
Computes a linear regression for any climate variable at a given station.
Returns the slope (rate of change per decade), R² goodness-of-fit, and all data points.

Uses PostgreSQL's native `regr_slope` and `regr_r2` aggregate functions for efficiency.
A positive slope indicates the variable is increasing over time.
    """,
)
async def get_trends(
    station_id: str,
    variable: str = Query("mean_temp_c", description=VARIABLE_DESC),
    date_from: date = Query(..., description="Start date (YYYY-MM-DD)"),
    date_to: date = Query(..., description="End date (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
):
    service = AnalyticsService(db)
    return await service.get_trend(station_id, variable, date_from, date_to)


@router.get(
    "/anomalies/{station_id}",
    response_model=AnomalyResponse,
    summary="Detect statistical anomalies",
    description="""
Identifies observations that deviate more than `threshold_sigma` standard deviations
from the long-term monthly mean for that station.

Monthly means and standard deviations are computed across all available data,
then each observation is scored. Useful for identifying extreme weather events.
    """,
)
async def get_anomalies(
    station_id: str,
    variable: str = Query("max_temp_c", description=VARIABLE_DESC),
    threshold_sigma: float = Query(2.0, ge=0.5, le=5.0, description="Detection threshold in standard deviations"),
    date_from: date | None = Query(None, description="Optional start date filter"),
    date_to: date | None = Query(None, description="Optional end date filter"),
    db: AsyncSession = Depends(get_db),
):
    service = AnalyticsService(db)
    return await service.get_anomalies(station_id, variable, threshold_sigma, date_from, date_to)


@router.get(
    "/seasonal/{station_id}",
    response_model=SeasonalResponse,
    summary="Seasonal and monthly climate statistics",
    description="""
Returns month-by-month statistics (mean, min, max, standard deviation) for a given
variable and year range. Results include season labels (Winter/Spring/Summer/Autumn).

Useful for understanding seasonal patterns and building climate charts.
    """,
)
async def get_seasonal(
    station_id: str,
    variable: str = Query("mean_temp_c", description=VARIABLE_DESC),
    year_from: int = Query(1990, ge=1800, le=2100, description="Start year"),
    year_to: int = Query(2024, ge=1800, le=2100, description="End year"),
    db: AsyncSession = Depends(get_db),
):
    service = AnalyticsService(db)
    return await service.get_seasonal(station_id, variable, year_from, year_to)


@router.get(
    "/compare",
    response_model=CompareResponse,
    summary="Compare multiple stations",
    description="""
Compares aggregate statistics (mean, min, max, count) for a climate variable
across multiple UK weather stations over a specified date range.

Pass station IDs as a comma-separated list, e.g. `stations=LEEDS,MANCHESTER,EDINBURGH`.
    """,
)
async def compare_stations(
    stations: str = Query(..., description="Comma-separated list of station IDs (min 2), e.g. LEEDS,MANCHESTER"),
    variable: str = Query("mean_temp_c", description=VARIABLE_DESC),
    date_from: date = Query(..., description="Start date (YYYY-MM-DD)"),
    date_to: date = Query(..., description="End date (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
):
    station_list = [s.strip() for s in stations.split(",") if s.strip()]
    service = AnalyticsService(db)
    return await service.get_compare(station_list, variable, date_from, date_to)


@router.get(
    "/extremes",
    response_model=ExtremesResponse,
    summary="All-time climate records",
    description="""
Returns all-time UK climate records:
- Hottest day (highest max_temp_c)
- Coldest day (lowest min_temp_c)
- Wettest day (highest rainfall_mm)
- Most sunshine (highest sunshine_hours)

Optionally filter by region to get regional records.
    """,
)
async def get_extremes(
    region: str | None = Query(None, description="Filter by region name (partial match), e.g. Scotland"),
    db: AsyncSession = Depends(get_db),
):
    service = AnalyticsService(db)
    return await service.get_extremes(region)


@router.get(
    "/heatmap/{station_id}",
    response_model=HeatmapResponse,
    summary="Daily values for calendar heatmap",
    description="""
Returns all daily values for a given variable and year, structured for rendering
as a calendar heatmap (e.g. GitHub-style contribution graph).

Each cell represents one day with its observed value (or null if missing).
    """,
)
async def get_heatmap(
    station_id: str,
    variable: str = Query("mean_temp_c", description=VARIABLE_DESC),
    year: int = Query(..., ge=1800, le=2100, description="Year to retrieve (e.g. 2023)"),
    db: AsyncSession = Depends(get_db),
):
    service = AnalyticsService(db)
    return await service.get_heatmap(station_id, variable, year)


@router.get(
    "/climate-normal/{station_id}",
    response_model=ClimateNormalResponse,
    summary="WMO 30-year climate normals (1991–2020)",
    description="""
Returns the World Meteorological Organisation (WMO) standard 30-year climate normals
for the period 1991–2020 at the specified station.

Monthly averages are computed for maximum temperature, minimum temperature,
rainfall, and sunshine hours. These are used internationally as the baseline
for comparing current climate conditions.
    """,
)
async def get_climate_normal(
    station_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = AnalyticsService(db)
    return await service.get_climate_normal(station_id)
