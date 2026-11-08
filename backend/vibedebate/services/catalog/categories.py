from dataclasses import dataclass
from vibedebate.repositories.catalog import CategoryRepository
from vibedebate.schemas.responses.catalog import CategoryResponse


@dataclass
class CategoryService:
    category_repository: CategoryRepository

    async def list_active_categories(self) -> list[CategoryResponse]:
        return [
            CategoryResponse.model_validate(category)
            for category in await self.category_repository.list_active_categories()
        ]
