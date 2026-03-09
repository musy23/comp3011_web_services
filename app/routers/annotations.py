import math
from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import PaginationParams, require_api_key
from app.schemas.annotation import (
    AnnotationCreate,
    AnnotationPatch,
    AnnotationResponse,
    AnnotationUpdate,
)
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.services.annotation_service import AnnotationService

router = APIRouter()


@router.get(
    "",
    response_model=PaginatedResponse[AnnotationResponse],
    summary="List annotations",
    description="Returns paginated user-submitted annotations. Filter by station, approval status, or date.",
)
async def list_annotations(
    pagination: PaginationParams = Depends(),
    station_id: int | None = Query(None, description="Filter by internal station ID"),
    approved: bool | None = Query(None, description="Filter by approval status"),
    date_from: date | None = Query(None, description="Filter annotations from this observation date"),
    date_to: date | None = Query(None, description="Filter annotations up to this observation date"),
    db: AsyncSession = Depends(get_db),
):
    service = AnnotationService(db)
    annotations, total = await service.list_annotations(
        pagination.offset, pagination.page_size, station_id, approved, date_from, date_to
    )
    return PaginatedResponse(
        data=annotations,
        pagination=PaginationMeta(
            page=pagination.page,
            page_size=pagination.page_size,
            total=total,
            pages=math.ceil(total / pagination.page_size) if total else 0,
        ),
    )


@router.get(
    "/{annotation_id}",
    response_model=AnnotationResponse,
    summary="Get a single annotation",
    responses={404: {"description": "Annotation not found"}},
)
async def get_annotation(annotation_id: int, db: AsyncSession = Depends(get_db)):
    service = AnnotationService(db)
    return await service.get_annotation(annotation_id)


@router.post(
    "",
    response_model=AnnotationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a new annotation",
    description="Public endpoint — no API key required. Annotations are unapproved by default.",
    responses={404: {"description": "Station not found"}},
)
async def create_annotation(payload: AnnotationCreate, db: AsyncSession = Depends(get_db)):
    service = AnnotationService(db)
    return await service.create_annotation(payload)


@router.put(
    "/{annotation_id}",
    response_model=AnnotationResponse,
    summary="Replace an annotation (full update)",
    dependencies=[Depends(require_api_key)],
    responses={
        404: {"description": "Annotation or station not found"},
        401: {"description": "Invalid or missing API key"},
    },
)
async def update_annotation(
    annotation_id: int, payload: AnnotationUpdate, db: AsyncSession = Depends(get_db)
):
    service = AnnotationService(db)
    return await service.update_annotation(annotation_id, payload)


@router.patch(
    "/{annotation_id}",
    response_model=AnnotationResponse,
    summary="Partially update an annotation",
    description="Use this to approve/reject annotations (set approved=true/false).",
    dependencies=[Depends(require_api_key)],
    responses={
        404: {"description": "Annotation not found"},
        401: {"description": "Invalid or missing API key"},
    },
)
async def patch_annotation(
    annotation_id: int, payload: AnnotationPatch, db: AsyncSession = Depends(get_db)
):
    service = AnnotationService(db)
    return await service.patch_annotation(annotation_id, payload)


@router.delete(
    "/{annotation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an annotation",
    dependencies=[Depends(require_api_key)],
    responses={
        404: {"description": "Annotation not found"},
        401: {"description": "Invalid or missing API key"},
    },
)
async def delete_annotation(annotation_id: int, db: AsyncSession = Depends(get_db)):
    service = AnnotationService(db)
    await service.delete_annotation(annotation_id)
