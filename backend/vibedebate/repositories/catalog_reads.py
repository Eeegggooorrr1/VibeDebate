from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from vibedebate.repositories.catalog import CategoryRepository
from vibedebate.repositories.cached import ReadCache, cached_read
from vibedebate.schemas.responses.catalog import (
    CategoryResponse,
    TopicResponse,
    PersonaResponse,
)
from vibedebate.schemas.internal.catalog import PersonaConfiguration
from vibedebate.repositories.debate import DebateRepository


class CatalogReadRepository(Protocol):
    async def persona(
        self, persona_id: UUID | None, difficulty: int
    ) -> PersonaConfiguration: ...
    async def topics(
        self, category_id: UUID | None, limit: int, offset: int
    ) -> list[TopicResponse]: ...
    async def personas(self) -> list[PersonaResponse]: ...
    async def categories(self) -> list[CategoryResponse]: ...


@dataclass
class PostgresCatalogReadRepository:
    factory: async_sessionmaker[AsyncSession]

    async def persona(self, persona_id, difficulty):
        async with self.factory() as session:
            return PersonaConfiguration.model_validate(
                await DebateRepository(session).persona(persona_id, difficulty)
            )

    async def topics(self, category_id, limit, offset):
        async with self.factory() as session:
            return [
                TopicResponse.model_validate(row)
                for row in await CategoryRepository(session).list_topics(
                    category_id, limit, offset
                )
            ]

    async def personas(self):
        async with self.factory() as session:
            return [
                PersonaResponse.model_validate(row)
                for row in await CategoryRepository(session).list_personas()
            ]

    async def categories(self):
        async with self.factory() as session:
            return [
                CategoryResponse.model_validate(row)
                for row in await CategoryRepository(session).list_active_categories()
            ]


@dataclass
class CachedCatalogReadRepository:
    source: CatalogReadRepository
    cache: ReadCache

    @cached_read(
        PersonaConfiguration,
        key=lambda pid, difficulty: f"persona-config:{pid}:{difficulty}",
        tags=lambda *args: ["catalog"],
        ttl="cache_catalog_ttl",
    )
    async def persona(self, persona_id, difficulty):
        return await self.source.persona(persona_id, difficulty)

    @cached_read(
        list[TopicResponse],
        key=lambda cid, limit, offset: f"topics:{cid}:{limit}:{offset}",
        tags=lambda *args: ["catalog"],
        ttl="cache_catalog_ttl",
    )
    async def topics(self, category_id, limit, offset):
        return await self.source.topics(category_id, limit, offset)

    @cached_read(
        list[PersonaResponse],
        key=lambda: "personas",
        tags=lambda: ["catalog"],
        ttl="cache_catalog_ttl",
    )
    async def personas(self):
        return await self.source.personas()

    @cached_read(
        list[CategoryResponse],
        key=lambda: "categories",
        tags=lambda: ["catalog"],
        ttl="cache_catalog_ttl",
    )
    async def categories(self):
        return await self.source.categories()
