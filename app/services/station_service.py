from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictError, NotFoundError
from app.repositories.station_repository import StationRepository
from app.schemas.station import StationCreate, StationPatch, StationUpdate


class StationService:
    def __init__(self, db: AsyncSession):
        self.repo = StationRepository(db)

    async def list_stations(self, offset: int, limit: int, region: str | None,
                            country: str | None, active_only: bool):
        return await self.repo.get_all(offset, limit, region, country, active_only)

    async def get_station(self, station_id: int):
        station = await self.repo.get_by_id(station_id)
        if not station:
            raise NotFoundError("Station", station_id)
        return station

    async def create_station(self, payload: StationCreate):
        existing = await self.repo.get_by_station_id(payload.station_id)
        if existing:
            raise ConflictError(f"Station with station_id '{payload.station_id}' already exists")
        data = payload.model_dump()
        data["station_id"] = data["station_id"].upper()
        return await self.repo.create(data)

    async def update_station(self, station_id: int, payload: StationUpdate):
        station = await self.repo.get_by_id(station_id)
        if not station:
            raise NotFoundError("Station", station_id)
        data = payload.model_dump()
        data["station_id"] = data["station_id"].upper()
        return await self.repo.update(station, data)

    async def patch_station(self, station_id: int, payload: StationPatch):
        station = await self.repo.get_by_id(station_id)
        if not station:
            raise NotFoundError("Station", station_id)
        # Only apply fields that were explicitly set
        data = payload.model_dump(exclude_unset=True)
        return await self.repo.update(station, data)

    async def delete_station(self, station_id: int) -> None:
        station = await self.repo.get_by_id(station_id)
        if not station:
            raise NotFoundError("Station", station_id)
        await self.repo.delete(station)
