from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.observation import Observation


class ObservationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(
        self,
        offset: int = 0,
        limit: int = 50,
        station_id: int | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        data_quality: int | None = None,
    ) -> tuple[list[Observation], int]:
        query = select(Observation)
        count_query = select(func.count()).select_from(Observation)

        filters = []
        if station_id:
            filters.append(Observation.station_id == station_id)
        if date_from:
            filters.append(Observation.date >= date_from)
        if date_to:
            filters.append(Observation.date <= date_to)
        if data_quality:
            filters.append(Observation.data_quality == data_quality)

        if filters:
            query = query.where(*filters)
            count_query = count_query.where(*filters)

        total = (await self.db.execute(count_query)).scalar_one()
        result = await self.db.execute(
            query.offset(offset).limit(limit).order_by(Observation.date.desc())
        )
        return list(result.scalars().all()), total

    async def get_by_id(self, obs_id: int) -> Observation | None:
        result = await self.db.execute(select(Observation).where(Observation.id == obs_id))
        return result.scalar_one_or_none()

    async def get_by_station_and_date(self, station_id: int, obs_date: date) -> Observation | None:
        result = await self.db.execute(
            select(Observation).where(
                Observation.station_id == station_id,
                Observation.date == obs_date,
            )
        )
        return result.scalar_one_or_none()

    async def create(self, data: dict) -> Observation:
        obs = Observation(**data)
        self.db.add(obs)
        await self.db.flush()
        await self.db.refresh(obs)
        return obs

    async def update(self, obs: Observation, data: dict) -> Observation:
        for key, value in data.items():
            setattr(obs, key, value)
        await self.db.flush()
        await self.db.refresh(obs)
        return obs

    async def delete(self, obs: Observation) -> None:
        await self.db.delete(obs)
        await self.db.flush()
