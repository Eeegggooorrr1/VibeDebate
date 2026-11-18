from dataclasses import dataclass
from uuid import UUID
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from vibedebate.models.catalog import TopicCategory, Topic, OpponentPersona
from vibedebate.models.debate import DebateChat
from vibedebate.repositories.invalidation import invalidate_on_commit


@dataclass
class CategoryRepository:
    session: AsyncSession

    async def retire_personas(self, keys: list[str]) -> None:
        retired = list(
            await self.session.scalars(
                select(OpponentPersona.id).where(OpponentPersona.key.in_(keys))
            )
        )
        if not retired:
            return
        basic = await self.session.scalar(
            select(OpponentPersona.id).where(OpponentPersona.key == "basic")
        )
        if basic is None:
            raise ValueError("Basic persona must be seeded before retirement")
        rows = (
            await self.session.execute(
                update(DebateChat)
                .where(DebateChat.opponent_persona_id.in_(retired))
                .values(opponent_persona_id=basic)
                .returning(DebateChat.id, DebateChat.debate_id)
            )
        ).all()
        await self.session.execute(
            update(OpponentPersona)
            .where(OpponentPersona.id.in_(retired))
            .values(is_active=False)
        )
        invalidate_on_commit(self.session, "catalog")
        for chat_id, debate_id in rows:
            invalidate_on_commit(self.session, f"chat:{chat_id}", f"debate:{debate_id}")

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
