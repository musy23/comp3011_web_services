import hashlib

from fastapi import Depends, Header, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.exceptions import UnauthorizedError
from app.models.api_key import ApiKey


async def require_api_key(
    x_api_key: str | None = Header(None, description="API key for write operations"),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Dependency that enforces API key authentication for write endpoints."""
    if x_api_key is None:
        raise UnauthorizedError()

    key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()

    # Check against stored keys OR the admin env key
    if x_api_key == settings.admin_api_key:
        return

    result = await db.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active.is_(True))
    )
    key_record = result.scalar_one_or_none()

    if key_record is None:
        raise UnauthorizedError()


class PaginationParams:
    def __init__(
        self,
        page: int = Query(1, ge=1, description="Page number (1-indexed)"),
        page_size: int = Query(
            settings.default_page_size,
            ge=1,
            le=settings.max_page_size,
            description="Results per page",
        ),
    ):
        self.page = page
        self.page_size = page_size
        self.offset = (page - 1) * page_size
