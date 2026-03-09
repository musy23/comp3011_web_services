from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictError, InvalidDateRangeError, NotFoundError
from app.repositories.observation_repository import ObservationRepository
from app.repositories.station_repository import StationRepository
from app.schemas.observation import ObservationCreate, ObservationPatch, ObservationUpdate


class ObservationService:
    def __init__(self, db: AsyncSession):
        self.repo = ObservationRepository(db)
        self.station_repo = StationRepository(db)

    async def list_observations(
        self,
        offset: int,
        limit: int,
        station_id: int | None,
        date_from: date | None,
        date_to: date | None,
        data_quality: int | None,
    ):
        if date_from and date_to and date_to < date_from:
            raise InvalidDateRangeError()
        return await self.repo.get_all(offset, limit, station_id, date_from, date_to, data_quality)

    async def get_observation(self, obs_id: int):
        obs = await self.repo.get_by_id(obs_id)
        if not obs:
            raise NotFoundError("Observation", obs_id)
        return obs

    async def create_observation(self, payload: ObservationCreate):
        # Verify station exists
        station = await self.station_repo.get_by_id(payload.station_id)
        if not station:
            raise NotFoundError("Station", payload.station_id)
        # Check for duplicate
        existing = await self.repo.get_by_station_and_date(payload.station_id, payload.date)
        if existing:
            raise ConflictError(
                f"Observation for station {payload.station_id} on {payload.date} already exists"
            )
        return await self.repo.create(payload.model_dump())

    async def update_observation(self, obs_id: int, payload: ObservationUpdate):
        obs = await self.repo.get_by_id(obs_id)
        if not obs:
            raise NotFoundError("Observation", obs_id)
        station = await self.station_repo.get_by_id(payload.station_id)
        if not station:
            raise NotFoundError("Station", payload.station_id)
        return await self.repo.update(obs, payload.model_dump())

    async def patch_observation(self, obs_id: int, payload: ObservationPatch):
        obs = await self.repo.get_by_id(obs_id)
        if not obs:
            raise NotFoundError("Observation", obs_id)
        return await self.repo.update(obs, payload.model_dump(exclude_unset=True))

    async def delete_observation(self, obs_id: int) -> None:
        obs = await self.repo.get_by_id(obs_id)
        if not obs:
            raise NotFoundError("Observation", obs_id)
        await self.repo.delete(obs)
