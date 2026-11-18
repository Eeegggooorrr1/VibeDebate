from pydantic import Field

from .base import EnvSettings


class CacheSettings(EnvSettings):
    redis_url: str = Field(min_length=1)
    cache_enabled: bool = True
    cache_namespace: str = Field(min_length=1)
    cache_timeout_seconds: float = Field(default=0.3, gt=0, le=5)
    cache_catalog_ttl: int = Field(default=900, ge=1)
    cache_view_ttl: int = Field(default=60, ge=1)
    cache_history_ttl: int = Field(default=300, ge=1)
    cache_analysis_ttl: int = Field(default=3600, ge=1)
    cache_status_ttl: int = Field(default=2, ge=1)
    cache_max_entry_bytes: int = Field(default=2_000_000, ge=1024)


def create_cache_settings() -> CacheSettings:
    return CacheSettings()
