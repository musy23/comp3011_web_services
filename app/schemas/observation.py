from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ObservationBase(BaseModel):
    date: date = Field(..., examples=["2023-07-15"])
    max_temp_c: float | None = Field(None, ge=-50, le=60, examples=[22.5])
    min_temp_c: float | None = Field(None, ge=-50, le=60, examples=[11.3])
    mean_temp_c: float | None = Field(None, ge=-50, le=60, examples=[16.9])
    rainfall_mm: float | None = Field(None, ge=0, le=1000, examples=[3.2])
    snow_depth_cm: int | None = Field(None, ge=0, le=500, examples=[None])
    sunshine_hours: float | None = Field(None, ge=0, le=24, examples=[8.5])
    wind_speed_kmh: float | None = Field(None, ge=0, le=500, examples=[15.0])
    data_quality: Literal[1, 2, 3] = Field(
        1,
        description="Data quality flag: 1=good, 2=estimated, 3=suspect",
    )

    @model_validator(mode="after")
    def min_below_max(self) -> "ObservationBase":
        if self.min_temp_c is not None and self.max_temp_c is not None:
            if self.min_temp_c > self.max_temp_c:
                raise ValueError("min_temp_c must be <= max_temp_c")
        return self


class ObservationCreate(ObservationBase):
    station_id: int = Field(..., description="Internal station PK")


class ObservationUpdate(ObservationBase):
    station_id: int


class ObservationPatch(BaseModel):
    max_temp_c: float | None = Field(None, ge=-50, le=60)
    min_temp_c: float | None = Field(None, ge=-50, le=60)
    mean_temp_c: float | None = Field(None, ge=-50, le=60)
    rainfall_mm: float | None = Field(None, ge=0, le=1000)
    snow_depth_cm: int | None = Field(None, ge=0, le=500)
    sunshine_hours: float | None = Field(None, ge=0, le=24)
    wind_speed_kmh: float | None = Field(None, ge=0, le=500)
    data_quality: Literal[1, 2, 3] | None = None


class ObservationResponse(ObservationBase):
    id: int
    station_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
