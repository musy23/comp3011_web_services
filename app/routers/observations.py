import math
from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import PaginationParams, require_api_key
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.observation import (
    ObservationCreate,
    ObservationPatch,
    ObservationResponse,
    ObservationUpdate,
)
from app.services.observation_service import ObservationService

router = APIRouter()


@router.get(
    "",
    response_model=PaginatedResponse[ObservationResponse],
    summary="List observations",
    description="Returns paginated daily climate observations. Filter by station, date range, or data quality.",
)
async def list_observations(
    pagination: PaginationParams = Depends(),
    station_id: int | None = Query(None, description="Filter by internal station ID"),
    date_from: date | None = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: date | None = Query(None, description="End date (YYYY-MM-DD)"),
    data_quality: int | None = Query(None, ge=1, le=3, description="Filter by quality flag: 1=good, 2=estimated, 3=suspect"),
    db: AsyncSession = Depends(get_db),
):
    service = ObservationService(db)
    observations, total = await service.list_observations(
        pagination.offset, pagination.page_size, station_id, date_from, date_to, data_quality
    )
    return PaginatedResponse(
        data=observations,
        pagination=PaginationMeta(
            page=pagination.page,
            page_size=pagination.page_size,
            total=total,
            pages=math.ceil(total / pagination.page_size) if total else 0,
        ),
    )


@router.get(
    "/{obs_id}",
    response_model=ObservationResponse,
    summary="Get a single observation",
    responses={404: {"description": "Observation not found"}},
)
async def get_observation(obs_id: int, db: AsyncSession = Depends(get_db)):
    service = ObservationService(db)
    return await service.get_observation(obs_id)


@router.post(
    "",
    response_model=ObservationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new observation",
    description="Requires API key. Each station can only have one observation per date.",
    dependencies=[Depends(require_api_key)],
    responses={
        404: {"description": "Station not found"},
        409: {"description": "Observation for this station and date already exists"},
        401: {"description": "Invalid or missing API key"},
    },
)
async def create_observation(payload: ObservationCreate, db: AsyncSession = Depends(get_db)):
    service = ObservationService(db)
    return await service.create_observation(payload)


@router.put(
    "/{obs_id}",
    response_model=ObservationResponse,
    summary="Replace an observation (full update)",
    dependencies=[Depends(require_api_key)],
    responses={
        404: {"description": "Observation or station not found"},
        401: {"description": "Invalid or missing API key"},
    },
)
async def update_observation(
    obs_id: int, payload: ObservationUpdate, db: AsyncSession = Depends(get_db)
):
    service = ObservationService(db)
    return await service.update_observation(obs_id, payload)


@router.patch(
    "/{obs_id}",
    response_model=ObservationResponse,
    summary="Partially update an observation",
    dependencies=[Depends(require_api_key)],
    responses={
        404: {"description": "Observation not found"},
        401: {"description": "Invalid or missing API key"},
    },
)
async def patch_observation(
    obs_id: int, payload: ObservationPatch, db: AsyncSession = Depends(get_db)
):
    service = ObservationService(db)
    return await service.patch_observation(obs_id, payload)


@router.delete(
    "/{obs_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an observation",
    dependencies=[Depends(require_api_key)],
    responses={
        404: {"description": "Observation not found"},
        401: {"description": "Invalid or missing API key"},
    },
)
async def delete_observation(obs_id: int, db: AsyncSession = Depends(get_db)):
    service = ObservationService(db)
    await service.delete_observation(obs_id)
