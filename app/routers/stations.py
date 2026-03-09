import math

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import PaginationParams, require_api_key
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.station import StationCreate, StationPatch, StationResponse, StationUpdate
from app.services.station_service import StationService

router = APIRouter()


@router.get(
    "",
    response_model=PaginatedResponse[StationResponse],
    summary="List all weather stations",
    description="Returns a paginated list of UK weather stations. Filter by region, country, or active status.",
)
async def list_stations(
    pagination: PaginationParams = Depends(),
    region: str | None = Query(None, description="Filter by region name (partial match)"),
    country: str | None = Query(None, description="Filter by country (partial match)"),
    active_only: bool = Query(False, description="Only return stations that are still active"),
    db: AsyncSession = Depends(get_db),
):
    service = StationService(db)
    stations, total = await service.list_stations(
        pagination.offset, pagination.page_size, region, country, active_only
    )
    return PaginatedResponse(
        data=stations,
        pagination=PaginationMeta(
            page=pagination.page,
            page_size=pagination.page_size,
            total=total,
            pages=math.ceil(total / pagination.page_size) if total else 0,
        ),
    )


@router.get(
    "/{station_id}",
    response_model=StationResponse,
    summary="Get a station by ID",
    responses={404: {"description": "Station not found"}},
)
async def get_station(station_id: int, db: AsyncSession = Depends(get_db)):
    service = StationService(db)
    return await service.get_station(station_id)


@router.post(
    "",
    response_model=StationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new weather station",
    description="Requires API key. station_id must be unique.",
    dependencies=[Depends(require_api_key)],
    responses={
        409: {"description": "Station with that station_id already exists"},
        401: {"description": "Invalid or missing API key"},
    },
)
async def create_station(payload: StationCreate, db: AsyncSession = Depends(get_db)):
    service = StationService(db)
    return await service.create_station(payload)


@router.put(
    "/{station_id}",
    response_model=StationResponse,
    summary="Replace a station (full update)",
    dependencies=[Depends(require_api_key)],
    responses={
        404: {"description": "Station not found"},
        401: {"description": "Invalid or missing API key"},
    },
)
async def update_station(
    station_id: int, payload: StationUpdate, db: AsyncSession = Depends(get_db)
):
    service = StationService(db)
    return await service.update_station(station_id, payload)


@router.patch(
    "/{station_id}",
    response_model=StationResponse,
    summary="Partially update a station",
    dependencies=[Depends(require_api_key)],
    responses={
        404: {"description": "Station not found"},
        401: {"description": "Invalid or missing API key"},
    },
)
async def patch_station(
    station_id: int, payload: StationPatch, db: AsyncSession = Depends(get_db)
):
    service = StationService(db)
    return await service.patch_station(station_id, payload)


@router.delete(
    "/{station_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a station",
    description="Deletes the station and all associated observations and annotations.",
    dependencies=[Depends(require_api_key)],
    responses={
        404: {"description": "Station not found"},
        401: {"description": "Invalid or missing API key"},
    },
)
async def delete_station(station_id: int, db: AsyncSession = Depends(get_db)):
    service = StationService(db)
    await service.delete_station(station_id)
