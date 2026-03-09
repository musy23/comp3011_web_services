from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, SmallInteger, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Observation(Base):
    __tablename__ = "observations"
    __table_args__ = (UniqueConstraint("station_id", "date", name="uq_station_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    station_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("stations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # Temperature (°C)
    max_temp_c: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    min_temp_c: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    mean_temp_c: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)

    # Precipitation
    rainfall_mm: Mapped[float | None] = mapped_column(Numeric(7, 2), nullable=True)
    snow_depth_cm: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Other climate variables
    sunshine_hours: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    wind_speed_kmh: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)

    # Data quality flag: 1=good, 2=estimated, 3=suspect
    data_quality: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    station: Mapped["Station"] = relationship("Station", back_populates="observations")  # noqa: F821
