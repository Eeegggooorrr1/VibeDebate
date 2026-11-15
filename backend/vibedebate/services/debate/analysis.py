from __future__ import annotations
from vibedebate.services.debate.exceptions import MessageNotAnalyzableError

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from vibedebate.ai.analysis import MessageAnalyzer, AnalysisResult
from vibedebate.ai.contracts import AIMessage
from vibedebate.ai.replies import reply_context
from vibedebate.ai.usage import usage_scope
from vibedebate.core.db import transaction
from vibedebate.models.analysis import MessageAnalysis, AnalysisIssue
from vibedebate.repositories.analysis import AnalysisRepository
from vibedebate.repositories.debate import DebateRepository
from vibedebate.services.debate.progression import ChatProgressPolicy, ProgressState

logger = logging.getLogger(__name__)


class AnalysisService:
    def __init__(
        self,
        factory: async_sessionmaker[AsyncSession],
        analyzer: MessageAnalyzer,
        progression: ChatProgressPolicy | None = None,
    ):
        self.factory, self.analyzer = factory, analyzer
        self.progression = progression or ChatProgressPolicy()
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
        retry: bool = False,
    ):
        async with transaction(self.factory) as session:
            debates = DebateRepository(session)
            analyses = AnalysisRepository(session)
            message = await debates.message(message_id, user_id=user_id)

            if message.role != "user" or message.generation_status != "completed":
                raise MessageNotAnalyzableError()

            await debates.chat(message.chat_id, user_id, lock=True)
            analysis = await analyses.get_or_create(message_id)

            self._reset_analysis(analysis, retry)
            issues = await analyses.issues(analysis.id)

            result = self._analysis_response(message_id, analysis, issues)

        if result["status"] == "pending":
            self.start(message_id)

        return result

    async def _run(
        self,
        message_id: UUID,
    ) -> None:
        analysis_id = None

        try:
            async with transaction(self.factory) as session:
                analysis_id = await AnalysisRepository(session).claim(message_id)

                if analysis_id is None:
                    return

                messages, owner, debate_id, chat_id = await self._analysis_context(
                    session, message_id
                )

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
        analysis_id: UUID,
    ) -> None:
        async with transaction(self.factory) as session:
            await AnalysisRepository(session).fail(analysis_id)

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
                float(analysis.confidence) if analysis.confidence is not None else None
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
            and analysis.started_at < datetime.now(timezone.utc) - timedelta(minutes=10)
        ):
            analysis.analysis_status = "failed"

        if retry and analysis.analysis_status == "failed":
            analysis.analysis_status, analysis.completed_at = "pending", None

    async def _analysis_context(
        self,
        session: AsyncSession,
        message_id: UUID,
    ) -> tuple[list[AIMessage], UUID, UUID, UUID]:
        repo = DebateRepository(session)
        message = await repo.message(message_id)
        chat = await repo.message_chat(message_id)
        debate = await repo.debate(chat.debate_id, chat.user_id)
        history = await repo.completed_history(chat.id, message.sequence_no)

        messages = (
            [
                AIMessage(
                    role="system",
                    content=(
                        f"Тема: {debate.topic_title}\nОбщая позиция пользователя в дебатах (не обязательно его текущий тезис): {debate.user_position}\n"
                        f"Направление: {chat.side}\nТезис оппонента в Defense: {chat.seed_claim if chat.side == 'defense' else 'нет'}"
                    ),
                )
            ]
            + reply_context(message.reply_to_message_id, message.reply_to_content)
            + [AIMessage(role=m.role, content=m.content) for m in history]
        )
        owner, debate_id, chat_id = chat.user_id, chat.debate_id, chat.id

        return messages, owner, debate_id, chat_id

    async def _save_analysis(
        self,
        analysis_id: UUID,
        message_id: UUID,
        result: AnalysisResult,
    ) -> None:
        async with transaction(self.factory) as session:
            await AnalysisRepository(session).complete(
                analysis_id,
                message_id,
                values={
                    "is_substantive": result.is_substantive,
                    "overall_score": result.overall_score,
                    "confidence": result.confidence,
                    "dimensions": {d.key: d.model_dump() for d in result.dimensions},
                    "strengths": result.strengths,
                    "conduct_flags": result.conduct_flags,
                    "next_step": result.next_step,
                },
                issues=[
                    {"issue_type": issue.type, **issue.model_dump(exclude={"type"})}
                    for issue in result.issues
                ],
            )

            repo = DebateRepository(session)
            chat = await repo.message_chat(message_id)
            state = ProgressState(
                chat.scored_answers,
                chat.score_total,
                chat.good_streak,
                chat.mastered_at is not None,
            )

            while True:
                rows = await repo.progress_batch(chat)
                sequence = chat.progress_sequence

                for seq, status, substantive, score, critical in rows:
                    if status != "completed":
                        break
                    state = self.progression.advance(
                        state,
                        float(score) if substantive and score is not None else None,
                        critical,
                    )
                    sequence = seq

                repo.save_progress(
                    chat, state, self.progression.percentage(state), sequence
                )

                if len(rows) < 64 or sequence != rows[-1][0]:
                    break
