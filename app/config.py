from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/uk_climate"
    database_url_sync: str = "postgresql://postgres:postgres@localhost:5432/uk_climate"

    # API
    api_title: str = "UK Climate Insights API"
    api_version: str = "1.0.0"
    api_description: str = """
A comprehensive REST API for historical UK weather observations.

## Features
- Full CRUD for weather stations, observations, and user annotations
- Statistical analytics: trends, anomalies, seasonal patterns, climate normals
- API key authentication for write operations
- Rate limiting on expensive analytics endpoints
- MCP (Model Context Protocol) server compatible

## Data Sources
Historical data sourced from the UK Met Office MIDAS dataset via the CEDA Archive
and the data.gov.uk open data portal, under the Open Government Licence v3.0.
"""

    # Auth
    admin_api_key: str = "change-me-in-production"

    # Pagination
    default_page_size: int = 50
    max_page_size: int = 500

    # Cache TTL (seconds)
    analytics_cache_ttl: int = 3600

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
