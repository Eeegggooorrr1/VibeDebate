from collections.abc import AsyncIterator
import httpx
from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from vibedebate.core.config import DatabaseSettings
from vibedebate.core.db import create_engine, transaction


class InfrastructureProvider(Provider):
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
    ) -> async_sessionmaker[AsyncSession]:
        return async_sessionmaker(engine, expire_on_commit=False)

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
