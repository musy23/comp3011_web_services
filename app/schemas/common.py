from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationMeta(BaseModel):
    page: int
    page_size: int
    total: int
    pages: int


class PaginatedResponse(BaseModel, Generic[T]):
    data: list[T]
    pagination: PaginationMeta


class ErrorResponse(BaseModel):
    error: str = Field(..., examples=["StationNotFound"])
    detail: str = Field(..., examples=["Station with id 99 not found"])
    status_code: int = Field(..., examples=[404])
