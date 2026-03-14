from datetime import date

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import InvalidDateRangeError, NotFoundError
from app.repositories.analytics_repository import AnalyticsRepository


class AnalyticsService:
    def __init__(self, db: AsyncSession):
        self.repo = AnalyticsRepository(db)

    async def _resolve_station(self, station_id: str) -> dict:
        station = await self.repo.get_station_by_station_id(station_id)
        if not station:
            raise NotFoundError("Station", station_id)
        return station

    async def get_trend(
        self,
        station_id: str,
        variable: str,
        date_from: date,
        date_to: date,
    ) -> dict:
        if date_to < date_from:
            raise InvalidDateRangeError()
        station = await self._resolve_station(station_id)
        try:
            column = self.repo._validate_variable(variable)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        data = await self.repo.get_trend(station["id"], column, date_from, date_to)
        return {
            "station_id": station["station_id"],
            "variable": variable,
            "date_from": date_from,
            "date_to": date_to,
            **data,
        }

    async def get_anomalies(
        self,
        station_id: str,
        variable: str,
        threshold_sigma: float,
        date_from: date | None,
        date_to: date | None,
    ) -> dict:
        station = await self._resolve_station(station_id)
        try:
            column = self.repo._validate_variable(variable)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        anomalies = await self.repo.get_anomalies(
            station["id"], column, threshold_sigma, date_from, date_to
        )
        # Attach variable name to each record
        for a in anomalies:
            a["variable"] = variable
        return {
            "station_id": station["station_id"],
            "variable": variable,
            "threshold_sigma": threshold_sigma,
            "anomalies": anomalies,
        }

    async def get_seasonal(
        self,
        station_id: str,
        variable: str,
        year_from: int,
        year_to: int,
    ) -> dict:
        if year_to < year_from:
            raise HTTPException(status_code=422, detail="year_to must be >= year_from")
        station = await self._resolve_station(station_id)
        try:
            column = self.repo._validate_variable(variable)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        monthly = await self.repo.get_seasonal(station["id"], column, year_from, year_to)
        return {
            "station_id": station["station_id"],
            "variable": variable,
            "year_from": year_from,
            "year_to": year_to,
            "monthly_stats": monthly,
        }

    async def get_compare(
        self,
        station_ids: list[str],
        variable: str,
        date_from: date,
        date_to: date,
    ) -> dict:
        if date_to < date_from:
            raise InvalidDateRangeError()
        if len(station_ids) < 2:
            raise HTTPException(status_code=422, detail="Provide at least 2 station IDs to compare")
        try:
            column = self.repo._validate_variable(variable)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        stations_data = await self.repo.get_compare(station_ids, column, date_from, date_to)
        return {
            "variable": variable,
            "date_from": date_from,
            "date_to": date_to,
            "stations": stations_data,
        }

    async def get_extremes(self, region: str | None) -> dict:
        return await self.repo.get_extremes(region)

    async def get_heatmap(
        self,
        station_id: str,
        variable: str,
        year: int,
    ) -> dict:
        station = await self._resolve_station(station_id)
        try:
            column = self.repo._validate_variable(variable)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        cells = await self.repo.get_heatmap(station["id"], column, year)
        return {
            "station_id": station["station_id"],
            "variable": variable,
            "year": year,
            "cells": cells,
        }

    async def get_climate_normal(self, station_id: str) -> dict:
        station = await self._resolve_station(station_id)
        normals = await self.repo.get_climate_normal(station["id"])
        return {
            "station_id": station["station_id"],
            "station_name": station["name"],
            "normal_period": "1991-2020",
            "normals": normals,
        }
