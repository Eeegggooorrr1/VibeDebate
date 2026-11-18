from collections.abc import AsyncIterator
import httpx
from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from vibedebate.core.config import DatabaseSettings
from vibedebate.core.db import create_engine, transaction
from redis.asyncio import Redis
from redis.asyncio.retry import Retry
from redis.backoff import NoBackoff
from vibedebate.core.config.cache import CacheSettings, create_cache_settings
from vibedebate.infrastructure.redis_cache import RedisCacheRepository
from vibedebate.repositories.cache import CacheRepository, NullCacheRepository
from vibedebate.repositories.cached import ReadCache


class InfrastructureProvider(Provider):
    cache_settings = provide(staticmethod(create_cache_settings), scope=Scope.APP)
    read_cache = provide(ReadCache, scope=Scope.APP)

    @provide(scope=Scope.APP)
    async def cache(self, settings: CacheSettings) -> AsyncIterator[CacheRepository]:
        if not settings.cache_enabled:
            yield NullCacheRepository()
            return

        client = Redis.from_url(
            settings.redis_url,
            socket_timeout=settings.cache_timeout_seconds,
            socket_connect_timeout=settings.cache_timeout_seconds,
            retry=Retry(NoBackoff(), 0),
        )
        try:
            yield RedisCacheRepository(client, settings)
        finally:
            await client.aclose()

    @provide(scope=Scope.APP)
    async def engine(
        self,
        settings: DatabaseSettings,
    ) -> AsyncIterator[AsyncEngine]:
        engine = create_engine(settings)

        try:
            yield engine
        finally:
            await engine.dispose()

    @provide(scope=Scope.APP)
    def sessions(
        self,
        engine: AsyncEngine,
        cache: CacheRepository,
    ) -> async_sessionmaker[AsyncSession]:
        return async_sessionmaker(
            engine, expire_on_commit=False, info={"cache_repository": cache}
        )

    @provide(scope=Scope.REQUEST)
    async def session(
        self,
        factory: async_sessionmaker[AsyncSession],
    ) -> AsyncIterator[AsyncSession]:
        async with transaction(factory) as session:
            yield session

    @provide(scope=Scope.APP)
    async def http(
        self,
    ) -> AsyncIterator[httpx.AsyncClient]:
        async with httpx.AsyncClient(timeout=5, follow_redirects=False) as client:
            yield client
