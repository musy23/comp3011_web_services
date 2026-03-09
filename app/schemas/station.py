from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StationBase(BaseModel):
    station_id: str = Field(..., max_length=20, examples=["ABERDEEN"], description="Met Office station identifier")
    name: str = Field(..., max_length=100, examples=["Aberdeen Airport"], description="Full station name")
    region: str | None = Field(None, max_length=50, examples=["Scotland"])
    country: str = Field("UK", max_length=20)
    latitude: float | None = Field(None, ge=-90, le=90, examples=[57.2017])
    longitude: float | None = Field(None, ge=-180, le=180, examples=[-2.2078])
    elevation_m: int | None = Field(None, ge=-500, le=9000, examples=[65])
    opened_year: int | None = Field(None, ge=1800, le=2100, examples=[1931])
    closed_year: int | None = Field(None, ge=1800, le=2100, examples=[None])

    @model_validator(mode="after")
    def closed_after_opened(self) -> "StationBase":
        if self.opened_year and self.closed_year:
            if self.closed_year < self.opened_year:
                raise ValueError("closed_year must be >= opened_year")
        return self


class StationCreate(StationBase):
    pass


class StationUpdate(StationBase):
    pass


class StationPatch(BaseModel):
    name: str | None = Field(None, max_length=100)
    region: str | None = None
    country: str | None = Field(None, max_length=20)
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    elevation_m: int | None = Field(None, ge=-500, le=9000)
    opened_year: int | None = Field(None, ge=1800, le=2100)
    closed_year: int | None = Field(None, ge=1800, le=2100)


class StationResponse(StationBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StationSummary(BaseModel):
    """Lightweight station representation used in observation responses."""
    id: int
    station_id: str
    name: str
    region: str | None

    model_config = ConfigDict(from_attributes=True)
