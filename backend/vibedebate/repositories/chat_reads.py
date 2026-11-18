"""Read repositories return detached DTOs, never cached ORM instances."""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from pydantic import TypeAdapter, ValidationError

from vibedebate.models.analysis import MessageAnalysis, AnalysisIssue
from vibedebate.models.debate import ChatMessage
from vibedebate.repositories.debate import DebateRepository
from vibedebate.repositories.cached import ReadCache, cached_read
from vibedebate.repositories.cache import CacheWrite
from vibedebate.schemas.responses.debate import (
    DebateResponse,
    DebateDetail,
    ChatResponse,
    MessageResponse,
    MessageAnalysisResponse,
)
from vibedebate.services.debate.exceptions import MessageNotAnalyzableError


def analysis_response(message_id, analysis, issues) -> MessageAnalysisResponse:
    return MessageAnalysisResponse(
        message_id=message_id,
        status=analysis.analysis_status if analysis else "pending",
        is_substantive=analysis.is_substantive if analysis else None,
        overall_score=analysis.overall_score if analysis else None,
        confidence=analysis.confidence if analysis else None,
        dimensions=list(analysis.dimensions.values()) if analysis else [],
        strengths=analysis.strengths if analysis else [],
        conduct_flags=analysis.conduct_flags if analysis else [],
        next_step=analysis.next_step if analysis else None,
        issues=[
            dict(
                type=i.issue_type,
                severity=i.severity,
                evidence_quote=i.evidence_quote,
                explanation=i.explanation,
                improvement=i.improvement,
                confidence=float(i.confidence),
            )
            for i in issues
        ],
    )


class ChatReadRepository(Protocol):
    async def access_chat(self, user_id: UUID, chat_id: UUID) -> None: ...
    async def access_debate(self, user_id: UUID, debate_id: UUID) -> None: ...
    async def access_message(self, user_id: UUID, message_id: UUID) -> None: ...
    async def debates(
        self, user_id: UUID, limit: int, offset: int
    ) -> list[DebateResponse]: ...
    async def detail(self, user_id: UUID, debate_id: UUID) -> DebateDetail: ...
    async def chat(self, user_id: UUID, chat_id: UUID) -> ChatResponse: ...
    async def messages(
        self,
        user_id: UUID,
        chat_id: UUID,
        limit: int,
        offset: int,
        after_sequence: int = 0,
    ) -> list[MessageResponse]: ...
    async def completed_tail(self, chat_id: UUID) -> list[MessageResponse]: ...
    async def completed_before(
        self, chat_id: UUID, before_sequence: int
    ) -> list[MessageResponse]: ...
    async def analysis(
        self, user_id: UUID, message_id: UUID
    ) -> MessageAnalysisResponse: ...
    async def analysis_batch(
        self, message_ids: list[UUID]
    ) -> list[MessageAnalysisResponse]: ...
    async def analyzable_ids(
        self, user_id: UUID, chat_id: UUID, ids: list[UUID]
    ) -> None: ...


@dataclass
class PostgresChatReadRepository:
    factory: async_sessionmaker[AsyncSession]

    async def access_chat(self, user_id: UUID, chat_id: UUID):
        async with self.factory() as session:
            await DebateRepository(session).check_chat_access(chat_id, user_id)

    async def access_debate(self, user_id: UUID, debate_id: UUID):
        async with self.factory() as session:
            await DebateRepository(session).check_debate_access(debate_id, user_id)

    async def access_message(self, user_id: UUID, message_id: UUID):
        async with self.factory() as session:
            await DebateRepository(session).check_analysis_access(message_id, user_id)

    async def debates(self, user_id: UUID, limit: int, offset: int):
        async with self.factory() as session:
            return [
                DebateResponse.model_validate(d)
                for d in await DebateRepository(session).debates(user_id, limit, offset)
            ]

    async def detail(self, user_id: UUID, debate_id: UUID):
        async with self.factory() as session:
            repo = DebateRepository(session)
            debate = await repo.debate(debate_id, user_id)
            return DebateDetail(
                **DebateResponse.model_validate(debate).model_dump(),
                chats=[
                    ChatResponse.model_validate(c) for c in await repo.chats(debate_id)
                ],
            )

    async def chat(self, user_id: UUID, chat_id: UUID):
        async with self.factory() as session:
            return ChatResponse.model_validate(
                await DebateRepository(session).chat(chat_id, user_id)
            )

    async def messages(
        self,
        user_id: UUID,
        chat_id: UUID,
        limit: int,
        offset: int,
        after_sequence: int = 0,
    ):
        await self.access_chat(user_id, chat_id)
        async with self.factory() as session:
            rows = await DebateRepository(session).messages(
                chat_id, limit, offset, after_sequence=after_sequence
            )
            return [MessageResponse.model_validate(m) for m in rows]

    async def completed_tail(self, chat_id: UUID):
        async with self.factory() as session:
            rows = await session.scalars(
                select(ChatMessage)
                .where(
                    ChatMessage.chat_id == chat_id,
                    ChatMessage.generation_status == "completed",
                )
                .order_by(ChatMessage.sequence_no.desc())
                .limit(100)
            )
            return list(reversed([MessageResponse.model_validate(m) for m in rows]))

    async def completed_before(self, chat_id: UUID, before_sequence: int):
        async with self.factory() as session:
            rows = await DebateRepository(session).completed_history(
                chat_id, before_sequence - 1
            )
            return [MessageResponse.model_validate(m) for m in rows]

    async def analysis(self, user_id: UUID, message_id: UUID):
        await self.access_message(user_id, message_id)
        return (await self.analysis_batch([message_id]))[0]

    async def analysis_batch(self, message_ids: list[UUID]):
        if not message_ids:
            return []

        async with self.factory() as session:
            rows = (
                await session.execute(
                    select(MessageAnalysis, AnalysisIssue)
                    .outerjoin(
                        AnalysisIssue, AnalysisIssue.analysis_id == MessageAnalysis.id
                    )
                    .where(MessageAnalysis.message_id.in_(message_ids))
                    .order_by(AnalysisIssue.created_at, AnalysisIssue.id)
                )
            ).all()
            analyses, issues = {}, {}
            for analysis, issue in rows:
                analyses[analysis.message_id] = analysis
                if issue:
                    issues.setdefault(analysis.message_id, []).append(issue)
            return [
                analysis_response(mid, analyses.get(mid), issues.get(mid, []))
                for mid in message_ids
            ]

    async def analyzable_ids(self, user_id: UUID, chat_id: UUID, ids: list[UUID]):
        await self.access_chat(user_id, chat_id)
        async with self.factory() as session:
            found = set(
                await session.scalars(
                    select(ChatMessage.id).where(
                        ChatMessage.chat_id == chat_id,
                        ChatMessage.id.in_(ids),
                        ChatMessage.role == "user",
                        ChatMessage.generation_status == "completed",
                    )
                )
            )
            if found != set(ids):
                raise MessageNotAnalyzableError()


@dataclass
class CachedChatReadRepository:
    source: ChatReadRepository
    cache: ReadCache

    async def access_chat(self, user_id: UUID, chat_id: UUID) -> None:
        await self.source.access_chat(user_id, chat_id)

    async def access_debate(self, user_id: UUID, debate_id: UUID) -> None:
        await self.source.access_debate(user_id, debate_id)

    async def access_message(self, user_id: UUID, message_id: UUID) -> None:
        await self.source.access_message(user_id, message_id)

    async def completed_before(
        self, chat_id: UUID, before_sequence: int
    ) -> list[MessageResponse]:
        return await self.source.completed_before(chat_id, before_sequence)

    async def analyzable_ids(
        self, user_id: UUID, chat_id: UUID, ids: list[UUID]
    ) -> None:
        await self.source.analyzable_ids(user_id, chat_id, ids)

    @cached_read(
        list[DebateResponse],
        key=lambda uid, limit, offset: f"debates:{uid}:{limit}:{offset}",
        tags=lambda uid, *args: [f"debates:{uid}"],
        ttl="cache_view_ttl",
    )
    async def debates(self, user_id, limit, offset):
        return await self.source.debates(user_id, limit, offset)

    async def detail(self, user_id, debate_id):
        await self.source.access_debate(user_id, debate_id)
        return await self._detail(user_id, debate_id)

    @cached_read(
        DebateDetail,
        key=lambda uid, did: f"debate:{uid}:{did}",
        tags=lambda uid, did: [f"debate:{did}"],
        ttl="cache_view_ttl",
    )
    async def _detail(self, user_id, debate_id):
        return await self.source.detail(user_id, debate_id)

    async def chat(self, user_id, chat_id):
        await self.source.access_chat(user_id, chat_id)
        return await self._chat(user_id, chat_id)

    @cached_read(
        ChatResponse,
        key=lambda uid, cid: f"chat:{uid}:{cid}",
        tags=lambda uid, cid: [f"chat:{cid}"],
        ttl="cache_view_ttl",
    )
    async def _chat(self, user_id, chat_id):
        return await self.source.chat(user_id, chat_id)

    async def messages(self, user_id, chat_id, limit, offset, after_sequence=0):
        await self.source.access_chat(user_id, chat_id)
        return await self._messages(user_id, chat_id, limit, offset, after_sequence)

    @cached_read(
        list[MessageResponse],
        key=lambda uid, cid, limit, offset, after: f"messages:{uid}:{cid}:{limit}:{offset}:{after}",
        tags=lambda uid, cid, *args: [f"messages:{cid}"],
        ttl=lambda settings, rows: (
            settings.cache_status_ttl
            if any(m.generation_status in ("pending", "generating") for m in rows)
            else settings.cache_history_ttl
        ),
    )
    async def _messages(self, user_id, chat_id, limit, offset, after_sequence):
        return await self.source.messages(
            user_id, chat_id, limit, offset, after_sequence
        )

    @cached_read(
        list[MessageResponse],
        key=lambda cid: f"tail:{cid}",
        tags=lambda cid: [f"messages:{cid}"],
        ttl="cache_history_ttl",
    )
    async def completed_tail(self, chat_id):
        return await self.source.completed_tail(chat_id)

    async def analysis(self, user_id, message_id):
        await self.source.access_message(user_id, message_id)
        return (await self.analysis_batch([message_id]))[0]

    async def analysis_batch(self, message_ids):
        # One generation lookup and one MGET for the entire batch, not N Redis trips.
        adapter = TypeAdapter(MessageAnalysisResponse)
        tags = [f"analysis:{mid}" for mid in message_ids]
        if not tags:
            return []
        generations = await self.cache.repository.generations(tags)
        if generations is None:
            return await self.source.analysis_batch(message_ids)

        keys = [f"analysis:{mid}:{gen}" for mid, gen in zip(message_ids, generations)]
        values = await self.cache.repository.get_many(keys)
        results, missing = {}, []
        for mid, value in zip(message_ids, values):
            try:
                results[mid] = adapter.validate_json(value) if value else None
            except ValidationError:
                results[mid] = None
            if results[mid] is None:
                missing.append(mid)

        if missing:
            writes = []
            positions = {mid: index for index, mid in enumerate(message_ids)}
            for result in await self.source.analysis_batch(missing):
                mid = result.message_id
                index = positions[mid]
                results[mid] = result
                ttl = (
                    self.cache.settings.cache_analysis_ttl
                    if result.status == "completed"
                    else self.cache.settings.cache_status_ttl
                )
                writes.append(
                    CacheWrite(
                        keys[index],
                        adapter.dump_json(result),
                        ttl,
                        [tags[index]],
                        [generations[index]],
                    )
                )
            await self.cache.repository.put_many(writes)
        return [results[mid] for mid in message_ids]
