from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.station import Station


class StationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(
        self,
        offset: int = 0,
        limit: int = 50,
        region: str | None = None,
        country: str | None = None,
        active_only: bool = False,
    ) -> tuple[list[Station], int]:
        query = select(Station)
        count_query = select(func.count()).select_from(Station)

        if region:
            query = query.where(Station.region.ilike(f"%{region}%"))
            count_query = count_query.where(Station.region.ilike(f"%{region}%"))
        if country:
            query = query.where(Station.country.ilike(f"%{country}%"))
            count_query = count_query.where(Station.country.ilike(f"%{country}%"))
        if active_only:
            query = query.where(Station.closed_year.is_(None))
            count_query = count_query.where(Station.closed_year.is_(None))

        total = (await self.db.execute(count_query)).scalar_one()
        result = await self.db.execute(query.offset(offset).limit(limit).order_by(Station.name))
        return list(result.scalars().all()), total

    async def get_by_id(self, station_id: int) -> Station | None:
        result = await self.db.execute(select(Station).where(Station.id == station_id))
        return result.scalar_one_or_none()

    async def get_by_station_id(self, station_id: str) -> Station | None:
        result = await self.db.execute(
            select(Station).where(Station.station_id == station_id.upper())
        )
        return result.scalar_one_or_none()

    async def create(self, data: dict) -> Station:
        station = Station(**data)
        self.db.add(station)
        await self.db.flush()
        await self.db.refresh(station)
        return station

    async def update(self, station: Station, data: dict) -> Station:
        for key, value in data.items():
            setattr(station, key, value)
        await self.db.flush()
        await self.db.refresh(station)
        return station

    async def delete(self, station: Station) -> None:
        await self.db.delete(station)
        await self.db.flush()
