from vibedebate.services.debate.exceptions import (
    ChatBusyError,
    ChatNotFoundError,
    DebateNotFoundError,
    IdempotencyConflictError,
    InvalidReplyTargetError,
    MessageChatNotFoundError,
    MessageNotFoundError,
    OpponentUnavailableError,
    TopicUnavailableError,
)
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID
from typing import TypeVar

from sqlalchemy import select, update, exists
from sqlalchemy.ext.asyncio import AsyncSession

from vibedebate.models.catalog import Topic, TopicCategory, OpponentPersona
from vibedebate.models.debate import Debate, DebateChat, ChatMessage
from vibedebate.schemas.responses.debate import MessageResponse
from vibedebate.schemas.internal.progression import ProgressState
from vibedebate.models.base import Base
from vibedebate.models.analysis import MessageAnalysis, AnalysisIssue

EntityType = TypeVar("EntityType", bound=Base)


@dataclass
class DebateRepository:
    session: AsyncSession

    async def archive_debate(self, debate_id: UUID, user_id: UUID) -> None:
        debate = await self.debate(debate_id, user_id)
        debate.status = "archived"
        await self.session.execute(
            update(DebateChat)
            .where(DebateChat.debate_id == debate_id)
            .values(status="archived")
        )

    async def archive_chat(self, chat_id: UUID, user_id: UUID) -> None:
        chat = await self.chat(chat_id, user_id, lock=True)
        chat.status = "archived"

    async def lock_message_chat(self, message_id: UUID) -> DebateChat:
        return await self.session.scalar(
            select(DebateChat)
            .join(ChatMessage)
            .where(ChatMessage.id == message_id)
            .with_for_update(of=DebateChat)
        )

    async def progress_batch(self, chat: DebateChat):
        critical = exists(
            select(AnalysisIssue.id).where(
                AnalysisIssue.analysis_id == MessageAnalysis.id,
                AnalysisIssue.severity == "high",
            )
        )
        return (
            await self.session.execute(
                select(
                    ChatMessage.sequence_no,
                    MessageAnalysis.analysis_status,
                    MessageAnalysis.is_substantive,
                    MessageAnalysis.overall_score,
                    critical,
                )
                .outerjoin(
                    MessageAnalysis, MessageAnalysis.message_id == ChatMessage.id
                )
                .where(
                    ChatMessage.chat_id == chat.id,
                    ChatMessage.role == "user",
                    ChatMessage.sequence_no > chat.progress_sequence,
                )
                .order_by(ChatMessage.sequence_no)
                .limit(64)
            )
        ).all()

    def save_progress(
        self,
        chat: DebateChat,
        state: ProgressState,
        percentage: int,
        sequence: int,
        source: str = "statistics",
    ) -> None:
        chat.scored_answers = state.count
        chat.score_total = state.total
        chat.good_streak = state.streak
        chat.progress = percentage
        chat.progress_sequence = sequence

        if state.mastered and chat.mastered_at is None:
            chat.mastered_at = datetime.now(timezone.utc)
            chat.mastery_source = source

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
            raise TopicUnavailableError()

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
            raise OpponentUnavailableError()

        return persona

    async def debate(
        self,
        debate_id: UUID,
        user_id: UUID,
    ) -> Debate:
        debate = await self.session.scalar(
            select(Debate).where(
                Debate.id == debate_id,
                Debate.user_id == user_id,
                Debate.status != "archived",
            )
        )

        if debate is None:
            raise DebateNotFoundError()

        return debate

    async def chat(
        self,
        chat_id: UUID,
        user_id: UUID,
        *,
        lock: bool = False,
    ) -> DebateChat:
        query = select(DebateChat).where(
            DebateChat.id == chat_id,
            DebateChat.user_id == user_id,
            DebateChat.status != "archived",
            exists(
                select(Debate.id).where(
                    Debate.id == DebateChat.debate_id, Debate.status != "archived"
                )
            ),
        )

        if lock:
            query = query.with_for_update()

        chat = await self.session.scalar(query)

        if chat is None:
            raise ChatNotFoundError()

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
                .where(Debate.user_id == user_id, Debate.status != "archived")
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
                .where(
                    DebateChat.debate_id == debate_id, DebateChat.status != "archived"
                )
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

    async def message(
        self, message_id: UUID, *, user_id: UUID | None = None
    ) -> ChatMessage:
        query = select(ChatMessage).where(ChatMessage.id == message_id)

        if user_id is not None:
            query = query.join(DebateChat).where(
                DebateChat.user_id == user_id,
                DebateChat.status != "archived",
                exists(
                    select(Debate.id).where(
                        Debate.id == DebateChat.debate_id, Debate.status != "archived"
                    )
                ),
            )

        message = await self.session.scalar(query)

        if message is None:
            raise MessageNotFoundError()

        return message

    async def message_chat(self, message_id: UUID) -> DebateChat:
        chat = await self.session.scalar(
            select(DebateChat).join(ChatMessage).where(ChatMessage.id == message_id)
        )

        if chat is None:
            raise MessageChatNotFoundError()

        return chat

    async def completed_history(
        self, chat_id: UUID, through_sequence: int
    ) -> list[ChatMessage]:
        return list(
            await self.session.scalars(
                select(ChatMessage)
                .where(
                    ChatMessage.chat_id == chat_id,
                    ChatMessage.sequence_no <= through_sequence,
                    ChatMessage.generation_status == "completed",
                )
                .order_by(ChatMessage.sequence_no)
            )
        )

    async def previous_assistant_message(
        self, chat_id: UUID, before_sequence: int
    ) -> ChatMessage | None:
        return await self.session.scalar(
            select(ChatMessage)
            .where(
                ChatMessage.chat_id == chat_id,
                ChatMessage.sequence_no < before_sequence,
                ChatMessage.role == "assistant",
                ChatMessage.generation_status == "completed",
            )
            .order_by(ChatMessage.sequence_no.desc())
            .limit(1)
        )

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
        reply_to_message_id: UUID | None = None,
    ) -> tuple[ChatMessage, ChatMessage, bool]:
        existing = await self.session.scalar(
            select(ChatMessage).where(
                ChatMessage.chat_id == chat.id, ChatMessage.client_request_id == key
            )
        )

        if existing:
            if (
                existing.content != content
                or existing.reply_to_message_id != reply_to_message_id
            ):
                raise IdempotencyConflictError()

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
            raise ChatBusyError()

        reply = None

        if reply_to_message_id is not None:
            reply = await self.session.scalar(
                select(ChatMessage).where(
                    ChatMessage.id == reply_to_message_id,
                    ChatMessage.chat_id == chat.id,
                    ChatMessage.role == "assistant",
                    ChatMessage.generation_status == "completed",
                )
            )

            if reply is None or not reply.content.strip():
                raise InvalidReplyTargetError()

        return await self._reserve_messages(chat, content, key, reply)

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
        reply: ChatMessage | None = None,
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
                reply_to_message_id=reply.id if reply else None,
                reply_to_content=reply.content if reply else None,
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
