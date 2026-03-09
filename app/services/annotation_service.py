from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundError
from app.repositories.annotation_repository import AnnotationRepository
from app.repositories.station_repository import StationRepository
from app.schemas.annotation import AnnotationCreate, AnnotationPatch, AnnotationUpdate


class AnnotationService:
    def __init__(self, db: AsyncSession):
        self.repo = AnnotationRepository(db)
        self.station_repo = StationRepository(db)

    async def list_annotations(
        self,
        offset: int,
        limit: int,
        station_id: int | None,
        approved: bool | None,
        date_from: date | None,
        date_to: date | None,
    ):
        return await self.repo.get_all(offset, limit, station_id, approved, date_from, date_to)

    async def get_annotation(self, annotation_id: int):
        annotation = await self.repo.get_by_id(annotation_id)
        if not annotation:
            raise NotFoundError("Annotation", annotation_id)
        return annotation

    async def create_annotation(self, payload: AnnotationCreate):
        station = await self.station_repo.get_by_id(payload.station_id)
        if not station:
            raise NotFoundError("Station", payload.station_id)
        return await self.repo.create(payload.model_dump())

    async def update_annotation(self, annotation_id: int, payload: AnnotationUpdate):
        annotation = await self.repo.get_by_id(annotation_id)
        if not annotation:
            raise NotFoundError("Annotation", annotation_id)
        station = await self.station_repo.get_by_id(payload.station_id)
        if not station:
            raise NotFoundError("Station", payload.station_id)
        return await self.repo.update(annotation, payload.model_dump())

    async def patch_annotation(self, annotation_id: int, payload: AnnotationPatch):
        annotation = await self.repo.get_by_id(annotation_id)
        if not annotation:
            raise NotFoundError("Annotation", annotation_id)
        return await self.repo.update(annotation, payload.model_dump(exclude_unset=True))

    async def delete_annotation(self, annotation_id: int) -> None:
        annotation = await self.repo.get_by_id(annotation_id)
        if not annotation:
            raise NotFoundError("Annotation", annotation_id)
        await self.repo.delete(annotation)
