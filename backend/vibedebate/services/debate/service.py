from __future__ import annotations
from vibedebate.models.enums import ChatSide
from dataclasses import dataclass
import asyncio
import json
import logging
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from uuid import UUID
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from vibedebate.core.config import AISettings
from vibedebate.core.db import transaction
from vibedebate.core.exceptions import AppError, ConflictError
from vibedebate.models.debate import Debate, DebateChat, ChatMessage
from vibedebate.repositories.debate import DebateRepository
from vibedebate.repositories.user import UserRepository
from vibedebate.schemas.internal.user import CurrentUser
from vibedebate.schemas.internal.debate import PreparedTurn
from vibedebate.schemas.requests.debate import (
    AdvancedDebateCreate,
    ChatCreate,
    MessageCreate,
    SuggestionRequest,
)
from vibedebate.schemas.responses.debate import (
    DebateResponse,
    DebateDetail,
    ChatResponse,
    MessageResponse,
)
from vibedebate.ai.contracts import AIProvider, AIMessage, AIError, AIChunk
from vibedebate.ai.debate import DebateIntelligence, DebatePlan, ChatSeed, check_context
from vibedebate.ai.prompts import opponent_instruction
from vibedebate.ai.usage import usage_scope
from vibedebate.models.analysis import MessageAnalysis
from vibedebate.services.debate.analysis import AnalysisService
from vibedebate.models.enums import UserStatus
from vibedebate.services.user.exceptions import UserDeletedError

logger = logging.getLogger(__name__)


@dataclass
class DebateService:
    factory: async_sessionmaker[AsyncSession]
    intelligence: DebateIntelligence
    provider: AIProvider
    settings: AISettings
    analyses: AnalysisService

    @staticmethod
    async def _user(
        session: AsyncSession,
        current: CurrentUser,
    ) -> UUID:
        user = await UserRepository(session).get_or_create_user(
            current.subject, current.display_name
        )

        if user.status == UserStatus.DELETED:
            raise UserDeletedError()

        return user.id

    @staticmethod
    def _context(
        debate: Debate,
    ) -> dict[str, Any]:
        return {
            "topic": debate.topic_title,
            "user_position": debate.user_position,
            "opponent_position": debate.opponent_position,
        }

    async def _add_chat(
        self,
        repo: DebateRepository,
        debate: Debate,
        seed: ChatSeed,
        persona_id: UUID,
        difficulty: int,
        side: str,
        attack_hint: str | None = None,
    ) -> DebateChat:
        chat = await repo.add(
            DebateChat(
                debate_id=debate.id,
                user_id=debate.user_id,
                side=side,
                attack_hint=attack_hint,
                user_role="attacker" if side == ChatSide.ATTACK else "defender",
                opponent_persona_id=persona_id,
                difficulty=difficulty,
                status="new",
                **seed.model_dump(),
            )
        )

        if side == ChatSide.DEFENSE:
            await repo.add(
                ChatMessage(
                    chat_id=chat.id,
                    sequence_no=1,
                    role="assistant",
                    content=seed.seed_claim,
                    generation_status="completed",
                    completed_at=datetime.now(timezone.utc),
                )
            )

        return chat

    async def create(
        self,
        current: CurrentUser,
        request: AdvancedDebateCreate,
    ) -> DebateDetail:
        async with transaction(self.factory) as session:
            user_id = await self._user(session, current)

            repo = DebateRepository(session)
            topic = await repo.topic(request.topic_id) if request.topic_id else None

            title = topic.title if topic else request.custom_topic
            description = topic.description if topic else ""
            persona = await repo.persona(
                request.opponent_persona_id, request.difficulty
            )

            persona_id = persona.id

        with usage_scope(user_id, "debate_plan"):
            plan, _ = await self.intelligence.plan(
                {
                    "topic": title,
                    "description": description,
                    "user_position": request.user_position,
                }
            )

        async with transaction(self.factory) as session:
            repo = DebateRepository(session)

            return await self._save_debate(repo, request, user_id, persona_id, title, plan)

    async def list(
        self,
        current: CurrentUser,
        limit: int,
        offset: int,
    ) -> list[DebateResponse]:
        async with transaction(self.factory) as session:
            repo = DebateRepository(session)
            user_id = await self._user(session, current)

            return [
                DebateResponse.model_validate(d)
                for d in await repo.debates(user_id, limit, offset)
            ]

    async def detail(
        self,
        current: CurrentUser,
        debate_id: UUID,
    ) -> DebateDetail:
        async with transaction(self.factory) as session:
            repo = DebateRepository(session)
            debate = await repo.debate(debate_id, await self._user(session, current))

            return DebateDetail(
                **DebateResponse.model_validate(debate).model_dump(),
                chats=[
                    ChatResponse.model_validate(c) for c in await repo.chats(debate.id)
                ],
            )

    async def create_chat(
        self,
        current: CurrentUser,
        debate_id: UUID,
        request: ChatCreate,
    ) -> ChatResponse:
        async with transaction(self.factory) as session:
            repo = DebateRepository(session)
            debate = await repo.debate(debate_id, await self._user(session, current))

            if debate.status != "active":
                raise ConflictError(code="debate_inactive")

            persona = await repo.persona(
                request.opponent_persona_id, request.difficulty
            )

            persona_id = persona.id
            context = self._context(debate) | {
                "title": request.title,
                "description": request.description,
                "side": request.side,
                "persona": persona.base_prompt_config,
                "difficulty": request.difficulty,
                "existing_topics": [
                    {"title": c.title, "seed_claim": c.seed_claim}
                    for c in await repo.chats(debate.id)
                ],
            }

        seed = await self._chat_seed(request, debate, context)

        async with transaction(self.factory) as session:
            repo = DebateRepository(session)
            return await self._save_chat(repo, debate_id, debate.user_id, persona_id, request, seed)

    async def suggest(
        self,
        current: CurrentUser,
        debate_id: UUID,
        request: SuggestionRequest,
    ):
        async with transaction(self.factory) as session:
            repo = DebateRepository(session)
            debate = await repo.debate(debate_id, await self._user(session, current))

            if debate.status != "active":
                raise ConflictError(code="debate_inactive")

            persona = await repo.persona(
                request.opponent_persona_id, request.difficulty
            )

            context = self._context(debate) | {
                "side": request.side,
                "direction": request.title,
                "persona": persona.base_prompt_config,
                "difficulty": request.difficulty,
                "existing_topics": [c.title for c in await repo.chats(debate_id)],
                "previous_titles": request.previous_titles,
            }

        with usage_scope(debate.user_id, "chat_suggestion", debate_id=debate_id):
            suggestion, _ = await self.intelligence.suggest(context)

        return suggestion

    async def analysis(
        self,
        current: CurrentUser,
        message_id: UUID,
        *,
        retry=False,
    ):
        async with transaction(self.factory) as session:
            user_id = await self._user(session, current)

        return await self.analyses.get(user_id, message_id, retry=retry)

    async def chat(
        self,
        current: CurrentUser,
        chat_id: UUID,
    ) -> ChatResponse:
        async with transaction(self.factory) as session:
            chat = await DebateRepository(session).chat(
                chat_id, await self._user(session, current)
            )

            return ChatResponse.model_validate(chat)

    async def messages(
        self,
        current: CurrentUser,
        chat_id: UUID,
        limit: int,
        offset: int,
    ) -> list[MessageResponse]:
        async with transaction(self.factory) as session:
            repo = DebateRepository(session)
            await repo.chat(chat_id, await self._user(session, current))

            return [
                MessageResponse.model_validate(m)
                for m in await repo.messages(chat_id, limit, offset)
            ]

    async def prepare_turn(
        self,
        current: CurrentUser,
        chat_id: UUID,
        request: MessageCreate,
        key: str,
    ) -> PreparedTurn:
        async with transaction(self.factory) as session:
            repo = DebateRepository(session)
            chat = await repo.chat(
                chat_id, await self._user(session, current), lock=True
            )

            debate = await repo.debate(chat.debate_id, chat.user_id)

            if debate.status != "active" or chat.status not in (
                "new",
                "active",
                "mastery_suggested",
            ):
                raise ConflictError(code="chat_inactive")

            user, response, replay = await repo.reserve(chat, request.content, key)

            snapshot = PreparedTurn(
                user=MessageResponse.model_validate(user),
                response=MessageResponse.model_validate(response),
                replay=replay,
                user_id=chat.user_id,
                debate_id=debate.id,
            )

            if replay:
                return snapshot

            session.add(MessageAnalysis(message_id=user.id, analysis_status="pending"))

            return await self._complete_turn_context(repo, chat, debate, snapshot, request)

    async def _finish(
        self,
        snapshot: PreparedTurn,
        text: str,
        failed: bool,
        seed: ChatSeed | None = None,
    ) -> MessageResponse:
        async with transaction(self.factory) as session:
            repo = DebateRepository(session)
            result = await repo.finish(snapshot.response.id, text, failed=failed)

            if seed is not None:
                chat = await repo.chat(snapshot.user.chat_id, snapshot.user_id)

                chat.title, chat.description, chat.seed_claim = (
                    seed.title,
                    seed.description,
                    seed.seed_claim,
                )

            return result

    async def _prepare_attack_seed(
        self,
        snapshot: PreparedTurn,
    ) -> ChatSeed | None:
        if not snapshot.first_attack:
            return None

        with usage_scope(
            snapshot.user_id,
            "attack_seed",
            debate_id=snapshot.debate_id,
            chat_id=snapshot.user.chat_id,
            message_id=snapshot.user.id,
        ):
            seed, _ = await self.intelligence.seed(snapshot.context)

        snapshot.messages[0] = opponent_instruction(
            snapshot.context | {"seed_claim": seed.seed_claim}
        )
        check_context(snapshot.messages, self.settings)

        return seed

    async def stream_turn(
        self,
        snapshot: PreparedTurn,
    ) -> AsyncIterator[str]:
        if snapshot.replay:
            yield self._started_event(snapshot)
            yield self._event("message_status", snapshot.response.model_dump(mode="json"))

            return

        self.analyses.start(snapshot.user.id)
        text, completed, persisted = "", False, False
        seed = None

        try:
            yield self._started_event(snapshot)
            seed = await self._prepare_attack_seed(snapshot)

            async for chunk in self._reply_chunks(snapshot):
                if chunk.delta:
                    text += chunk.delta
                    yield self._event("delta", {"content": chunk.delta})

                if chunk.finished:
                    completed = True

            if not completed or not text.strip():
                raise AIError("Incomplete AI response", code="ai_invalid_response")

            response = await self._finish(snapshot, text, False, seed)

            persisted = True
            yield self._event("message_completed", response.model_dump(mode="json"))
        except Exception as exc:
            await self._finish(snapshot, text, True, seed)

            persisted = True
            yield self._error_event(snapshot, exc)
        finally:
            if not persisted:
                await asyncio.shield(self._finish(snapshot, text, True, seed))

    async def _complete_turn_context(
        self,
        repo: DebateRepository,
        chat: DebateChat,
        debate: Debate,
        snapshot: PreparedTurn,
        request: MessageCreate,
    ) -> PreparedTurn:
        persona = await repo.persona(chat.opponent_persona_id, chat.difficulty)

        context = self._context(debate) | {
            "side": chat.side,
            "seed_claim": chat.seed_claim,
            "difficulty": chat.difficulty,
            "persona": persona.base_prompt_config,
        }

        if chat.side == ChatSide.DEFENSE:
            context["opponent_position"] = chat.seed_claim
            context["user_position"] = (
                "Локальная позиция пользователя определяется его сообщениями: он проверяет тезис ИИ."
            )

        history = await repo.messages(chat.id)

        messages = [opponent_instruction(context)]
        messages.extend(
            AIMessage(role=m.role, content=m.content)
            for m in history
            if m.id != snapshot.response.id and m.generation_status == "completed"
        )
        check_context(messages, self.settings)
        snapshot.messages = messages
        snapshot.first_attack = (
            chat.side == ChatSide.ATTACK
            and not chat.attack_hint
            and not any(
                m.role == "assistant" and m.generation_status == "completed"
                for m in history
            )
        )
        snapshot.context = context | {"first_argument": request.content}

        return snapshot

    async def _chat_seed(
        self,
        request: ChatCreate,
        debate: Debate,
        context: dict[str, Any],
    ) -> ChatSeed:
        if request.accepted_suggestion:
            seed = ChatSeed(**request.accepted_suggestion.model_dump(exclude={"hint"}))
        elif request.side == ChatSide.DEFENSE:
            with usage_scope(debate.user_id, "defense_seed", debate_id=debate.id):
                seed, _ = await self.intelligence.seed(context)
        else:
            seed = ChatSeed(
                title=request.title or "Новая атака",
                description=request.description or "Аргумент пользователя",
                seed_claim="Начните с аргумента",
            )

        return seed

    async def _save_debate(
        self,
        repo: DebateRepository,
        request: AdvancedDebateCreate,
        user_id: UUID,
        persona_id: UUID,
        title: str,
        plan: DebatePlan,
    ) -> DebateDetail:
        if request.topic_id:
            await repo.topic(request.topic_id)

        await repo.persona(persona_id, request.difficulty)

        debate = await repo.add(
            Debate(
                user_id=user_id,
                mode="advanced",
                topic_id=request.topic_id,
                custom_topic=request.custom_topic,
                topic_title=title,
                user_position=request.user_position,
                opponent_position=plan.opponent_position,
            )
        )

        chats = [
            ChatResponse.model_validate(
                await self._add_chat(
                    repo, debate, seed, persona_id, request.difficulty, ChatSide.DEFENSE
                )
            )
            for seed in plan.chats
        ]

        return DebateDetail(
            **DebateResponse.model_validate(debate).model_dump(), chats=chats
        )

    @staticmethod
    def _event(
        name: str,
        payload: dict,
    ) -> str:
        return f"event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

    def _started_event(
        self,
        snapshot: PreparedTurn,
    ) -> str:
        return self._event(
            "message_started",
            {
                "user_message": snapshot.user.model_dump(mode="json"),
                "response": snapshot.response.model_dump(mode="json"),
                "replayed": snapshot.replay,
            },
        )

    def _error_event(
        self,
        snapshot: PreparedTurn,
        error: Exception,
    ) -> str:
        if not isinstance(error, AppError):
            logger.exception("Debate generation failed")

        return self._event(
            "error",
            {
                "code": error.code if isinstance(error, AppError) else "generation_failed",
                "message": "Response generation failed",
                "message_id": str(snapshot.response.id),
            },
        )

    async def _save_chat(
        self,
        repo: DebateRepository,
        debate_id: UUID,
        user_id: UUID,
        persona_id: UUID,
        request: ChatCreate,
        seed: ChatSeed,
    ) -> ChatResponse:
        debate = await repo.debate(debate_id, user_id)

        if debate.status != "active":
            raise ConflictError(code="debate_inactive")

        await repo.persona(persona_id, request.difficulty)

        chat = await self._add_chat(
            repo,
            debate,
            seed,
            persona_id,
            request.difficulty,
            request.side,
            attack_hint=(
                request.accepted_suggestion.hint
                if request.accepted_suggestion and request.side == ChatSide.ATTACK
                else None
            ),
        )

        return ChatResponse.model_validate(chat)

    async def _reply_chunks(
        self,
        snapshot: PreparedTurn,
    ) -> AsyncIterator[AIChunk]:
        with usage_scope(
            snapshot.user_id,
            "opponent_reply",
            debate_id=snapshot.debate_id,
            chat_id=snapshot.user.chat_id,
            message_id=snapshot.response.id,
        ):
            async for chunk in self.provider.stream(snapshot.messages):
                yield chunk
