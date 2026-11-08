from dataclasses import dataclass
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from vibedebate.models.catalog import TopicCategory


@dataclass
class CategoryRepository:
    session: AsyncSession

    async def list_active_categories(self) -> list[TopicCategory]:
        return list(
            await self.session.scalars(
                select(TopicCategory)
                .where(TopicCategory.is_active.is_(True))
                .order_by(TopicCategory.slug)
            )
        )

    async def are_categories_active(self, category_ids: list[UUID]) -> bool:
        active_ids = await self.session.scalars(
            select(TopicCategory.id).where(
                TopicCategory.id.in_(category_ids), TopicCategory.is_active.is_(True)
            )
        )
        return set(active_ids) == set(category_ids)
