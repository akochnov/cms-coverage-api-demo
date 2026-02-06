"""Configuration settings for the CMS Coverage Search Tool."""

from dataclasses import dataclass


@dataclass
class Settings:
    """Application settings."""

    CMS_API_BASE_URL: str = "https://api.coverage.cms.gov"
    APP_TITLE: str = "CMS Coverage Search"
    DEBUG: bool = False

    # Cache TTL in seconds
    METADATA_CACHE_TTL: int = 3600  # 1 hour
    LICENSE_TOKEN_TTL: int = 3500   # Just under 1 hour


settings = Settings()
