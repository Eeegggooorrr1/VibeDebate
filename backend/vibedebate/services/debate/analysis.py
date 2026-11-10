from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from vibedebate.ai.analysis import MessageAnalyzer, AnalysisResult, AnalysisResult
from vibedebate.ai.contracts import AIMessage
from vibedebate.ai.usage import usage_scope
from vibedebate.core.db import transaction
from vibedebate.core.exceptions import NotFoundError, UnprocessableEntityError
from vibedebate.models.analysis import MessageAnalysis, AnalysisIssue
from vibedebate.models.debate import ChatMessage, DebateChat, Debate
from vibedebate.repositories.debate import DebateRepository

logger = logging.getLogger(__name__)


class AnalysisService:
    def __init__(
        self,
        factory: async_sessionmaker[AsyncSession],
        analyzer: MessageAnalyzer,
    ):
        self.factory, self.analyzer = factory, analyzer
        self.tasks: dict[UUID, asyncio.Task] = {}

    def start(
        self,
        message_id: UUID,
    ):
        if message_id not in self.tasks:
            task = asyncio.create_task(self._run(message_id))
            self.tasks[message_id] = task
            task.add_done_callback(lambda _: self.tasks.pop(message_id, None))

    async def close(
        self,
    ):
        tasks = list(self.tasks.values())

        for task in tasks:
            task.cancel()

        await asyncio.gather(*tasks, return_exceptions=True)

    async def get(
        self,
        user_id: UUID,
        message_id: UUID,
        *,
        retry=False,
    ):
        async with transaction(self.factory) as session:
            message = await session.scalar(
                select(ChatMessage)
                .join(DebateChat)
                .where(
                    ChatMessage.id == message_id,
                    DebateChat.user_id == user_id,
                )
            )

            if message is None:
                raise NotFoundError()

            if message.role != "user" or message.generation_status != "completed":
                raise UnprocessableEntityError(code="message_not_analyzable")

            await DebateRepository(session).chat(message.chat_id, user_id, lock=True)

            analysis = await session.scalar(
                select(MessageAnalysis)
                .where(MessageAnalysis.message_id == message_id)
                .with_for_update()
            )

            if analysis is None:
                analysis = MessageAnalysis(
                    message_id=message_id, analysis_status="pending"
                )
                session.add(analysis)
                await session.flush()

            self._reset_analysis(analysis, retry)
            issues = (
                await session.scalars(
                    select(AnalysisIssue)
                    .where(AnalysisIssue.analysis_id == analysis.id)
                    .order_by(AnalysisIssue.created_at, AnalysisIssue.id)
                )
            ).all()

            result = self._analysis_response(message_id, analysis, issues)

        if result["status"] == "pending":
            self.start(message_id)

        return result

    async def _run(
        self,
        message_id,
    ):
        analysis_id = None

        try:
            async with transaction(self.factory) as session:
                analysis_id = await session.scalar(
                    update(MessageAnalysis)
                    .where(
                        MessageAnalysis.message_id == message_id,
                        MessageAnalysis.analysis_status == "pending",
                    )
                    .values(
                        analysis_status="running", started_at=datetime.now(timezone.utc)
                    )
                    .returning(MessageAnalysis.id)
                )

                if analysis_id is None:
                    return

                messages, owner, debate_id, chat_id = await self._analysis_context(session, message_id)

            with usage_scope(
                owner,
                "message_analysis",
                debate_id=debate_id,
                chat_id=chat_id,
                message_id=message_id,
            ):
                result = await self.analyzer.analyze(messages)

            await self._save_analysis(analysis_id, message_id, result)
        except (Exception, asyncio.CancelledError) as exc:
            if not isinstance(exc, asyncio.CancelledError):
                logger.warning("Message analysis failed: %s", type(exc).__name__)

            if analysis_id:
                await asyncio.shield(self._failed(analysis_id))

    async def _failed(
        self,
        analysis_id,
    ):
        async with transaction(self.factory) as session:
            await session.execute(
                update(MessageAnalysis)
                .where(
                    MessageAnalysis.id == analysis_id,
                    MessageAnalysis.analysis_status == "running",
                )
                .values(
                    analysis_status="failed", completed_at=datetime.now(timezone.utc)
                )
            )

    @staticmethod
    def _analysis_response(
        message_id: UUID,
        analysis: MessageAnalysis,
        issues: list[AnalysisIssue],
    ) -> dict:
        result = dict(
            message_id=message_id,
            status=analysis.analysis_status,
            is_substantive=analysis.is_substantive,
            overall_score=(
                float(analysis.overall_score)
                if analysis.overall_score is not None
                else None
            ),
            confidence=(
                float(analysis.confidence)
                if analysis.confidence is not None
                else None
            ),
            dimensions=list(analysis.dimensions.values()),
            strengths=analysis.strengths,
            conduct_flags=analysis.conduct_flags,
            next_step=analysis.next_step,
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

        return result

    @staticmethod
    def _reset_analysis(
        analysis: MessageAnalysis,
        retry: bool,
    ) -> None:
        if (
            analysis.analysis_status == "running"
            and analysis.started_at
            and analysis.started_at
            < datetime.now(timezone.utc) - timedelta(minutes=10)
        ):
            analysis.analysis_status = "failed"

        if retry and analysis.analysis_status == "failed":
            analysis.analysis_status, analysis.completed_at = "pending", None

    async def _analysis_context(
        self,
        session: AsyncSession,
        message_id: UUID,
    ) -> tuple[list[AIMessage], UUID, UUID, UUID]:
        message = await session.get(ChatMessage, message_id)

        chat = await session.get(DebateChat, message.chat_id)

        debate = await session.get(Debate, chat.debate_id)

        history = (
            await session.scalars(
                select(ChatMessage)
                .where(
                    ChatMessage.chat_id == chat.id,
                    ChatMessage.sequence_no <= message.sequence_no,
                    ChatMessage.generation_status == "completed",
                )
                .order_by(ChatMessage.sequence_no)
            )
        ).all()

        messages = [
            AIMessage(
                role="system",
                content=(
                    f"Тема: {debate.topic_title}\nОбщая позиция пользователя в дебатах (не обязательно его текущий тезис): {debate.user_position}\n"
                    f"Направление: {chat.side}\nТезис оппонента в Defense: {chat.seed_claim if chat.side == 'defense' else 'нет'}"
                ),
            )
        ] + [AIMessage(role=m.role, content=m.content) for m in history]
        owner, debate_id, chat_id = chat.user_id, chat.debate_id, chat.id

        return messages, owner, debate_id, chat_id

    async def _save_analysis(
        self,
        analysis_id: UUID,
        message_id: UUID,
        result: AnalysisResult,
    ) -> None:
        async with transaction(self.factory) as session:
            analysis = await session.get(
                MessageAnalysis, analysis_id, with_for_update=True
            )

            if analysis is None or analysis.analysis_status != "running":
                return

            analysis.is_substantive, analysis.overall_score = (
                result.is_substantive,
                result.overall_score,
            )
            analysis.confidence = result.confidence
            analysis.dimensions = {d.key: d.model_dump() for d in result.dimensions}
            analysis.strengths, analysis.conduct_flags = (
                result.strengths,
                result.conduct_flags,
            )
            analysis.next_step = result.next_step
            analysis.analysis_status, analysis.completed_at = (
                "completed",
                datetime.now(timezone.utc),
            )
            await session.execute(
                delete(AnalysisIssue).where(
                    AnalysisIssue.analysis_id == analysis_id
                )
            )

            for issue in result.issues:
                session.add(
                    AnalysisIssue(
                        analysis_id=analysis_id,
                        issue_type=issue.type,
                        **issue.model_dump(exclude={"type"}),
                    )
                )

            await session.execute(
                update(ChatMessage)
                .where(ChatMessage.id == message_id)
                .values(is_substantive=result.is_substantive)
            )

