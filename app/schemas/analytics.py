from datetime import date

from pydantic import BaseModel, Field


class TrendPoint(BaseModel):
    date: date
    value: float | None


class TrendResponse(BaseModel):
    station_id: str
    variable: str
    date_from: date
    date_to: date
    slope_per_decade: float | None = Field(None, description="Rate of change per decade")
    r_squared: float | None = Field(None, description="Goodness of fit (0–1)")
    data_points: list[TrendPoint]


class AnomalyRecord(BaseModel):
    id: int
    date: date
    value: float
    monthly_mean: float
    deviation_sigma: float = Field(..., description="Standard deviations from monthly mean")
    variable: str


class AnomalyResponse(BaseModel):
    station_id: str
    variable: str
    threshold_sigma: float
    anomalies: list[AnomalyRecord]


class SeasonalRecord(BaseModel):
    month: int
    month_name: str
    season: str
    mean: float | None
    min: float | None
    max: float | None
    std_dev: float | None
    count: int


class SeasonalResponse(BaseModel):
    station_id: str
    variable: str
    year_from: int
    year_to: int
    monthly_stats: list[SeasonalRecord]


class ComparisonStation(BaseModel):
    station_id: str
    station_name: str
    mean: float | None
    min: float | None
    max: float | None
    count: int


class CompareResponse(BaseModel):
    variable: str
    date_from: date
    date_to: date
    stations: list[ComparisonStation]


class ExtremeRecord(BaseModel):
    station_id: str
    station_name: str
    region: str | None
    date: date
    value: float


class ExtremesResponse(BaseModel):
    hottest_day: ExtremeRecord | None
    coldest_day: ExtremeRecord | None
    wettest_day: ExtremeRecord | None
    most_sunshine: ExtremeRecord | None


class ClimateNormalRecord(BaseModel):
    month: int
    month_name: str
    mean_max_temp_c: float | None
    mean_min_temp_c: float | None
    mean_rainfall_mm: float | None
    mean_sunshine_hours: float | None


class ClimateNormalResponse(BaseModel):
    station_id: str
    station_name: str
    normal_period: str = "1991-2020"
    normals: list[ClimateNormalRecord]


class HeatmapCell(BaseModel):
    date: date
    value: float | None


class HeatmapResponse(BaseModel):
    station_id: str
    variable: str
    year: int
    cells: list[HeatmapCell]
