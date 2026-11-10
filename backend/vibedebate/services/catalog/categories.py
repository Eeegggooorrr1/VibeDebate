from dataclasses import dataclass
from vibedebate.repositories.catalog import CategoryRepository
from vibedebate.schemas.responses.catalog import CategoryResponse
from vibedebate.schemas.responses.catalog import TopicResponse, PersonaResponse
from uuid import UUID


@dataclass
class CategoryService:
    category_repository: CategoryRepository

    async def list_topics(
        self,
        category_id: UUID | None,
        limit: int,
        offset: int,
    ) -> list[TopicResponse]:
        return [
            TopicResponse.model_validate(t)
            for t in await self.category_repository.list_topics(
                category_id, limit, offset
            )
        ]

    async def list_personas(
        self,
    ) -> list[PersonaResponse]:
        return [
            PersonaResponse.model_validate(p)
            for p in await self.category_repository.list_personas()
        ]

    async def list_active_categories(
        self,
    ) -> list[CategoryResponse]:
        return [
            CategoryResponse.model_validate(category)
            for category in await self.category_repository.list_active_categories()
        ]
