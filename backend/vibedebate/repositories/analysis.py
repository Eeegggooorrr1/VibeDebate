from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from vibedebate.models.analysis import AnalysisIssue, MessageAnalysis
from vibedebate.models.debate import ChatMessage, DebateChat


@dataclass
class AnalysisRepository:
    session: AsyncSession

    async def create(self, message_id: UUID) -> MessageAnalysis:
        analysis = MessageAnalysis(message_id=message_id, analysis_status="pending")
        self.session.add(analysis)
        await self.session.flush()

        return analysis

    async def get_or_create(self, message_id: UUID) -> MessageAnalysis:
        # The caller holds the chat lock to serialize creation and retries.
        analysis = await self.session.scalar(
            select(MessageAnalysis)
            .where(MessageAnalysis.message_id == message_id)
            .with_for_update()
        )

        if analysis is None:
            return await self.create(message_id)

        return analysis

    async def issues(self, analysis_id: UUID) -> list[AnalysisIssue]:
        return list(
            await self.session.scalars(
                select(AnalysisIssue)
                .where(AnalysisIssue.analysis_id == analysis_id)
                .order_by(AnalysisIssue.created_at, AnalysisIssue.id)
            )
        )

    async def claim(self, message_id: UUID) -> UUID | None:
        return await self.session.scalar(
            update(MessageAnalysis)
            .where(
                MessageAnalysis.message_id == message_id,
                MessageAnalysis.analysis_status == "pending",
            )
            .values(analysis_status="running", started_at=datetime.now(timezone.utc))
            .returning(MessageAnalysis.id)
        )

    async def fail(self, analysis_id: UUID) -> None:
        await self.session.execute(
            update(MessageAnalysis)
            .where(
                MessageAnalysis.id == analysis_id,
                MessageAnalysis.analysis_status == "running",
            )
            .values(analysis_status="failed", completed_at=datetime.now(timezone.utc))
        )

    async def complete(
        self,
        analysis_id: UUID,
        message_id: UUID,
        *,
        values: dict[str, Any],
        issues: list[dict[str, Any]],
    ) -> None:
        # Match the chat -> analysis lock order used by lazy creation/retry.
        await self.session.scalar(
            select(DebateChat)
            .join(ChatMessage)
            .where(ChatMessage.id == message_id)
            .with_for_update(of=DebateChat)
        )

        analysis = await self.session.get(
            MessageAnalysis, analysis_id, with_for_update=True
        )

        if analysis is None or analysis.analysis_status != "running":
            return

        for field, value in values.items():
            setattr(analysis, field, value)

        analysis.analysis_status = "completed"
        analysis.completed_at = datetime.now(timezone.utc)

        await self.session.execute(
            delete(AnalysisIssue).where(AnalysisIssue.analysis_id == analysis_id)
        )
        self.session.add_all(
            AnalysisIssue(analysis_id=analysis_id, **issue) for issue in issues
        )

        await self.session.execute(
            update(ChatMessage)
            .where(ChatMessage.id == message_id)
            .values(is_substantive=values["is_substantive"])
        )
