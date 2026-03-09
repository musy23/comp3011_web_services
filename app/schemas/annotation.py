from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class AnnotationBase(BaseModel):
    observation_date: date | None = Field(None, examples=["2023-07-15"])
    note: str = Field(..., min_length=5, max_length=2000, examples=["Unusually high wind gust recorded during storm."])
    submitted_by: str | None = Field(None, max_length=100, examples=["researcher@leeds.ac.uk"])


class AnnotationCreate(AnnotationBase):
    station_id: int = Field(..., description="Internal station PK")


class AnnotationUpdate(AnnotationBase):
    station_id: int
    approved: bool = False


class AnnotationPatch(BaseModel):
    observation_date: date | None = None
    note: str | None = Field(None, min_length=5, max_length=2000)
    submitted_by: str | None = Field(None, max_length=100)
    approved: bool | None = None


class AnnotationResponse(AnnotationBase):
    id: int
    station_id: int
    approved: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
