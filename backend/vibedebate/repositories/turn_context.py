
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select

from vibedebate.models.debate import ChatMessage
from vibedebate.repositories.cached import ReadCache, cached_read
from vibedebate.repositories.debate import DebateRepository
from vibedebate.schemas.internal.catalog import PersonaConfiguration
from vibedebate.schemas.responses.debate import MessageResponse


@dataclass
class TurnContextRepository:
    source: DebateRepository

    async def persona(self, persona_id: UUID, difficulty: int) -> PersonaConfiguration:
        return PersonaConfiguration.model_validate(
            await self.source.persona(persona_id, difficulty)
        )

    async def tail(self, chat_id: UUID, through_sequence: int) -> list[MessageResponse]:
        rows = await self.source.session.scalars(
            select(ChatMessage)
            .where(
                ChatMessage.chat_id == chat_id,
                ChatMessage.sequence_no <= through_sequence,
                ChatMessage.generation_status == "completed",
            )
            .order_by(ChatMessage.sequence_no.desc())
            .limit(100)
        )
        return list(reversed([MessageResponse.model_validate(m) for m in rows]))

    async def history(
        self, chat_id: UUID, through_sequence: int
    ) -> list[MessageResponse]:
        return [
            MessageResponse.model_validate(m)
            for m in await self.source.completed_history(chat_id, through_sequence)
        ]

    async def head(self, chat_id: UUID, through_sequence: int) -> int:
        return await self.source.completed_head(chat_id, through_sequence)


@dataclass
class CachedTurnContextRepository:
    source: TurnContextRepository
    cache: ReadCache

    @cached_read(
        PersonaConfiguration,
        key=lambda pid, difficulty: f"persona-config:{pid}:{difficulty}",
        tags=lambda *args: ["catalog"],
        ttl="cache_catalog_ttl",
    )
    async def persona(self, persona_id: UUID, difficulty: int) -> PersonaConfiguration:
        return await self.source.persona(persona_id, difficulty)

    @cached_read(
        list[MessageResponse],
        key=lambda cid, through: f"tail:{cid}",
        tags=lambda cid, through: [f"messages:{cid}"],
        ttl="cache_history_ttl",
    )
    async def tail(self, chat_id: UUID, through_sequence: int) -> list[MessageResponse]:
        return await self.source.tail(chat_id, through_sequence)

    async def history(
        self, chat_id: UUID, through_sequence: int
    ) -> list[MessageResponse]:
        head = await self.source.head(chat_id, through_sequence)
        cached_tail = await self.tail(chat_id, through_sequence)
        tail = [m for m in cached_tail if m.sequence_no <= through_sequence]
        if (tail[-1].sequence_no if tail else 0) != head:
            return await self.source.history(chat_id, through_sequence)
        if len(cached_tail) == 100 and tail:
            return await self.source.history(chat_id, tail[0].sequence_no - 1) + tail
        return tail


@dataclass
class TurnContextRepositoryFactory:
    cache: ReadCache

    def bind(self, repository: DebateRepository) -> CachedTurnContextRepository:
        return CachedTurnContextRepository(
            TurnContextRepository(repository), self.cache
        )
