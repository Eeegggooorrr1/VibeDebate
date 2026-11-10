from vibedebate.models.enums import ChatSide
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID
from typing import TypeVar
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from vibedebate.core.exceptions import (
    NotFoundError,
    ConflictError,
    UnprocessableEntityError,
)
from vibedebate.models.catalog import Topic, TopicCategory, OpponentPersona
from vibedebate.models.debate import Debate, DebateChat, ChatMessage
from vibedebate.schemas.responses.debate import MessageResponse
from vibedebate.models.base import Base

EntityType = TypeVar("EntityType", bound=Base)


@dataclass
class DebateRepository:
    session: AsyncSession

    async def topic(
        self,
        topic_id: UUID,
    ) -> Topic:
        topic = await self.session.scalar(
            select(Topic)
            .join(TopicCategory)
            .where(
                Topic.id == topic_id,
                Topic.is_active.is_(True),
                TopicCategory.is_active.is_(True),
            )
        )

        if topic is None:
            raise UnprocessableEntityError(
                "Topic is unavailable", code="topic_unavailable"
            )

        return topic

    async def persona(
        self,
        persona_id: UUID | None,
        difficulty: int,
    ) -> OpponentPersona:
        query = select(OpponentPersona).where(OpponentPersona.is_active.is_(True))
        query = (
            query.where(OpponentPersona.id == persona_id)
            if persona_id
            else query.where(OpponentPersona.key == "socratic")
        )
        persona = await self.session.scalar(query)

        if persona is None or difficulty not in persona.available_difficulties:
            raise UnprocessableEntityError(
                "Opponent or difficulty unavailable", code="opponent_unavailable"
            )

        return persona

    async def debate(
        self,
        debate_id: UUID,
        user_id: UUID,
    ) -> Debate:
        debate = await self.session.scalar(
            select(Debate).where(Debate.id == debate_id, Debate.user_id == user_id)
        )

        if debate is None:
            raise NotFoundError(code="debate_not_found")

        return debate

    async def chat(
        self,
        chat_id: UUID,
        user_id: UUID,
        *,
        lock: bool = False,
    ) -> DebateChat:
        query = select(DebateChat).where(
            DebateChat.id == chat_id, DebateChat.user_id == user_id
        )

        if lock:
            query = query.with_for_update()

        chat = await self.session.scalar(query)

        if chat is None:
            raise NotFoundError(code="chat_not_found")

        return chat

    async def debates(
        self,
        user_id: UUID,
        limit: int,
        offset: int,
    ) -> list[Debate]:
        return list(
            await self.session.scalars(
                select(Debate)
                .where(Debate.user_id == user_id)
                .order_by(Debate.created_at.desc(), Debate.id)
                .limit(limit)
                .offset(offset)
            )
        )

    async def chats(
        self,
        debate_id: UUID,
    ) -> list[DebateChat]:
        return list(
            await self.session.scalars(
                select(DebateChat)
                .where(DebateChat.debate_id == debate_id)
                .order_by(DebateChat.created_at, DebateChat.id)
            )
        )

    async def messages(
        self,
        chat_id: UUID,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[ChatMessage]:
        query = (
            select(ChatMessage)
            .where(ChatMessage.chat_id == chat_id)
            .order_by(ChatMessage.sequence_no)
            .offset(offset)
        )

        if limit is not None:
            query = query.limit(limit)

        return list(await self.session.scalars(query))

    async def add(
        self,
        entity: EntityType,
    ) -> EntityType:
        self.session.add(entity)
        await self.session.flush()

        return entity

    async def reserve(
        self,
        chat: DebateChat,
        content: str,
        key: str,
    ) -> tuple[ChatMessage, ChatMessage, bool]:
        existing = await self.session.scalar(
            select(ChatMessage).where(
                ChatMessage.chat_id == chat.id, ChatMessage.client_request_id == key
            )
        )

        if existing:
            if existing.content != content:
                raise ConflictError(
                    "Idempotency key was used for another message",
                    code="idempotency_conflict",
                )

            response = await self.session.scalar(
                select(ChatMessage).where(
                    ChatMessage.chat_id == chat.id,
                    ChatMessage.sequence_no == existing.sequence_no + 1,
                )
            )

            return existing, response, True

        busy = await self.session.scalar(
            select(ChatMessage.id).where(
                ChatMessage.chat_id == chat.id,
                ChatMessage.role == "assistant",
                ChatMessage.generation_status.in_(["pending", "generating"]),
            )
        )

        if busy:
            raise ConflictError(
                "A response is already being generated", code="chat_busy"
            )

        return await self._reserve_messages(chat, content, key)

    async def finish(
        self,
        message_id: UUID,
        content: str,
        *,
        failed: bool,
    ) -> MessageResponse:
        message = await self.session.get(ChatMessage, message_id, with_for_update=True)

        message.content = content
        message.generation_status = "failed" if failed else "completed"
        message.completed_at = datetime.now(timezone.utc)
        await self.session.flush()

        return MessageResponse.model_validate(message)

    async def _reserve_messages(
        self,
        chat: DebateChat,
        content: str,
        key: str,
    ) -> tuple[ChatMessage, ChatMessage, bool]:
        last = (
            await self.session.scalar(
                select(ChatMessage.sequence_no)
                .where(ChatMessage.chat_id == chat.id)
                .order_by(ChatMessage.sequence_no.desc())
                .limit(1)
            )
            or 0
        )

        user = await self.add(
            ChatMessage(
                chat_id=chat.id,
                sequence_no=last + 1,
                role="user",
                content=content,
                client_request_id=key,
                generation_status="completed",
                completed_at=datetime.now(timezone.utc),
            )
        )

        response = await self.add(
            ChatMessage(
                chat_id=chat.id,
                sequence_no=last + 2,
                role="assistant",
                content="",
                generation_status="generating",
            )
        )

        chat.status = "active"

        return user, response, False


