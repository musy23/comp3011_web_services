from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.annotation import UserAnnotation


class AnnotationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(
        self,
        offset: int = 0,
        limit: int = 50,
        station_id: int | None = None,
        approved: bool | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> tuple[list[UserAnnotation], int]:
        query = select(UserAnnotation)
        count_query = select(func.count()).select_from(UserAnnotation)

        filters = []
        if station_id:
            filters.append(UserAnnotation.station_id == station_id)
        if approved is not None:
            filters.append(UserAnnotation.approved == approved)
        if date_from:
            filters.append(UserAnnotation.observation_date >= date_from)
        if date_to:
            filters.append(UserAnnotation.observation_date <= date_to)

        if filters:
            query = query.where(*filters)
            count_query = count_query.where(*filters)

        total = (await self.db.execute(count_query)).scalar_one()
        result = await self.db.execute(
            query.offset(offset).limit(limit).order_by(UserAnnotation.created_at.desc())
        )
        return list(result.scalars().all()), total

    async def get_by_id(self, annotation_id: int) -> UserAnnotation | None:
        result = await self.db.execute(
            select(UserAnnotation).where(UserAnnotation.id == annotation_id)
        )
        return result.scalar_one_or_none()

    async def create(self, data: dict) -> UserAnnotation:
        annotation = UserAnnotation(**data)
        self.db.add(annotation)
        await self.db.flush()
        await self.db.refresh(annotation)
        return annotation

    async def update(self, annotation: UserAnnotation, data: dict) -> UserAnnotation:
        for key, value in data.items():
            setattr(annotation, key, value)
        await self.db.flush()
        await self.db.refresh(annotation)
        return annotation

    async def delete(self, annotation: UserAnnotation) -> None:
        await self.db.delete(annotation)
        await self.db.flush()
