from dataclasses import dataclass
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from vibedebate.models.catalog import TopicCategory, Topic, OpponentPersona


@dataclass
class CategoryRepository:
    session: AsyncSession

    async def list_topics(
        self,
        category_id: UUID | None,
        limit: int,
        offset: int,
    ) -> list[Topic]:
        query = (
            select(Topic)
            .join(TopicCategory)
            .where(Topic.is_active.is_(True), TopicCategory.is_active.is_(True))
        )

        if category_id is not None:
            query = query.where(Topic.category_id == category_id)

        return list(
            await self.session.scalars(
                query.order_by(Topic.title, Topic.id).limit(limit).offset(offset)
            )
        )

    async def list_personas(
        self,
    ) -> list[OpponentPersona]:
        return list(
            await self.session.scalars(
                select(OpponentPersona)
                .where(OpponentPersona.is_active.is_(True))
                .order_by(OpponentPersona.key)
            )
        )

    async def list_active_categories(
        self,
    ) -> list[TopicCategory]:
        return list(
            await self.session.scalars(
                select(TopicCategory)
                .where(TopicCategory.is_active.is_(True))
                .order_by(TopicCategory.slug)
            )
        )

    async def are_categories_active(
        self,
        category_ids: list[UUID],
    ) -> bool:
        active_ids = await self.session.scalars(
            select(TopicCategory.id).where(
                TopicCategory.id.in_(category_ids), TopicCategory.is_active.is_(True)
            )
        )

        return set(active_ids) == set(category_ids)
